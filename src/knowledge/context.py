"""Deterministic, static analysis of a repository: file tree, imports,
docstrings, top-level defs, route decorators, and a local import graph --
built with `ast`, before any LLM call, so extraction reasons over
structured facts instead of raw file dumps. See selection.py for how a
small slice of this gets sent to the model.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

_IGNORED_DIRS = {"__pycache__", ".git", ".venv", "venv"}


@dataclass
class RouteInfo:
    method: str
    path: str
    function: str
    line: int


@dataclass
class FunctionInfo:
    name: str
    line: int
    params: list[str]
    docstring: str | None
    calls: set[str]  # names/attrs called in the function body
    raises: set[str]  # exception class names raised
    has_try_except: bool


@dataclass
class ClassInfo:
    name: str
    line: int
    docstring: str | None


@dataclass
class FileSummary:
    path: str  # posix-style, relative to repo root
    component: str  # top-level directory name, or "" if at repo root
    docstring: str | None
    imports: list[str]  # dotted module names
    classes: list[ClassInfo]
    functions: list[FunctionInfo]
    routes: list[RouteInfo]


@dataclass
class RepositoryContext:
    root: Path
    files: list[FileSummary]
    components: list[str]
    external_dependencies: set[str]
    local_import_graph: dict[str, set[str]] = field(default_factory=dict)  # file -> files it imports

    def file(self, path: str) -> FileSummary | None:
        return next((f for f in self.files if f.path == path), None)

    @property
    def test_files(self) -> list[str]:
        return [f.path for f in self.files if f.component == "tests"]

    def files_in(self, component: str) -> list[FileSummary]:
        return [f for f in self.files if f.component == component]


def build_context(repo_root: Path) -> RepositoryContext:
    repo_root = repo_root.resolve()
    py_files = sorted(
        p for p in repo_root.rglob("*.py") if not any(part in _IGNORED_DIRS for part in p.parts)
    )

    module_to_path: dict[str, str] = {}
    for path in py_files:
        rel = path.relative_to(repo_root)
        module_to_path[_module_name(rel)] = rel.as_posix()

    files = [
        _summarize_file(
            rel_posix=(rel := path.relative_to(repo_root)).as_posix(),
            component=rel.parts[0] if len(rel.parts) > 1 else "",
            source=path.read_text(encoding="utf-8"),
        )
        for path in py_files
    ]

    components = sorted({f.component for f in files if f.component})
    stdlib = getattr(sys, "stdlib_module_names", frozenset())

    external_dependencies: set[str] = set()
    local_import_graph: dict[str, set[str]] = {f.path: set() for f in files}

    for f in files:
        for imported in f.imports:
            resolved = _resolve_local_import(imported, module_to_path)
            if resolved and resolved != f.path:
                local_import_graph[f.path].add(resolved)
            else:
                top = imported.split(".")[0]
                if top not in stdlib and top not in components and top != "__future__":
                    external_dependencies.add(top)

    return RepositoryContext(
        root=repo_root,
        files=files,
        components=components,
        external_dependencies=external_dependencies,
        local_import_graph=local_import_graph,
    )


def _module_name(rel: Path) -> str:
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1].removesuffix(".py")
    return ".".join(parts)


def _resolve_local_import(imported: str, module_to_path: dict[str, str]) -> str | None:
    if imported in module_to_path:
        return module_to_path[imported]
    if "." in imported:
        parent = imported.rsplit(".", 1)[0]
        if parent in module_to_path:
            return module_to_path[parent]
    return None


def _summarize_file(rel_posix: str, component: str, source: str) -> FileSummary:
    tree = ast.parse(source, filename=rel_posix)
    docstring = ast.get_docstring(tree)

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    classes = [
        ClassInfo(name=n.name, line=n.lineno, docstring=ast.get_docstring(n))
        for n in tree.body
        if isinstance(n, ast.ClassDef)
    ]

    functions: list[FunctionInfo] = []
    routes: list[RouteInfo] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        functions.append(_summarize_function(node))
        routes.extend(_routes_from_decorators(node))

    return FileSummary(
        path=rel_posix,
        component=component,
        docstring=docstring,
        imports=imports,
        classes=classes,
        functions=functions,
        routes=routes,
    )


def _summarize_function(node: ast.FunctionDef) -> FunctionInfo:
    calls = {n.func.id for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    calls |= {
        n.func.attr for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    }
    raises = {
        n.exc.func.id
        for n in ast.walk(node)
        if isinstance(n, ast.Raise)
        and isinstance(n.exc, ast.Call)
        and isinstance(n.exc.func, ast.Name)
    }
    return FunctionInfo(
        name=node.name,
        line=node.lineno,
        params=[a.arg for a in node.args.args],
        docstring=ast.get_docstring(node),
        calls=calls,
        raises=raises,
        has_try_except=any(isinstance(n, ast.Try) for n in ast.walk(node)),
    )


def _routes_from_decorators(node: ast.FunctionDef) -> list[RouteInfo]:
    routes = []
    for decorator in node.decorator_list:
        if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name)):
            continue
        if decorator.func.id != "route" or len(decorator.args) < 2:
            continue
        method_arg, path_arg = decorator.args[0], decorator.args[1]
        if isinstance(method_arg, ast.Constant) and isinstance(path_arg, ast.Constant):
            routes.append(
                RouteInfo(
                    method=method_arg.value,
                    path=path_arg.value,
                    function=node.name,
                    line=node.lineno,
                )
            )
    return routes

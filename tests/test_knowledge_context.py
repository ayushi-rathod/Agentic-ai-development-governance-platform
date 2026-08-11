from pathlib import Path

from src.knowledge.context import build_context


def _write(root: Path, rel_path: str, content: str) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_components_are_top_level_directories(tmp_path):
    _write(tmp_path, "api/__init__.py", '"""API."""\n')
    _write(tmp_path, "api/handlers.py", '"""Handlers."""\n')
    _write(tmp_path, "services/__init__.py", '"""Services."""\n')

    context = build_context(tmp_path)
    assert context.components == ["api", "services"]


def test_local_import_is_resolved_to_a_file_not_an_external_dependency(tmp_path):
    _write(tmp_path, "a/__init__.py", "")
    _write(tmp_path, "a/mod.py", '"""A."""\n')
    _write(tmp_path, "b/__init__.py", "")
    _write(tmp_path, "b/mod.py", '"""B."""\nfrom a.mod import something\n')

    context = build_context(tmp_path)
    assert "a/mod.py" in context.local_import_graph["b/mod.py"]
    assert "a" not in context.external_dependencies


def test_third_party_import_is_an_external_dependency(tmp_path):
    _write(tmp_path, "a/__init__.py", "")
    _write(tmp_path, "a/mod.py", '"""A."""\nimport requests\n')

    context = build_context(tmp_path)
    assert "requests" in context.external_dependencies


def test_stdlib_import_is_not_an_external_dependency(tmp_path):
    _write(tmp_path, "a/__init__.py", "")
    _write(tmp_path, "a/mod.py", '"""A."""\nimport json\nimport os\n')

    context = build_context(tmp_path)
    assert context.external_dependencies == set()


def test_route_decorator_is_discovered_with_method_and_path(tmp_path):
    _write(
        tmp_path,
        "api/handlers.py",
        '"""API."""\n\n'
        "def route(method, path):\n"
        "    def decorator(fn):\n"
        "        return fn\n"
        "    return decorator\n\n\n"
        '@route("GET", "/things/{id}")\n'
        "def get_thing(request):\n"
        '    """Get a thing."""\n'
        "    return request\n",
    )

    context = build_context(tmp_path)
    handlers = context.file("api/handlers.py")
    assert len(handlers.routes) == 1
    assert handlers.routes[0].method == "GET"
    assert handlers.routes[0].path == "/things/{id}"
    assert handlers.routes[0].function == "get_thing"


def test_function_calls_and_raises_are_captured(tmp_path):
    _write(
        tmp_path,
        "a/mod.py",
        '"""A."""\n\n'
        "def do_thing(x):\n"
        "    if x is None:\n"
        '        raise ValueError("x is required")\n'
        "    helper(x)\n",
    )

    context = build_context(tmp_path)
    fn = context.file("a/mod.py").functions[0]
    assert fn.name == "do_thing"
    assert "helper" in fn.calls
    assert "ValueError" in fn.raises


def test_class_docstring_is_captured(tmp_path):
    _write(
        tmp_path,
        "models/thing.py",
        '"""Models."""\n\n'
        "class Widget:\n"
        '    """A thing that can be widgeted."""\n\n'
        "    id: str\n",
    )

    context = build_context(tmp_path)
    cls = context.file("models/thing.py").classes[0]
    assert cls.name == "Widget"
    assert cls.docstring == "A thing that can be widgeted."


def test_test_files_property(tmp_path):
    _write(tmp_path, "a/mod.py", '"""A."""\n')
    _write(tmp_path, "tests/test_mod.py", '"""Test."""\n')

    context = build_context(tmp_path)
    assert context.test_files == ["tests/test_mod.py"]

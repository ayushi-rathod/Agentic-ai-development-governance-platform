"""Context-selection strategy for the LLM step.

Instead of sending the whole repository to the model, send structured
summaries for every file (already compact -- see context.py) plus short
source excerpts for a small, scored subset of the most relevant files.
Deliberately simple: no embeddings, no vector search, no retrieval
framework -- a repo this size doesn't need one, and staying
understandable was an explicit constraint on this feature.
"""

from __future__ import annotations

from pathlib import Path

from src.knowledge.context import FileSummary, RepositoryContext

DEFAULT_MAX_SNIPPET_FILES = 5
DEFAULT_MAX_SNIPPET_LINES = 30


def _relevance_score(summary: FileSummary, in_degree: dict[str, int]) -> int:
    """Higher for files other files depend on, files that define routes,
    and files in the auth component -- a small, explicit proxy for "a
    reader would need to see this to understand the system," not a
    learned or configurable ranking.
    """
    score = in_degree.get(summary.path, 0)
    if summary.routes:
        score += 2
    if summary.component == "auth":
        score += 1
    return score


def select_context(
    context: RepositoryContext,
    max_snippet_files: int = DEFAULT_MAX_SNIPPET_FILES,
    max_snippet_lines: int = DEFAULT_MAX_SNIPPET_LINES,
) -> dict:
    in_degree: dict[str, int] = {f.path: 0 for f in context.files}
    for targets in context.local_import_graph.values():
        for target in targets:
            in_degree[target] = in_degree.get(target, 0) + 1

    ranked = sorted(context.files, key=lambda f: _relevance_score(f, in_degree), reverse=True)
    snippet_paths = [f.path for f in ranked[:max_snippet_files] if _relevance_score(f, in_degree) > 0]

    file_summaries = [
        {
            "path": f.path,
            "component": f.component,
            "docstring": f.docstring,
            "classes": [
                {"name": c.name, "line": c.line, "docstring": c.docstring} for c in f.classes
            ],
            "functions": [
                {
                    "name": fn.name,
                    "line": fn.line,
                    "params": fn.params,
                    "docstring": fn.docstring,
                    "calls": sorted(fn.calls),
                    "raises": sorted(fn.raises),
                    "has_try_except": fn.has_try_except,
                }
                for fn in f.functions
            ],
            "routes": [{"method": r.method, "path": r.path, "function": r.function} for r in f.routes],
            "imports": f.imports,
        }
        for f in context.files
    ]

    snippets = {path: _read_excerpt(context.root / path, max_snippet_lines) for path in snippet_paths}

    return {
        "repo_path": str(context.root),
        "components": context.components,
        "external_dependencies": sorted(context.external_dependencies),
        "files": file_summaries,
        "local_import_graph": {k: sorted(v) for k, v in context.local_import_graph.items()},
        "snippets": snippets,
    }


def _read_excerpt(path: Path, max_lines: int) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    excerpt = lines[:max_lines]
    if len(lines) > max_lines:
        excerpt.append(f"... ({len(lines) - max_lines} more lines)")
    return "\n".join(excerpt)

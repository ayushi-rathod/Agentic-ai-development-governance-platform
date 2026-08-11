"""Deterministic, AST-based checkers for the handful of common policy
categories this project ships with (secrets, SQL building, authorization,
input validation, error handling).

These exist so the review pipeline doesn't depend on an LLM to catch the
mechanical, unambiguous cases -- a regex/AST match is faster, free, and
100% reproducible. The LLM is reserved for cases with no matching checker
and for writing human-readable explanations. See CodeReviewAgent.
"""

from __future__ import annotations

import ast
from collections.abc import Callable

_SECRET_NAME_MARKERS = ("key", "secret", "token", "password", "credential")
_SQL_KEYWORDS = ("select", "insert", "update", "delete")
_SENSITIVE_FUNCTION_PREFIXES = (
    "delete_",
    "remove_",
    "update_",
    "admin_",
    "grant_",
    "rotate_",
    "revoke_",
)
_PRIVILEGED_FUNCTION_PREFIXES = ("rotate_", "revoke_", "grant_")


def _source(node: ast.AST, code: str) -> str:
    return (ast.get_source_segment(code, node) or "").strip()


def check_hardcoded_secret(code: str) -> str | None:
    """Flags `SOME_KEY = "literal string"` style assignments."""
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not (isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and any(
                marker in target.id.lower() for marker in _SECRET_NAME_MARKERS
            ):
                return _source(node, code)
    return None


def check_sql_string_building(code: str) -> str | None:
    """Flags `x = f"SELECT ... {var} ..."`-style query assembly."""
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.JoinedStr):
            continue
        text = _source(node.value, code).lower()
        if any(keyword in text for keyword in _SQL_KEYWORDS):
            return _source(node, code)
    return None


def check_missing_authorization(code: str) -> str | None:
    """Flags functions with sensitive-sounding names that never mention 'auth'."""
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if not node.name.startswith(_SENSITIVE_FUNCTION_PREFIXES):
            continue
        body_text = _source(node, code).lower()
        if "auth" not in body_text:
            return f"def {node.name}(...): performs a sensitive action with no authorization check"
    return None


def _subscript_key(node: ast.Subscript) -> str | None:
    slice_node = node.slice
    if isinstance(slice_node, ast.Index):  # pragma: no cover (Python < 3.9)
        slice_node = slice_node.value
    if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
        return slice_node.value
    return None


def check_missing_input_validation(code: str) -> str | None:
    """Flags functions that subscript a parameter with a literal key (e.g.
    request["user_id"]) without any guard (an `if` or `isinstance`)
    appearing in the function body first.
    """
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        param_names = {a.arg for a in node.args.args}
        body_text = _source(node, code)
        has_guard = "if " in body_text or "isinstance(" in body_text
        if has_guard:
            continue
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Subscript):
                continue
            if not (isinstance(sub.value, ast.Name) and sub.value.id in param_names):
                continue
            key = _subscript_key(sub)
            if key is not None:
                return (
                    f"def {node.name}(...): reads {sub.value.id}[{key!r}] "
                    "without validating it first"
                )
    return None


def _is_risky_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in {"open", "int", "float"}
    if isinstance(func, ast.Attribute):
        return (
            func.attr == "loads"
            and isinstance(func.value, ast.Name)
            and func.value.id == "json"
        )
    return False


def check_missing_error_handling(code: str) -> str | None:
    """Flags functions that call a fallible builtin (open/int/float/json.loads)
    with no surrounding try/except.

    Matches actual Call nodes, not a text substring -- an earlier substring
    version of this check (`"int(" in body_text`) false-flagged any
    function that merely called `print(...)`, since "print(" contains
    "int(" as a substring. AST matching on the call's real callee avoids
    that whole class of bug.
    """
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        has_try = any(isinstance(n, ast.Try) for n in ast.walk(node))
        if has_try:
            continue
        if any(
            isinstance(call, ast.Call) and _is_risky_call(call) for call in ast.walk(node)
        ):
            return f"def {node.name}(...): calls a fallible operation with no try/except"
    return None


def check_missing_audit_log(code: str) -> str | None:
    """Flags functions that rotate/revoke/grant a credential with no
    mention of an audit log call in their body.
    """
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if not node.name.startswith(_PRIVILEGED_FUNCTION_PREFIXES):
            continue
        body_text = _source(node, code).lower()
        if "audit" not in body_text:
            return f"def {node.name}(...): performs a privileged action with no audit log entry"
    return None


_HANDLER_PARAM_NAMES = frozenset({"request", "req", "ctx", "context"})


def find_handler_functions_missing_call(code: str, marker: str) -> list[tuple[str, int, bool]]:
    """For each top-level function that looks like a request handler (takes
    a parameter named request/req/ctx/context), reports (name, line,
    calls_marker). Used for convention checking, not policy checking --
    it's a heuristic tied to this repo's own handler-parameter naming
    convention, not a general-purpose analysis. See
    CodeReviewAgent.check_conventions.
    """
    tree = ast.parse(code)
    results = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        params = {a.arg for a in node.args.args}
        if not params & _HANDLER_PARAM_NAMES:
            continue
        calls = {n.func.id for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        calls |= {
            n.func.attr for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        }
        results.append((node.name, node.lineno, marker in calls))
    return results


CHECKERS: dict[str, Callable[[str], str | None]] = {
    "secrets": check_hardcoded_secret,
    "sql_injection": check_sql_string_building,
    "authorization": check_missing_authorization,
    "input_validation": check_missing_input_validation,
    "error_handling": check_missing_error_handling,
    "audit_logging": check_missing_audit_log,
}

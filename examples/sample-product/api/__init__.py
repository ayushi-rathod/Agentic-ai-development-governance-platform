"""API layer: HTTP-style route handlers.

Handlers are kept thin: validate input, enforce authorization, delegate
the actual work to services/. See services/ for where business logic
lives.
"""

from __future__ import annotations

from collections.abc import Callable


def route(method: str, path: str) -> Callable:
    """Registers a handler's HTTP method and path.

    A minimal stand-in for a real routing framework -- just enough
    structure for the knowledge extractor to deterministically discover
    route definitions from the decorator's own arguments.
    """

    def decorator(func: Callable) -> Callable:
        func.route_method = method
        func.route_path = path
        return func

    return decorator

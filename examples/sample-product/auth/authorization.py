"""Authorization for privileged, state-changing actions.

Every handler that performs a privileged action is expected to call
require_authorization() before doing anything else -- this is the
established convention the knowledge extractor discovers from this file
plus its callers, not an assumption.
"""

from __future__ import annotations


class AuthorizationError(PermissionError):
    """Raised when a caller is not authorized to perform an action."""


def require_authorization(request: dict) -> None:
    if not request.get("is_authorized"):
        raise AuthorizationError("caller is not authorized for this action")

"""Read-only endpoint for looking up a service account."""

from __future__ import annotations

from api import route
from services.account_service import get_account


@route("GET", "/accounts/{account_id}")
def get_user(request: dict) -> dict:
    """Look up a service account by id.

    Read-only, so unlike rotate_api_key this does not call
    require_authorization -- session validation happens upstream of this
    layer for read endpoints.
    """
    if "account_id" not in request:
        raise ValueError("account_id is required")
    account_id = request["account_id"]

    account = get_account(account_id)
    return {"status": "ok", "account_id": account.account_id, "name": account.name}

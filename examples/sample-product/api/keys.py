"""Admin endpoint for rotating a service account's API key."""

from __future__ import annotations

from api import route
from auth.authorization import require_authorization
from services.key_service import rotate_key


@route("POST", "/admin/accounts/{account_id}/keys/rotate")
def rotate_api_key(request: dict) -> dict:
    """Rotate the API key for a service account.

    Requires an authorized caller and a valid account_id.
    """
    require_authorization(request)

    if "account_id" not in request:
        raise ValueError("account_id is required")
    account_id = request["account_id"]

    new_key = rotate_key(account_id)
    return {"status": "ok", "account_id": account_id, "key_id": new_key.key_id}

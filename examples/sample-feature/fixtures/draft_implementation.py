"""Admin endpoint for rotating a service account's API key.

First draft. Fictional, written for this demo -- not derived from any
real system. Used as the ImplementationAgent.implement() fixture when
running --provider fake (see FakeLLMClient).
"""

import os
import secrets


def rotate_api_key(request):
    require_authorization(request)
    if "account_id" not in request:
        raise ValueError("account_id is required")
    account_id = request["account_id"]

    new_key = secrets.token_hex(32)
    store_key(account_id, new_key)
    return {"account_id": account_id, "rotated": True}


def require_authorization(request):
    if not request.get("is_authorized"):
        raise PermissionError("caller is not authorized for this action")


def store_key(account_id, key):
    # Persist the new key for the account (storage details omitted for
    # this demo).
    os.environ[f"SERVICE_KEY_{account_id}"] = key

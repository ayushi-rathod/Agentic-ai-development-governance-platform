"""Admin endpoint for rotating a service account's API key.

Remediated version: adds the audit-logging call required by the
payment-service domain governance layer (see
governance/products/sample-product/domains/payment-service/policies.md).
Used as the ImplementationAgent.remediate() fixture when running
--provider fake.
"""

import os
import secrets


def rotate_api_key(request):
    require_authorization(request)
    if "account_id" not in request:
        raise ValueError("account_id is required")
    account_id = request["account_id"]

    audit_log("rotate_api_key", account_id)

    new_key = secrets.token_hex(32)
    store_key(account_id, new_key)
    return {"account_id": account_id, "rotated": True}


def require_authorization(request):
    if not request.get("is_authorized"):
        raise PermissionError("caller is not authorized for this action")


def audit_log(action, account_id):
    # Record the privileged action for later review (storage details
    # omitted for this demo).
    print(f"AUDIT: {action} performed on account {account_id}")


def store_key(account_id, key):
    os.environ[f"SERVICE_KEY_{account_id}"] = key

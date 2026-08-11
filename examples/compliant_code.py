"""Compliant counterpart to violating_code.py.

Demonstrates a version of the same fictional service that satisfies every
rule in policies/sample_engineering_policy.md this project can check
deterministically (see README for why rule 6 stays a WARNING even here).
"""

import os
import sqlite3


def get_user(request):
    if "user_id" not in request:
        raise ValueError("user_id is required")
    user_id = request["user_id"]

    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cursor.fetchone()


def delete_account(request):
    require_authorization(request)
    if "user_id" not in request:
        raise ValueError("user_id is required")
    user_id = request["user_id"]

    conn = sqlite3.connect("app.db")
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()


def parse_config(path):
    try:
        data = open(path).read()
    except OSError as exc:
        raise ValueError(f"could not read config file: {exc}") from exc
    return data.split(",")


def require_authorization(request):
    if not request.get("is_authorized"):
        raise PermissionError("caller is not authorized for this action")


API_KEY = os.environ.get("API_KEY", "")

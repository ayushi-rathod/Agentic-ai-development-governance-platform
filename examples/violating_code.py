"""Example service module used to demonstrate policy violations.

This file is fictional and was written for this demo project. It is not
derived from, and does not resemble, any real company's production code.
"""

import sqlite3

API_KEY = "sk-demo-1234567890abcdef"


def get_user(request):
    user_id = request["user_id"]
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    return cursor.fetchone()


def delete_account(request):
    user_id = request["user_id"]
    conn = sqlite3.connect("app.db")
    query = f"DELETE FROM users WHERE id = {user_id}"
    conn.execute(query)
    conn.commit()


def parse_config(path):
    data = open(path).read()
    return data.split(",")

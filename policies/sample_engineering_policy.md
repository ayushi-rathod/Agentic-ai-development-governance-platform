# Sample Engineering Policy

This is a small, fictional policy document used to demonstrate the review
pipeline in this project. It is not derived from, and does not resemble,
any real company's internal standards.

## Rules

1. **Input validation** — Public functions must validate required fields before using them, and reject malformed input with a clear error.
2. **No hardcoded secrets** — Credentials, API keys, and tokens must never be hardcoded in source; load them from environment variables or a secrets manager.
3. **Parameterized queries** — Database queries must use parameterized statements; never build SQL by concatenating or formatting user input into a query string.
4. **Authorization on sensitive actions** — Functions that delete, update, or grant access must perform an authorization check before acting.
5. **Explicit error handling** — Public functions must handle expected failure cases, such as missing files or invalid input, instead of letting exceptions propagate uncaught.
6. **Observability for state changes** — Functions that change significant state should record that change for later review.

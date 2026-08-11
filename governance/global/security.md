# Global Security Governance

These rules apply to every product and every repository. They may be
extended with stricter, more specific rules at the product or domain
layer, but they can never be relaxed there -- see
[`governance/global/agent-governance.md`](agent-governance.md) for the
principle this enforces.

## Rules

1. **No hardcoded secrets** — Credentials, API keys, and tokens must never be hardcoded in source; load them from environment variables or a secrets manager.
2. **Parameterized queries** — Database queries must use parameterized statements; never build SQL by concatenating or formatting user input into a query string.
3. **Authorization on sensitive actions** — Functions that delete, update, rotate, revoke, or grant access must perform an authorization check before acting.

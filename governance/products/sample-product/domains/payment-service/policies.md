# payment-service Governance (sample-product)

Adds to (never relaxes) [sample-product governance](../../policies.md) and
[global governance](../../../../global/). payment-service handles
privileged account operations, so it carries the strictest requirements
in this example.

## Rules

1. **Audit logging for privileged operations** — Functions that rotate, revoke, or grant credentials must record an audit log entry before completing.

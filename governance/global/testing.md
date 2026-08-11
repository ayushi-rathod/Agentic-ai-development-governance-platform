# Global Testing Governance

Applies everywhere, same inheritance rule as
[`security.md`](security.md): lower layers may add to this, never relax it.

## Rules

1. **Input validation** — Public functions must validate required fields before using them, and reject malformed input with a clear error.
2. **Explicit error handling** — Public functions must handle expected failure cases, such as missing files or invalid input, instead of letting exceptions propagate uncaught.

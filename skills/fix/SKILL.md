# Skill: fix

## Purpose

Propose a targeted, compliant replacement snippet for each violation a
review found, with a rationale -- advisory output for a human (or the
`implement` skill's remediation call) to act on, not an auto-applied
patch.

## Executed by

`FixAgent` (`src/agents/fixer.py`).

## Inputs

- `code` -- the file that was reviewed.
- `results` -- the `EvaluationResult` list from `code-review`; only the
  `FAIL` entries produce a suggestion.
- `rules` -- the same `PolicyRule` list used for review, so each result
  can be mapped back to its category.

## Procedure

1. For a rule category with a known template (`secrets`, `sql_injection`,
   `authorization`, `input_validation`, `error_handling`,
   `audit_logging`), build a suggestion from the evidence text a
   checker already found -- no model call needed for these.
2. For any other category, fall back to a model call with the
   `FIX_SUGGESTION` task prompt.
3. Never touch the file on disk. `EvaluationAgent`/`FeatureWorkflow`
   verify compliance by re-running `code-review` against a *new*
   implementation (see the `implement` skill's remediation step), not by
   trusting this skill's suggestion was applied correctly.

## Output

A list of `FixSuggestion`: rule id, rationale, original snippet, suggested
snippet.

## Applicable governance

N/A -- like `code-review`, this skill operates on other artifacts rather
than being governed itself.

## Evaluation criteria

See `tests/test_fixer.py` (unit-level; this skill's output is templated
and deterministic for its five known categories, so it's tested as code
correctness rather than a behavioral eval):

- Each known category's template produces a snippet that would actually
  resolve the violation (e.g. the input-validation fix guards the
  specific dict key that was read unvalidated, not a hardcoded example
  key).
- An unrecognized category falls back to the model rather than silently
  producing nothing.

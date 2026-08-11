# Skill: extract-policy

## Purpose

Turn a governance document written in plain English/markdown into a
structured, machine-checkable list of rules. Every other skill in this
project consumes this skill's output rather than re-parsing prose itself.

## Executed by

`PolicyExtractorAgent` (`src/agents/policy_extractor.py`).

## Inputs

- `policy_text` -- a markdown document containing a numbered list of rules
  in the form `N. **Title** — description`.
- `source` -- a label identifying where the text came from (a file path or
  a governance layer name), carried through for traceability.

## Procedure

1. Send the policy text to the model with the `POLICY_EXTRACTION` task
   prompt, asking for a JSON list of rules (id, description, category,
   severity, detection_hint).
2. Parse and validate the response into `PolicyRule` objects (Pydantic
   raises on a malformed shape rather than silently accepting it).
3. Raise if the response contains zero rules -- an empty ruleset is
   always a failure for this skill, not a valid outcome.

## Output

A `PolicyRuleSet`: the source label plus an ordered list of `PolicyRule`.
When invoked by `GovernanceResolver` (see `code-review`'s "Applicable
governance" below), the rule ids are re-prefixed with the governance layer
that produced them (e.g. `GLOBAL-001`) and each rule gets a `layer` tag.

## Applicable governance

None -- this skill extracts governance, it doesn't itself need to satisfy
implementation-level rules like secret handling or SQL safety.

## Evaluation criteria

See `evaluations/policy_evals/`:

- Every rule in a known input document is extracted (count matches).
- Each rule is assigned the expected category -- including rules whose
  *description* contains a misleading substring (e.g. "invalid input"
  contains "valid"), which must not override a clear *title* signal.
- Malformed/empty input raises rather than returning an empty ruleset.

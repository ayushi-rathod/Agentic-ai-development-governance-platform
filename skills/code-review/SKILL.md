# Skill: code-review

## Purpose

Check a source file against a resolved set of governance rules, producing
a typed PASS/FAIL/WARNING result per rule with evidence and an
explanation -- not a free-text opinion.

## Executed by

`CodeReviewAgent` (`src/agents/code_reviewer.py`), using the deterministic
checkers in `src/agents/checks.py` wherever one exists for a rule's
category.

## Inputs

- `code` -- full source file contents.
- `rules` -- a `PolicyRule` list, typically the resolved output of
  `extract-policy` run across the global -> product -> domain governance
  layers (see `src/governance/resolver.py`).

## Procedure

For each rule:

1. Look up a deterministic checker by the rule's category
   (`secrets`, `sql_injection`, `authorization`, `input_validation`,
   `error_handling`, `audit_logging`). If one exists, its PASS/FAIL
   verdict is treated as ground truth -- the model is only asked to write
   the human-readable explanation, never to overrule the finding
   (`method = HYBRID`).
2. If no checker matches the category, fall back to a full model
   judgment (`method = LLM`). A `PASS` returned with confidence below
   0.75 is downgraded to `WARNING` rather than trusted outright.

## Output

A list of `EvaluationResult`: rule id, description, severity, status,
evidence, explanation, confidence, method.

## Applicable governance

N/A to this skill itself -- it's the mechanism that applies governance to
other artifacts.

## Evaluation criteria

See `evaluations/skill_evals/test_code_review_eval.py`:

- A known, deliberately-introduced violation (hardcoded secret, string-built
  SQL, missing authorization, missing input validation, missing error
  handling, missing audit log) is detected with `status = FAIL` and
  `method = HYBRID` -- not missed, and not downgraded to a model guess.
- A compliant file produces zero `FAIL` results across the same rule set.
- A rule with no matching checker never produces a `PASS` at full
  confidence -- the offline demo client can't actually evaluate it, and
  the result must say so (`WARNING`, not a false `PASS`).

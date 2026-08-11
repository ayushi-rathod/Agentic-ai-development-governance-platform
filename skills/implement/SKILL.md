# Skill: implement

## Purpose

Produce a first-draft implementation of a tech spec, and -- on QC
failure -- regenerate a corrected version given the specific violations
found. This is one skill, not two, because both operations are "write
code satisfying these constraints"; the second call just has more
constraints (the original spec plus the review feedback).

## Executed by

`ImplementationAgent` (`src/agents/implementation.py`).

## Inputs

- `implement`: a `TechSpec`.
- `remediate`: the previous code plus the list of `EvaluationResult`s that
  came back `FAIL`.

## Procedure

1. `implement`: send the spec's overview and requirements to the model
   with the `IMPLEMENTATION` task prompt; expect back `{"code": "..."}`.
2. `remediate`: send the previous code plus the structured violations
   (rule id, evidence, explanation) with the `REMEDIATION` task prompt;
   expect a corrected full file back.
3. Regeneration, not patching: remediation asks for a new version of the
   whole file rather than a diff, which is both a more realistic pattern
   for how coding agents actually fix review feedback and sidesteps the
   much harder problem of reliably auto-patching a file in place (see
   `FixAgent`'s docstring, which suggests fixes but never auto-applies
   them for the same reason).

## Output

A string: the full contents of a source file.

## Applicable governance

This skill's *output* is what every code-level rule in
`governance/global/`, `governance/products/*/policies.md`, and
`governance/products/*/domains/*/policies.md` is checked against by
`code-review`. It doesn't check itself -- that's the next skill's job,
which is why the workflow always runs `implement` and `code-review` as
separate steps rather than folding review into generation.

## Evaluation criteria

See `evaluations/workflow_evals/test_feature_workflow_eval.py`:

- The first draft, run through `code-review`, reproduces a known,
  expected violation (the offline demo's fixture is deliberately
  imperfect -- see `examples/sample-feature/fixtures/`).
- The remediated version, given that violation's `EvaluationResult`,
  resolves it without introducing a new failure elsewhere.

# Skill: create-tech-spec

## Purpose

Turn a feature request plus a resolved set of governance rules into a
technical spec with required sections, so implementation starts from an
explicit, traceable plan rather than the request text alone.

## Executed by

`TechSpecAgent` (`src/agents/tech_spec.py`).

## Inputs

- `feature_id` -- identifier carried through the whole workflow for
  traceability.
- `feature_request` -- plain-English/markdown description of the feature.
- `rules` -- the `PolicyRule` list resolved for the target product/domain
  (see `GovernanceResolver`), i.e. the output of `extract-policy` run
  across every applicable governance layer.

## Procedure

1. Send the feature request and rule list to the model with the
   `TECH_SPEC_CREATION` task prompt.
2. Require the response to name every requirement, security
   consideration, and test-plan item, each referencing the governance
   rule id it satisfies.
3. Derive a title from the request body (skipping a generic markdown
   heading like `# Feature Request`, which makes a useless spec title on
   its own).

## Output

A `TechSpec`: overview, requirements, security considerations, test plan,
and the list of governance rule ids applied -- all traceable back to
specific rule ids. `TechSpec.render_markdown()` produces the
`generated-tech-spec.md` artifact.

## Applicable governance

None directly -- a spec is documentation, not executable code, so the
code-level rules (secrets, SQL, authorization, ...) don't apply to this
skill's own output. It's judged on completeness and traceability instead
(see below).

## Evaluation criteria

See `evaluations/skill_evals/test_tech_spec_eval.py`:

- The rendered markdown contains every required section header (Overview,
  Requirements, Security Considerations, Test Plan, Governance Rules
  Applied).
- Every rule id passed in appears in `governance_rule_ids` -- nothing
  silently dropped.
- Rules in security-relevant categories (secrets, authorization,
  sql_injection, audit_logging) are represented in
  `security_considerations`, not just buried in the generic requirements
  list.

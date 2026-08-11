# Agent Governance (Global)

These are principles for how agents participate in the governed
development workflow. Unlike `security.md` and `testing.md`, this file is
documentation, not a machine-checked policy list -- it isn't parsed into
`PolicyRule` objects, it's referenced by the agents and skills it governs.

- **Agents draft, humans approve.** The feature-development workflow
  always ends at a human approval checkpoint (see
  `workflows/feature-development.yaml`). No agent can approve its own
  output or skip that checkpoint.
- **Scope.** An agent only acts within the step it was invoked for --
  spec, implementation, review, or evaluation -- and doesn't reach into
  artifacts outside that step.
- **Extend, never relax.** A product or domain governance layer may add
  rules that are stricter or more specific than the layer above it, but
  may not weaken or remove an inherited rule. This is enforced
  mechanically by `src/governance/resolver.py`, not just documented here
  -- see its `GovernanceViolationError`.
- **Traceability.** Every artifact produced during a workflow run is
  tagged with the feature id that produced it, so the chain from request
  to shipped code stays inspectable afterward (see
  `FeatureWorkflowResult.render_traceability_markdown`).

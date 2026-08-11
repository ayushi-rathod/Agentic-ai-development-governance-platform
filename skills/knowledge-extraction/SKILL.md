# Skill: knowledge-extraction

## Purpose

Capture reusable engineering knowledge from an existing repository, so
other agents don't have to rediscover its architecture, conventions,
dependencies, and feature behavior from scratch on every run.

This is a different question from policy extraction. Policy answers
*"what rules must the system obey?"* Knowledge answers *"what do I need
to know about this particular system to work in it correctly?"* -- see
the README's "Governance vs. Knowledge vs. Skills" section for the full
distinction.

## Executed by

`KnowledgeExtractionAgent` (`src/agents/knowledge_extractor.py`), backed
by `src/knowledge/context.py` (deterministic AST analysis) and
`src/knowledge/selection.py` (context-selection strategy).

## Inputs

- `repository` -- a path to the repository to analyze.
- Scope is currently whole-repository; a `--module` style filter is a
  natural extension (see README Future Improvements), not implemented
  here to keep the demo's surface area small.
- No pre-existing knowledge artifacts are merged in this version -- each
  run produces a fresh report. Incremental updates are also a future
  improvement.

## Procedure

1. **Inspect repository structure.** `build_context()` walks every `.py`
   file with `ast`, extracting per-file docstrings, imports, classes,
   functions (with line numbers, parameters, calls, raised exceptions),
   and any `@route(...)`-decorated handlers.
2. **Identify relevant components and entry points.** Top-level
   directories become components; files whose functions carry a `route`
   decorator become feature entry points.
3. **Analyze implementation patterns, identify dependencies and feature
   flows.** A local import graph is built from resolved imports;
   `external_dependencies` is whatever remains after removing stdlib and
   local-component names -- entirely deterministic, no model involved.
   Features are built by walking each entry point's import closure and
   matching it against files in the `tests` component that import it
   back.
4. **Extract terminology, attach evidence to findings.** A compact,
   pre-selected context (`select_context()`: structured summaries for
   every file, source excerpts for only the most relevant few -- see its
   docstring for the relevance scoring) is sent to the model with the
   `KNOWLEDGE_SYNTHESIS` task. The model writes findings (authorization
   pattern, validation pattern, test organization, "files that change
   together", "how to add an endpoint"), glossary definitions, and a
   short architecture overview -- each citing evidence paths.
5. **Ground the model's claims.** Every evidence citation is checked
   against the real file list. A citation to a file that doesn't exist is
   dropped; a finding that loses all its evidence that way is kept but
   marked `uncertain=True` at low confidence rather than presented as
   fact, and a glossary term with no valid evidence is dropped entirely.
   See `KnowledgeExtractionAgent`'s docstring for the full reliability
   argument.
6. **Generate knowledge artifacts.** `src/knowledge/artifacts.py` renders
   the report into `KNOWLEDGE.md`, `FEATURES.yaml`, `GLOSSARY.md`,
   `architecture.md` (with a Mermaid diagram built from the same
   deterministic dependency chains, not from the model), and a
   `knowledge.json` sidecar for programmatic reuse.
7. **Flag uncertain findings for human review.** Surfaced both in the CLI
   output and in `KNOWLEDGE.md` itself (marked `_(uncertain -- needs
   human review)_`), never silently dropped or silently trusted.

## Outputs

- `KNOWLEDGE.md`, `FEATURES.yaml`, `GLOSSARY.md`, `architecture.md`
- `knowledge.json` (machine-readable; consumed by
  `CodeReviewAgent.check_conventions()` via `review --knowledge`)

## Applicable governance

None -- like `extract-policy`, this skill produces context for other
skills rather than being itself subject to code-level policy rules.

## Evaluation criteria

See `evaluations/knowledge_evals/`:

- **Known fact extraction**: a clearly-wired pattern (authorization
  routed through one specific function) is extracted, citing the correct
  files.
- **Cross-file dependency**: a feature spanning route + service +
  authorization + tests is reconstructed with all of those files present
  in its `dependencies`/`tests`.
- **Unsupported claim**: a dependency that was never imported (e.g.
  Redis) never appears in `external_dependencies` -- this is enforced
  structurally (dependency extraction has no model in the loop at all),
  not just by prompting.
- **Domain glossary**: a term clearly defined in code (a class with a
  docstring) is extracted with correct evidence; a claim with no valid
  evidence never reaches the published glossary.

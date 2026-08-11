"""Turns a repository into a KnowledgeReport.

Reliability design (see the "Important reliability requirement" this
implements): structural facts that have one unambiguous right answer --
which components exist, what imports what, which files a route's
handler transitively depends on, which test files exercise it -- are
computed directly from `RepositoryContext`, never from the model. There
is no code path by which the model can cause a Feature or Dependency
that doesn't actually exist in the repo.

The model (real or fake, via the same KNOWLEDGE_SYNTHESIS task and the
same selection.select_context() payload) is used only for the genuinely
interpretive part: writing findings/glossary definitions/an architecture
overview. Every evidence citation it returns is checked against the
real file list afterward -- an evidence entry naming a file that doesn't
exist is dropped, and if a finding loses all its evidence that way it's
kept but marked `uncertain=True` at low confidence rather than silently
presented as fact. A glossary term that ends up with no valid evidence
is dropped outright rather than published unsupported.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.knowledge.context import FunctionInfo, RepositoryContext, build_context
from src.knowledge.selection import select_context
from src.llm.client import LLMClient
from src.models.knowledge import (
    ArchitectureFlow,
    Component,
    Dependency,
    Feature,
    GlossaryTerm,
    KnowledgeFinding,
    KnowledgeReport,
)

SYSTEM_PROMPT = """\
[TASK:KNOWLEDGE_SYNTHESIS]
You are documenting an existing codebase for other AI agents to use as
context. You will receive a JSON object describing the repository:
components, per-file summaries (docstring, classes, functions with their
line numbers/calls/raises, routes, imports), a local import graph, and
short source excerpts for the most relevant files.

Produce findings that would help an agent work in this codebase
correctly: how authorization is wired, how input validation is handled,
how tests are organized, which files change together for a feature, and
how a new endpoint would typically be added. Also list domain-specific
terms worth defining (from class names/docstrings) and a short
architecture overview paragraph.

Hard rules:
- Every finding and every glossary term MUST cite evidence as "path" or
  "path:line" using ONLY paths that appear in the "files" list you were
  given. Never cite a file, module, or technology that isn't present in
  the provided context.
- If you are not confident a statement is well-supported, do not include
  it rather than guessing.

Reply with ONLY a JSON object of this exact shape:
{
  "findings": [{"category": "...", "statement": "...", "evidence": ["path:line", ...]}],
  "glossary": [{"term": "...", "definition": "...", "evidence": ["path:line", ...]}],
  "architecture_overview": "..."
}
"""

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    return _SLUG_RE.sub("-", name.lower()).strip("-")


class KnowledgeExtractionAgent:
    def __init__(self, client: LLMClient):
        self._client = client

    def extract(self, repo_path: str | Path) -> KnowledgeReport:
        context = build_context(Path(repo_path))
        known_paths = {f.path for f in context.files}

        components = self._build_components(context)
        dependencies = self._build_dependencies(context)
        features = self._build_features(context)
        flows = self._build_flows(context)

        payload = select_context(context)
        raw = self._client.complete(SYSTEM_PROMPT, json.dumps(payload))
        data = json.loads(raw)

        findings = []
        for index, item in enumerate(data.get("findings", []), start=1):
            evidence, confidence, uncertain = self._ground(item.get("evidence") or [], known_paths)
            findings.append(
                KnowledgeFinding(
                    id=f"KF-{index:03d}",
                    category=item["category"],
                    statement=item["statement"],
                    evidence=evidence,
                    confidence=confidence,
                    uncertain=uncertain,
                )
            )

        glossary = []
        for item in data.get("glossary", []):
            evidence, _confidence, uncertain = self._ground(item.get("evidence") or [], known_paths)
            if uncertain or not evidence:
                continue  # don't publish an unsupported glossary claim at all
            glossary.append(GlossaryTerm(term=item["term"], definition=item["definition"], evidence=evidence))

        return KnowledgeReport(
            repo_path=str(Path(repo_path)),
            components=components,
            findings=findings,
            dependencies=dependencies,
            flows=flows,
            features=features,
            glossary=glossary,
            architecture_overview=data.get("architecture_overview", ""),
        )

    @staticmethod
    def _ground(evidence: list[str], known_paths: set[str]) -> tuple[list[str], float, bool]:
        """Keeps only citations whose file actually exists; scores confidence
        by how much of the original citation list survived that check."""
        valid = [e for e in evidence if e.split(":")[0] in known_paths]
        if not evidence or not valid:
            return [], 0.2, True
        if len(valid) == len(evidence):
            return valid, 0.95, False
        return valid, 0.5, True

    def _build_components(self, context: RepositoryContext) -> list[Component]:
        components = []
        for name in context.components:
            files = context.files_in(name)
            init_file = next((f for f in files if f.path.endswith("__init__.py")), None)
            if init_file and init_file.docstring:
                description = init_file.docstring.splitlines()[0]
            else:
                described = next((f.docstring for f in files if f.docstring), None)
                description = described.splitlines()[0] if described else f"{name}/ component"
            components.append(Component(name=name, description=description, files=[f.path for f in files]))
        return components

    def _build_dependencies(self, context: RepositoryContext) -> list[Dependency]:
        deps = [
            Dependency(kind="internal", source=source, target=target)
            for source, targets in context.local_import_graph.items()
            for target in sorted(targets)
        ]
        for name in sorted(context.external_dependencies):
            for f in context.files:
                if name in {imp.split(".")[0] for imp in f.imports}:
                    deps.append(Dependency(kind="external", source=f.path, target=name))
        return deps

    def _build_features(self, context: RepositoryContext) -> list[Feature]:
        features = []
        for f in context.files:
            if not f.routes:
                continue
            route = f.routes[0]
            primary_func: FunctionInfo | None = next(
                (fn for fn in f.functions if fn.name == route.function), None
            )
            description = (
                primary_func.docstring.splitlines()[0]
                if primary_func and primary_func.docstring
                else f"{route.method} {route.path}"
            )
            chain = self._dependency_chain(context, f.path)
            tests = sorted(
                other.path
                for other in context.files
                if other.component == "tests" and f.path in context.local_import_graph.get(other.path, set())
            )
            evidence = [f"{f.path}:{primary_func.line}" if primary_func else f.path]
            features.append(
                Feature(
                    id=_slugify(route.function),
                    description=description,
                    entry_points=[f.path],
                    dependencies=[p for p in chain if p != f.path],
                    tests=tests,
                    evidence=evidence,
                )
            )
        return features

    def _build_flows(self, context: RepositoryContext) -> list[ArchitectureFlow]:
        flows = []
        for f in context.files:
            if not f.routes:
                continue
            route = f.routes[0]
            chain = self._dependency_chain(context, f.path)
            steps = [f"{route.method} {route.path} -> {f.path}:{route.function}()"]
            steps += [f"-> {node}" for node in chain[1:]]
            flows.append(ArchitectureFlow(name=f"{route.method} {route.path}", steps=steps, evidence=chain))
        return flows

    @staticmethod
    def _dependency_chain(context: RepositoryContext, start_path: str) -> list[str]:
        """Breadth-first closure over the local import graph, excluding
        tests -- "everything this entry point transitively pulls in."
        """
        chain = [start_path]
        seen = {start_path}
        frontier = [start_path]
        while frontier:
            next_frontier = []
            for node in frontier:
                for dep in context.local_import_graph.get(node, set()):
                    dep_file = context.file(dep)
                    if dep in seen or (dep_file and dep_file.component == "tests"):
                        continue
                    seen.add(dep)
                    chain.append(dep)
                    next_frontier.append(dep)
            frontier = next_frontier
        return chain

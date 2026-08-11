"""Renders a KnowledgeReport into the four human-readable artifacts the
brief asks for, plus a machine-readable knowledge.json sidecar that
`review --knowledge` loads (markdown is for people; CodeReviewAgent
needs the typed report, not a re-parse of prose).
"""

from __future__ import annotations

import re
from itertools import pairwise
from pathlib import Path

import yaml

from src.models.knowledge import ArchitectureFlow, KnowledgeReport

_NODE_ID_RE = re.compile(r"[^a-zA-Z0-9]")


def render_knowledge_md(report: KnowledgeReport) -> str:
    lines = [
        "# KNOWLEDGE.md",
        "",
        f"Generated from `{report.repo_path}`. Evidence-backed findings only --",
        "see FEATURES.yaml for the feature inventory and GLOSSARY.md for terms.",
        "",
        "## Components",
        "",
    ]
    for component in report.components:
        lines.append(f"- **{component.name}/** -- {component.description} ({len(component.files)} files)")

    lines += ["", "## Findings", ""]
    if not report.findings:
        lines.append("(none extracted)")
    for finding in report.findings:
        flag = " _(uncertain -- needs human review)_" if finding.uncertain else ""
        lines.append(f"### {finding.category}{flag}")
        lines.append("")
        lines.append(finding.statement)
        lines.append("")
        if finding.evidence:
            lines.append(f"Evidence: {', '.join(f'`{e}`' for e in finding.evidence)}")
        else:
            lines.append("Evidence: none -- do not treat this as established.")
        lines.append(f"Confidence: {finding.confidence:.2f}")
        lines.append("")

    return "\n".join(lines) + "\n"


def render_features_yaml(report: KnowledgeReport) -> str:
    data = {
        "features": [
            {
                "id": feature.id,
                "description": feature.description,
                "entry_points": feature.entry_points,
                "dependencies": feature.dependencies,
                "tests": feature.tests,
                "evidence": feature.evidence,
            }
            for feature in report.features
        ]
    }
    return yaml.safe_dump(data, sort_keys=False, default_flow_style=False)


def render_glossary_md(report: KnowledgeReport) -> str:
    lines = ["# GLOSSARY.md", "", "Domain terminology, defined only from what the repository supports.", ""]
    if not report.glossary:
        lines.append("(no terms extracted)")
    for term in report.glossary:
        lines.append(f"### {term.term}")
        lines.append("")
        lines.append(term.definition)
        lines.append("")
        lines.append(f"Evidence: {', '.join(f'`{e}`' for e in term.evidence)}")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_architecture_md(report: KnowledgeReport) -> str:
    lines = ["# architecture.md", ""]
    if report.architecture_overview:
        lines += [report.architecture_overview, ""]

    lines += ["## Flows", ""]
    if not report.flows:
        lines.append("(no routed entry points found -- nothing to diagram)")
    for flow in report.flows:
        lines.append(f"### {flow.name}")
        lines.append("")
        lines.extend(f"1. {step}" if i == 0 else f"   {step}" for i, step in enumerate(flow.steps))
        lines.append("")

    diagram = render_mermaid_flowchart(report.flows)
    if diagram:
        lines += ["## Diagram", "", "```mermaid", diagram, "```", ""]

    return "\n".join(lines) + "\n"


def render_mermaid_flowchart(flows: list[ArchitectureFlow]) -> str:
    """Built entirely from the deterministic dependency chains in
    `flow.evidence` -- no LLM involved, so the diagram can't show an edge
    that doesn't correspond to a real import.
    """
    edges: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for flow in flows:
        chain = flow.evidence
        for a, b in pairwise(chain):
            if (a, b) not in seen:
                seen.add((a, b))
                edges.append((a, b))
    if not edges:
        return ""

    def node_id(path: str) -> str:
        return _NODE_ID_RE.sub("_", path)

    lines = ["flowchart TD"]
    lines += [f'    {node_id(a)}["{a}"] --> {node_id(b)}["{b}"]' for a, b in edges]
    return "\n".join(lines)


def write_artifacts(report: KnowledgeReport, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "KNOWLEDGE.md": output_dir / "KNOWLEDGE.md",
        "FEATURES.yaml": output_dir / "FEATURES.yaml",
        "GLOSSARY.md": output_dir / "GLOSSARY.md",
        "architecture.md": output_dir / "architecture.md",
        "knowledge.json": output_dir / "knowledge.json",
    }
    paths["KNOWLEDGE.md"].write_text(render_knowledge_md(report), encoding="utf-8")
    paths["FEATURES.yaml"].write_text(render_features_yaml(report), encoding="utf-8")
    paths["GLOSSARY.md"].write_text(render_glossary_md(report), encoding="utf-8")
    paths["architecture.md"].write_text(render_architecture_md(report), encoding="utf-8")
    paths["knowledge.json"].write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return paths

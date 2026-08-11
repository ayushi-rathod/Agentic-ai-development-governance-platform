"""Models for knowledge extraction.

Knowledge answers "what does an agent need to know about this codebase
to work correctly?" -- a different question from governance's "what
rules must the system obey?" (models/policy.py) and the workflow's
"what's being built right now?" (models/workflow.py). Keeping it a
separate model module keeps that distinction visible in the code, not
just in prose.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Component(BaseModel):
    name: str  # top-level directory, e.g. "api"
    description: str
    files: list[str]


class KnowledgeFinding(BaseModel):
    id: str
    category: str  # e.g. "authorization_pattern", "test_organization"
    statement: str
    evidence: list[str] = Field(default_factory=list)  # "path" or "path:line"
    confidence: float = Field(ge=0.0, le=1.0)
    uncertain: bool = False


class Dependency(BaseModel):
    kind: str  # "internal" | "external"
    source: str  # the file doing the importing
    target: str  # module name (external) or file path (internal)


class ArchitectureFlow(BaseModel):
    name: str
    steps: list[str]  # ordered, human-readable, each traceable to evidence
    evidence: list[str] = Field(default_factory=list)


class Feature(BaseModel):
    id: str
    description: str
    entry_points: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class GlossaryTerm(BaseModel):
    term: str
    definition: str
    evidence: list[str] = Field(default_factory=list)


class KnowledgeReport(BaseModel):
    repo_path: str
    components: list[Component] = Field(default_factory=list)
    findings: list[KnowledgeFinding] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    flows: list[ArchitectureFlow] = Field(default_factory=list)
    features: list[Feature] = Field(default_factory=list)
    glossary: list[GlossaryTerm] = Field(default_factory=list)
    architecture_overview: str = ""

    @property
    def evidence_backed_count(self) -> int:
        return sum(1 for f in self.findings if f.evidence and not f.uncertain)

    @property
    def uncertain_findings(self) -> list[KnowledgeFinding]:
        return [f for f in self.findings if f.uncertain]

    @property
    def external_dependencies(self) -> list[str]:
        names = {d.target for d in self.dependencies if d.kind == "external"}
        return sorted(names)


class ConventionStatus(str, Enum):
    FOLLOWED = "FOLLOWED"
    DEVIATION = "DEVIATION"


class ConventionObservation(BaseModel):
    """Output of CodeReviewAgent.check_conventions().

    Deliberately not an EvaluationResult / Status: a convention deviation
    is informational, never a blocking FAIL on its own -- see
    CodeReviewAgent's docstring for why these are kept structurally
    separate from policy results rather than reusing that model with a
    softer status value.
    """

    convention: str
    description: str
    status: ConventionStatus
    evidence: str
    note: str

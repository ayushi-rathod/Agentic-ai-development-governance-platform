"""Structured data models shared by every agent.

Keeping these in one place means each agent's contract is defined by a type,
not by prose in a prompt -- callers get validation for free and the CLI/tests
can rely on stable shapes regardless of which LLM backend produced them.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


class CheckMethod(str, Enum):
    """How a result was produced -- lets a report distinguish a regex match
    from an LLM opinion, which matters when you're deciding how much to
    trust a FAIL."""

    DETERMINISTIC = "DETERMINISTIC"
    LLM = "LLM"
    HYBRID = "HYBRID"


class PolicyRule(BaseModel):
    id: str
    description: str
    category: str
    severity: Severity
    detection_hint: str | None = Field(
        default=None,
        description="Optional short keyword the reviewer can use to select "
        "a deterministic checker for this rule (e.g. 'hardcoded_secret').",
    )
    layer: str | None = Field(
        default=None,
        description="Which governance layer contributed this rule (e.g. "
        "'global', 'product:sample-product', 'domain:payment-service'). "
        "Unset for rules extracted from a single ad-hoc policy file.",
    )


class PolicyRuleSet(BaseModel):
    source: str
    rules: list[PolicyRule]


class Violation(BaseModel):
    rule_id: str
    file: str
    line: int | None = None
    evidence: str
    explanation: str


class FixSuggestion(BaseModel):
    rule_id: str
    rationale: str
    original_snippet: str
    suggested_snippet: str


class EvaluationResult(BaseModel):
    rule_id: str
    description: str
    severity: Severity
    status: Status
    evidence: str
    explanation: str
    confidence: float = Field(ge=0.0, le=1.0)
    method: CheckMethod


class EvaluationReport(BaseModel):
    policy_source: str
    code_source: str
    results: list[EvaluationResult]

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.status is Status.PASS)

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results if r.status is Status.FAIL)

    @property
    def warning_count(self) -> int:
        return sum(1 for r in self.results if r.status is Status.WARNING)

    @property
    def passed(self) -> bool:
        """True only if nothing failed. Warnings don't block."""
        return self.fail_count == 0

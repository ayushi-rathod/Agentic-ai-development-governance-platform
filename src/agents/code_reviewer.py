"""Reviews source code against a set of PolicyRule objects, and
optionally against extracted repository knowledge.

Design note (see README "Design decisions and tradeoffs" for the full
rationale): when a deterministic checker exists for a rule's category, its
PASS/FAIL verdict is treated as ground truth -- the LLM is only asked to
write the human-readable explanation, never to overrule the finding. Rules
with no matching checker fall back to a full LLM judgment, and a PASS the
model isn't confident about is downgraded to WARNING rather than trusted
outright.

check_conventions() is a separate, additive capability: it compares code
against a repository *convention* discovered by KnowledgeExtractionAgent
(e.g. "handlers call require_authorization()"), not a governance rule.
Deliberately kept off the review()/EvaluationResult path and returning a
different model (ConventionObservation, FOLLOWED/DEVIATION) -- a
convention deviation is informational, never a policy FAIL, unless an
actual PolicyRule with its own checker also catches it. Reusing
EvaluationResult with a softer status would blur that line; a caller
could accidentally treat a DEVIATION as a FAIL just by pattern-matching
on the model shape.
"""

from __future__ import annotations

import json
import re

from src.agents.checks import CHECKERS, find_handler_functions_missing_call
from src.llm.client import LLMClient
from src.models.knowledge import (
    ConventionObservation,
    ConventionStatus,
    KnowledgeReport,
)
from src.models.policy import CheckMethod, EvaluationResult, PolicyRule, Status

_MARKER_RE = re.compile(r"calling (\w+)\(\)")

SYSTEM_PROMPT = """\
[TASK:VIOLATION_REVIEW]
You are a code review assistant checking one engineering policy rule
against one source file.

You will receive a JSON object:
{
  "rule": {"id": ..., "description": ..., "category": ..., "severity": ...},
  "deterministic_evidence": "<snippet or null>",
  "code": "<full source file>"
}

If "deterministic_evidence" is not null, a static checker already found a
violation; write a clear one- or two-sentence explanation of why that
evidence violates the rule. If it is null, decide for yourself whether the
code violates the rule.

Reply with ONLY a JSON object of this exact shape:
{"status": "PASS" | "FAIL" | "WARNING", "confidence": <0.0-1.0>, "explanation": "..."}
"""

_LOW_CONFIDENCE_PASS_THRESHOLD = 0.75


class CodeReviewAgent:
    """Checks code against every rule in a PolicyRuleSet."""

    def __init__(self, client: LLMClient):
        self._client = client

    def review(self, code: str, rules: list[PolicyRule]) -> list[EvaluationResult]:
        return [self._review_one(code, rule) for rule in rules]

    def _review_one(self, code: str, rule: PolicyRule) -> EvaluationResult:
        checker = CHECKERS.get(rule.detection_hint or rule.category)

        if checker is not None:
            evidence = checker(code)
            status = Status.FAIL if evidence else Status.PASS
            explanation = self._explain(rule, evidence, code)
            return EvaluationResult(
                rule_id=rule.id,
                description=rule.description,
                severity=rule.severity,
                status=status,
                evidence=evidence or "(no matching pattern found)",
                explanation=explanation,
                confidence=1.0,
                method=CheckMethod.HYBRID,
            )

        judgment = self._judge(rule, code)
        status = Status(judgment["status"])
        confidence = float(judgment["confidence"])
        if status is Status.PASS and confidence < _LOW_CONFIDENCE_PASS_THRESHOLD:
            status = Status.WARNING
        return EvaluationResult(
            rule_id=rule.id,
            description=rule.description,
            severity=rule.severity,
            status=status,
            evidence="(no deterministic checker for this category)",
            explanation=judgment["explanation"],
            confidence=confidence,
            method=CheckMethod.LLM,
        )

    def _explain(self, rule: PolicyRule, evidence: str | None, code: str) -> str:
        payload = json.dumps(
            {
                "rule": rule.model_dump(mode="json"),
                "deterministic_evidence": evidence,
                "code": code,
            }
        )
        raw = self._client.complete(SYSTEM_PROMPT, payload)
        return json.loads(raw)["explanation"]

    def _judge(self, rule: PolicyRule, code: str) -> dict:
        payload = json.dumps(
            {
                "rule": rule.model_dump(mode="json"),
                "deterministic_evidence": None,
                "code": code,
            }
        )
        raw = self._client.complete(SYSTEM_PROMPT, payload)
        return json.loads(raw)

    def check_conventions(self, code: str, knowledge: KnowledgeReport) -> list[ConventionObservation]:
        """Checks code against the repo's established authorization
        convention (if KnowledgeExtractionAgent found one with good
        evidence). Returns [] if no such convention was found -- this
        never fabricates a convention to check against.
        """
        auth_finding = next(
            (
                f
                for f in knowledge.findings
                if f.category == "authorization_pattern" and not f.uncertain
            ),
            None,
        )
        if auth_finding is None:
            return []
        match = _MARKER_RE.search(auth_finding.statement)
        if match is None:
            return []
        marker = match.group(1)

        observations = []
        for name, line, calls_marker in find_handler_functions_missing_call(code, marker):
            status = ConventionStatus.FOLLOWED if calls_marker else ConventionStatus.DEVIATION
            note = (
                f"calls {marker}() as expected"
                if calls_marker
                else f"does not call {marker}(); may be intentional (e.g. a read-only "
                "endpoint) but deviates from the repo's established pattern -- not a "
                "policy failure by itself"
            )
            observations.append(
                ConventionObservation(
                    convention=f"authorization_pattern (established via {marker}())",
                    description=auth_finding.statement,
                    status=status,
                    evidence=f"function '{name}' at line {line}",
                    note=note,
                )
            )
        return observations

"""Coordinates the end-to-end workflow: extract rules, review code, propose
fixes, and (optionally) confirm a reference "already fixed" version of the
code satisfies the same policy.

Deliberately a plain class calling plain agent methods in sequence -- no
agent framework, no message bus. At this scale that would be indirection
for its own sake; the whole point of separate agent classes is that each
one is independently testable, not that they need a runtime to talk to
each other.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.agents.code_reviewer import CodeReviewAgent
from src.agents.evaluator import EvaluationAgent
from src.agents.fixer import FixAgent
from src.agents.policy_extractor import PolicyExtractorAgent
from src.llm.client import LLMClient
from src.models.policy import EvaluationReport, FixSuggestion, PolicyRule


@dataclass
class WorkflowResult:
    rules: list[PolicyRule]
    initial_report: EvaluationReport
    fixes: list[FixSuggestion]
    reference_report: EvaluationReport | None


class Orchestrator:
    def __init__(self, client: LLMClient):
        self._extractor = PolicyExtractorAgent(client)
        self._reviewer = CodeReviewAgent(client)
        self._fixer = FixAgent(client)
        self._evaluator = EvaluationAgent(self._reviewer)

    def run(
        self,
        policy_text: str,
        policy_source: str,
        code_text: str,
        code_source: str,
        reference_code: str | None = None,
        reference_source: str = "<reference>",
    ) -> WorkflowResult:
        rule_set = self._extractor.extract(policy_text, source=policy_source)

        initial_report = self._evaluator.evaluate(
            code_text, rule_set.rules, policy_source, code_source
        )
        fixes = self._fixer.propose_fixes(
            code_text, initial_report.results, rule_set.rules
        )

        reference_report = None
        if reference_code is not None:
            reference_report = self._evaluator.evaluate(
                reference_code, rule_set.rules, policy_source, reference_source
            )

        return WorkflowResult(
            rules=rule_set.rules,
            initial_report=initial_report,
            fixes=fixes,
            reference_report=reference_report,
        )

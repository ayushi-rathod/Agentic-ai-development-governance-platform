"""Generates (and, on QC failure, regenerates) source code for a tech spec.

Regeneration rather than patching is the deliberate design here: asking an
agent to "try again given this feedback" is both a more realistic pattern
for how coding agents actually remediate, and it avoids the much harder,
separate problem of reliably auto-patching a file in place (see
FixAgent's docstring for why that problem is intentionally out of scope).
"""

from __future__ import annotations

import json

from src.llm.client import LLMClient
from src.models.policy import EvaluationResult
from src.models.workflow import TechSpec

SYSTEM_PROMPT_IMPLEMENT = """\
[TASK:IMPLEMENTATION]
You are a software engineer. You will receive a JSON object describing a
technical spec: {"overview": ..., "requirements": [...]}.

Write a Python implementation satisfying every requirement. Reply with
ONLY a JSON object of this exact shape: {"code": "<full file contents>"}
"""

SYSTEM_PROMPT_REMEDIATE = """\
[TASK:REMEDIATION]
You are a software engineer fixing a failed policy review. You will
receive a JSON object: {"code": "<previous file contents>", "violations":
[{"rule_id": ..., "description": ..., "evidence": ..., "explanation": ...}, ...]}.

Return a corrected version of the file that resolves every violation
listed, without breaking anything that already passed. Reply with ONLY a
JSON object of this exact shape: {"code": "<full corrected file contents>"}
"""


class ImplementationAgent:
    def __init__(self, client: LLMClient):
        self._client = client

    def implement(self, spec: TechSpec) -> str:
        payload = json.dumps({"overview": spec.overview, "requirements": spec.requirements})
        raw = self._client.complete(SYSTEM_PROMPT_IMPLEMENT, payload)
        return json.loads(raw)["code"]

    def remediate(self, code: str, violations: list[EvaluationResult]) -> str:
        payload = json.dumps(
            {
                "code": code,
                "violations": [
                    {
                        "rule_id": v.rule_id,
                        "description": v.description,
                        "evidence": v.evidence,
                        "explanation": v.explanation,
                    }
                    for v in violations
                ],
            }
        )
        raw = self._client.complete(SYSTEM_PROMPT_REMEDIATE, payload)
        return json.loads(raw)["code"]

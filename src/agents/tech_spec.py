"""Turns a feature request plus resolved governance rules into a
structured technical specification.
"""

from __future__ import annotations

import json

from src.llm.client import LLMClient
from src.models.policy import PolicyRule
from src.models.workflow import TechSpec

SYSTEM_PROMPT = """\
[TASK:TECH_SPEC_CREATION]
You are a technical spec writer. You will receive a JSON object:
{
  "feature_request": "<plain-English feature request>",
  "rules": [{"id": ..., "description": ..., "category": ..., "severity": ...}, ...]
}

Write a technical spec for implementing the request that satisfies every
rule given. Reply with ONLY a JSON object of this exact shape:
{
  "overview": "<1-2 sentences>",
  "requirements": ["<one bullet per rule, referencing its id>", ...],
  "security_considerations": ["<bullets for security-relevant rules>", ...],
  "test_plan": ["<one bullet per rule describing how to test it>", ...]
}
"""


def _derive_title(feature_request: str, fallback: str, limit: int = 90) -> str:
    """First non-heading line(s) of the request, not the literal first line
    -- a request markdown file's first line is usually a generic "# Feature
    Request" heading, which makes a useless spec title on its own.
    """
    content_lines = [
        line.strip()
        for line in feature_request.strip().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    joined = " ".join(content_lines)
    if not joined:
        return fallback
    if len(joined) <= limit:
        return joined
    truncated = joined[:limit].rsplit(" ", 1)[0]
    return truncated + "..."


class TechSpecAgent:
    def __init__(self, client: LLMClient):
        self._client = client

    def create(
        self, feature_id: str, feature_request: str, rules: list[PolicyRule]
    ) -> TechSpec:
        payload = json.dumps(
            {
                "feature_request": feature_request,
                "rules": [r.model_dump(mode="json") for r in rules],
            }
        )
        raw = self._client.complete(SYSTEM_PROMPT, payload)
        data = json.loads(raw)

        return TechSpec(
            feature_id=feature_id,
            title=_derive_title(feature_request, fallback=feature_id),
            overview=data["overview"],
            requirements=data["requirements"],
            security_considerations=data["security_considerations"],
            test_plan=data["test_plan"],
            governance_rule_ids=[r.id for r in rules],
        )

"""Skill eval for code-review: did it detect the known violation?

Framed as the behavioral question skills/code-review/SKILL.md's
"Evaluation criteria" section poses, run against the real bundled example
files rather than synthetic snippets.
"""

from pathlib import Path

from src.agents.code_reviewer import CodeReviewAgent
from src.agents.policy_extractor import PolicyExtractorAgent
from src.governance.loader import load_layers
from src.governance.resolver import GovernanceResolver
from src.llm.client import FakeLLMClient
from src.models.policy import Status

ROOT = Path(__file__).resolve().parent.parent.parent


def test_code_review_detects_the_known_hardcoded_secret():
    """Did /code-review detect the known security violation?"""
    client = FakeLLMClient()
    extractor = PolicyExtractorAgent(client)
    policy_text = (ROOT / "policies" / "sample_engineering_policy.md").read_text()
    rules = extractor.extract(policy_text).rules
    code = (ROOT / "examples" / "violating_code.py").read_text()

    results = CodeReviewAgent(client).review(code, rules)
    secret_result = next(r for r in results if r.description.lower().startswith("credentials"))

    assert secret_result.status is Status.FAIL
    assert "API_KEY" in secret_result.evidence


def test_code_review_detects_the_domain_specific_audit_logging_gap():
    """Same question, against the layered-governance feature-workflow
    example: does the domain layer's rule actually get enforced?"""
    client = FakeLLMClient()
    layers = load_layers(ROOT / "governance", "sample-product", "payment-service")
    rules = GovernanceResolver(PolicyExtractorAgent(client)).resolve(layers).rules
    draft_code = (
        ROOT / "examples" / "sample-feature" / "fixtures" / "draft_implementation.py"
    ).read_text()

    results = CodeReviewAgent(client).review(draft_code, rules)
    audit_result = next(r for r in results if r.rule_id == "DOMAIN-PAYMENT-SERVICE-001")

    assert audit_result.status is Status.FAIL
    assert "rotate_api_key" in audit_result.evidence


def test_code_review_produces_no_false_fail_on_compliant_example():
    client = FakeLLMClient()
    extractor = PolicyExtractorAgent(client)
    policy_text = (ROOT / "policies" / "sample_engineering_policy.md").read_text()
    rules = extractor.extract(policy_text).rules
    code = (ROOT / "examples" / "compliant_code.py").read_text()

    results = CodeReviewAgent(client).review(code, rules)
    assert all(r.status is not Status.FAIL for r in results)

from src.agents.code_reviewer import CodeReviewAgent
from src.llm.client import FakeLLMClient
from src.models.knowledge import ConventionStatus, KnowledgeFinding, KnowledgeReport

FOLLOWED_CODE = "def create_thing(request):\n    require_auth(request)\n    return {}\n"
DEVIATION_CODE = "def create_thing(request):\n    return {}\n"


def _knowledge_with_auth_finding(uncertain: bool = False) -> KnowledgeReport:
    return KnowledgeReport(
        repo_path="<test>",
        findings=[
            KnowledgeFinding(
                id="KF-001",
                category="authorization_pattern",
                statement="Privileged actions are authorized by calling require_auth() before performing the action.",
                evidence=["auth/check.py:5"],
                confidence=0.95,
                uncertain=uncertain,
            )
        ],
    )


def _reviewer() -> CodeReviewAgent:
    return CodeReviewAgent(FakeLLMClient())


def test_handler_that_calls_the_marker_is_followed():
    [obs] = _reviewer().check_conventions(FOLLOWED_CODE, _knowledge_with_auth_finding())
    assert obs.status is ConventionStatus.FOLLOWED


def test_handler_that_skips_the_marker_is_a_deviation():
    [obs] = _reviewer().check_conventions(DEVIATION_CODE, _knowledge_with_auth_finding())
    assert obs.status is ConventionStatus.DEVIATION
    # ConventionStatus only has these two members -- there is no "FAIL"
    # value a caller could receive here even by mistake.
    assert set(ConventionStatus) == {ConventionStatus.FOLLOWED, ConventionStatus.DEVIATION}


def test_no_observations_when_no_authorization_finding_exists():
    empty_knowledge = KnowledgeReport(repo_path="<test>")
    assert _reviewer().check_conventions(FOLLOWED_CODE, empty_knowledge) == []


def test_no_observations_when_the_finding_is_uncertain():
    knowledge = _knowledge_with_auth_finding(uncertain=True)
    assert _reviewer().check_conventions(FOLLOWED_CODE, knowledge) == []


def test_no_observations_when_code_has_no_handler_shaped_functions():
    knowledge = _knowledge_with_auth_finding()
    code = "def helper(x):\n    return x\n"
    assert _reviewer().check_conventions(code, knowledge) == []

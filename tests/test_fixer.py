from src.agents import checks
from src.agents.fixer import FixAgent
from src.llm.client import FakeLLMClient
from src.models.policy import (
    CheckMethod,
    EvaluationResult,
    PolicyRule,
    Severity,
    Status,
)


def _rule(rule_id: str, category: str, description: str = "example rule") -> PolicyRule:
    return PolicyRule(
        id=rule_id,
        description=description,
        category=category,
        severity=Severity.HIGH,
        detection_hint=category,
    )


def _fail(rule_id: str, evidence: str) -> EvaluationResult:
    return EvaluationResult(
        rule_id=rule_id,
        description="example rule",
        severity=Severity.HIGH,
        status=Status.FAIL,
        evidence=evidence,
        explanation="n/a",
        confidence=1.0,
        method=CheckMethod.HYBRID,
    )


def _fixer() -> FixAgent:
    return FixAgent(FakeLLMClient())


def test_secret_fix_loads_from_environment():
    code = 'API_KEY = "sk-demo-123"\n'
    evidence = checks.check_hardcoded_secret(code)
    result = _fail("POL-001", evidence)
    [fix] = _fixer().propose_fixes(code, [result], [_rule("POL-001", "secrets")])
    assert fix.rule_id == "POL-001"
    assert "os.environ" in fix.suggested_snippet


def test_sql_fix_parameterizes_the_query():
    code = 'def f(user_id):\n    q = f"SELECT * FROM users WHERE id = {user_id}"\n    return q\n'
    evidence = checks.check_sql_string_building(code)
    result = _fail("POL-002", evidence)
    [fix] = _fixer().propose_fixes(code, [result], [_rule("POL-002", "sql_injection")])
    assert "?" in fix.suggested_snippet
    assert "user_id" in fix.suggested_snippet


def test_authorization_fix_adds_a_check():
    code = "def delete_account(request):\n    do_it(request)\n"
    evidence = checks.check_missing_authorization(code)
    result = _fail("POL-003", evidence)
    [fix] = _fixer().propose_fixes(code, [result], [_rule("POL-003", "authorization")])
    assert "require_authorization" in fix.suggested_snippet


def test_input_validation_fix_guards_the_right_key():
    code = 'def get_user(request):\n    user_id = request["user_id"]\n    return user_id\n'
    evidence = checks.check_missing_input_validation(code)
    result = _fail("POL-004", evidence)
    [fix] = _fixer().propose_fixes(code, [result], [_rule("POL-004", "input_validation")])
    assert '"user_id" not in request' in fix.suggested_snippet


def test_error_handling_fix_adds_try_except():
    code = "def parse_config(path):\n    return open(path).read()\n"
    evidence = checks.check_missing_error_handling(code)
    result = _fail("POL-005", evidence)
    [fix] = _fixer().propose_fixes(code, [result], [_rule("POL-005", "error_handling")])
    assert "except" in fix.suggested_snippet


def test_no_fix_proposed_for_passing_results():
    passing = EvaluationResult(
        rule_id="POL-001",
        description="example",
        severity=Severity.LOW,
        status=Status.PASS,
        evidence="n/a",
        explanation="n/a",
        confidence=1.0,
        method=CheckMethod.HYBRID,
    )
    fixes = _fixer().propose_fixes("x = 1\n", [passing], [_rule("POL-001", "secrets")])
    assert fixes == []


def test_unknown_category_falls_back_to_llm():
    result = _fail("POL-006", "no checker for this one")
    [fix] = _fixer().propose_fixes("x = 1\n", [result], [_rule("POL-006", "general")])
    assert fix.rule_id == "POL-006"
    assert "no offline fix template" in fix.rationale.lower()

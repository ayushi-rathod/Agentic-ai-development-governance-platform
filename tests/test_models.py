from src.models.policy import (
    CheckMethod,
    EvaluationReport,
    EvaluationResult,
    Severity,
    Status,
)


def _result(status: Status) -> EvaluationResult:
    return EvaluationResult(
        rule_id="POL-001",
        description="example rule",
        severity=Severity.HIGH,
        status=status,
        evidence="n/a",
        explanation="n/a",
        confidence=1.0,
        method=CheckMethod.DETERMINISTIC,
    )


def test_report_counts_each_status():
    report = EvaluationReport(
        policy_source="<policy>",
        code_source="<code>",
        results=[_result(Status.PASS), _result(Status.FAIL), _result(Status.WARNING)],
    )
    assert report.pass_count == 1
    assert report.fail_count == 1
    assert report.warning_count == 1


def test_passed_is_false_when_anything_fails():
    report = EvaluationReport(
        policy_source="<policy>",
        code_source="<code>",
        results=[_result(Status.PASS), _result(Status.FAIL)],
    )
    assert report.passed is False


def test_passed_is_true_with_only_warnings():
    report = EvaluationReport(
        policy_source="<policy>",
        code_source="<code>",
        results=[_result(Status.PASS), _result(Status.WARNING)],
    )
    assert report.passed is True

from src.agents.checks import (
    check_hardcoded_secret,
    check_missing_audit_log,
    check_missing_authorization,
    check_missing_error_handling,
    check_missing_input_validation,
    check_sql_string_building,
    find_handler_functions_missing_call,
)


def test_hardcoded_secret_detected():
    code = 'API_KEY = "sk-demo-123"\n'
    assert check_hardcoded_secret(code) is not None


def test_hardcoded_secret_not_flagged_when_loaded_from_env():
    code = "import os\nAPI_KEY = os.environ.get('API_KEY', '')\n"
    assert check_hardcoded_secret(code) is None


def test_sql_string_building_detected():
    code = 'def f(user_id):\n    q = f"SELECT * FROM users WHERE id = {user_id}"\n    return q\n'
    assert check_sql_string_building(code) is not None


def test_sql_parameterized_query_not_flagged():
    code = 'def f(user_id):\n    q = "SELECT * FROM users WHERE id = ?"\n    return q\n'
    assert check_sql_string_building(code) is None


def test_missing_authorization_detected():
    code = "def delete_account(request):\n    do_it(request)\n"
    assert check_missing_authorization(code) is not None


def test_authorization_present_not_flagged():
    code = (
        "def delete_account(request):\n"
        "    require_authorization(request)\n"
        "    do_it(request)\n"
    )
    assert check_missing_authorization(code) is None


def test_missing_input_validation_detected():
    code = 'def get_user(request):\n    user_id = request["user_id"]\n    return user_id\n'
    result = check_missing_input_validation(code)
    assert result is not None
    assert "user_id" in result


def test_input_validation_present_not_flagged():
    code = (
        'def get_user(request):\n'
        '    if "user_id" not in request:\n'
        '        raise ValueError("user_id is required")\n'
        '    return request["user_id"]\n'
    )
    assert check_missing_input_validation(code) is None


def test_missing_error_handling_detected():
    code = "def parse_config(path):\n    return open(path).read()\n"
    assert check_missing_error_handling(code) is not None


def test_error_handling_present_not_flagged():
    code = (
        "def parse_config(path):\n"
        "    try:\n"
        "        return open(path).read()\n"
        "    except OSError:\n"
        "        return ''\n"
    )
    assert check_missing_error_handling(code) is None


def test_error_handling_does_not_false_positive_on_print():
    # Regression test: an earlier substring-based version of this checker
    # matched "int(" against "print(" (which contains it as a substring)
    # and wrongly flagged any function that merely calls print().
    code = 'def audit_log(action):\n    print(f"AUDIT: {action}")\n'
    assert check_missing_error_handling(code) is None


def test_missing_audit_log_detected():
    code = "def rotate_api_key(request):\n    do_it(request)\n"
    result = check_missing_audit_log(code)
    assert result is not None
    assert "rotate_api_key" in result


def test_audit_log_present_not_flagged():
    code = (
        "def rotate_api_key(request):\n"
        '    audit_log("rotate_api_key", request)\n'
        "    do_it(request)\n"
    )
    assert check_missing_audit_log(code) is None


def test_audit_log_not_required_for_non_privileged_functions():
    code = "def get_user(request):\n    do_it(request)\n"
    assert check_missing_audit_log(code) is None


def test_find_handler_functions_missing_call_detects_missing_and_present():
    code = (
        "def create_thing(request):\n"
        "    require_auth(request)\n"
        "    return {}\n\n\n"
        "def get_thing(request):\n"
        "    return {}\n\n\n"
        "def helper(x):\n"  # no 'request'-like param -> not a handler, ignored
        "    return x\n"
    )
    results = find_handler_functions_missing_call(code, "require_auth")
    by_name = {name: calls_marker for name, _line, calls_marker in results}
    assert by_name == {"create_thing": True, "get_thing": False}

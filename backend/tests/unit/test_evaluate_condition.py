import pytest
from utils.evaluate_condition import evaluate_condition
from workflow.schemas.condition_nodes import (
    ConditionOperators,
    ConditionRule,
    IfCondition,
    IfConditionConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_condition(rules: list[ConditionRule], match_type: str = "ALL") -> IfCondition:
    return IfCondition(
        type="if_condition",
        config=IfConditionConfig(rules=rules, match_type=match_type),
    )


def make_rule(variable: str, operator: ConditionOperators, value) -> ConditionRule:
    return ConditionRule(variable=variable, operator=operator, value=value)


# ---------------------------------------------------------------------------
# EQUALS operator
# ---------------------------------------------------------------------------

def test_equals_exact_match():
    ctx = {"trigger": {"status": "active"}}
    condition = make_condition([make_rule("{{trigger.status}}", ConditionOperators.EQUALS, "active")])
    assert evaluate_condition(condition, ctx) is True


def test_equals_case_insensitive():
    ctx = {"trigger": {"status": "ACTIVE"}}
    condition = make_condition([make_rule("{{trigger.status}}", ConditionOperators.EQUALS, "active")])
    assert evaluate_condition(condition, ctx) is True


def test_equals_no_match():
    ctx = {"trigger": {"status": "inactive"}}
    condition = make_condition([make_rule("{{trigger.status}}", ConditionOperators.EQUALS, "active")])
    assert evaluate_condition(condition, ctx) is False


def test_equals_email_format_extracts_address():
    # "Alice Smith <alice@example.com>" should match against "alice@example.com"
    ctx = {"trigger": {"from": "Alice Smith <alice@example.com>"}}
    condition = make_condition([make_rule("{{trigger.from}}", ConditionOperators.EQUALS, "alice@example.com")])
    assert evaluate_condition(condition, ctx) is True


def test_equals_email_format_no_match():
    ctx = {"trigger": {"from": "Bob <bob@example.com>"}}
    condition = make_condition([make_rule("{{trigger.from}}", ConditionOperators.EQUALS, "alice@example.com")])
    assert evaluate_condition(condition, ctx) is False


def test_equals_two_email_format_strings():
    ctx = {"trigger": {"from": "Alice <alice@example.com>"}}
    condition = make_condition([make_rule("{{trigger.from}}", ConditionOperators.EQUALS, "Alice <alice@example.com>")])
    assert evaluate_condition(condition, ctx) is True


# ---------------------------------------------------------------------------
# CONTAINS operator
# ---------------------------------------------------------------------------

def test_contains_substring_match():
    ctx = {"trigger": {"subject": "Invoice for October"}}
    condition = make_condition([make_rule("{{trigger.subject}}", ConditionOperators.CONTAINS, "invoice")])
    assert evaluate_condition(condition, ctx) is True


def test_contains_case_insensitive():
    ctx = {"trigger": {"subject": "URGENT: action required"}}
    condition = make_condition([make_rule("{{trigger.subject}}", ConditionOperators.CONTAINS, "urgent")])
    assert evaluate_condition(condition, ctx) is True


def test_contains_no_match():
    ctx = {"trigger": {"subject": "Hello from Alice"}}
    condition = make_condition([make_rule("{{trigger.subject}}", ConditionOperators.CONTAINS, "invoice")])
    assert evaluate_condition(condition, ctx) is False


# ---------------------------------------------------------------------------
# EXISTS operator
# ---------------------------------------------------------------------------

def test_exists_variable_resolves():
    ctx = {"trigger": {"subject": "Hello"}}
    condition = make_condition([make_rule("{{trigger.subject}}", ConditionOperators.EXISTS, None)])
    assert evaluate_condition(condition, ctx) is True


def test_exists_variable_resolves_to_empty_string():
    # Empty string is still different from the original template → EXISTS is True
    ctx = {"trigger": {"subject": ""}}
    condition = make_condition([make_rule("{{trigger.subject}}", ConditionOperators.EXISTS, None)])
    assert evaluate_condition(condition, ctx) is True


# ---------------------------------------------------------------------------
# GREATER_THAN operator
# ---------------------------------------------------------------------------

def test_greater_than_true():
    ctx = {"node": {"count": "10"}}
    condition = make_condition([make_rule("{{node.count}}", ConditionOperators.GREATER_THAN, "5")])
    assert evaluate_condition(condition, ctx) is True


def test_greater_than_false():
    ctx = {"node": {"count": "3"}}
    condition = make_condition([make_rule("{{node.count}}", ConditionOperators.GREATER_THAN, "5")])
    assert evaluate_condition(condition, ctx) is False


def test_greater_than_equal_values_false():
    ctx = {"node": {"count": "5"}}
    condition = make_condition([make_rule("{{node.count}}", ConditionOperators.GREATER_THAN, "5")])
    assert evaluate_condition(condition, ctx) is False


def test_greater_than_non_numeric_returns_false():
    ctx = {"node": {"count": "not-a-number"}}
    condition = make_condition([make_rule("{{node.count}}", ConditionOperators.GREATER_THAN, "5")])
    assert evaluate_condition(condition, ctx) is False


# ---------------------------------------------------------------------------
# LESS_THAN operator
# ---------------------------------------------------------------------------

def test_less_than_true():
    ctx = {"node": {"count": "2"}}
    condition = make_condition([make_rule("{{node.count}}", ConditionOperators.LESS_THAN, "5")])
    assert evaluate_condition(condition, ctx) is True


def test_less_than_false():
    ctx = {"node": {"count": "8"}}
    condition = make_condition([make_rule("{{node.count}}", ConditionOperators.LESS_THAN, "5")])
    assert evaluate_condition(condition, ctx) is False


def test_less_than_non_numeric_returns_false():
    ctx = {"node": {"count": "abc"}}
    condition = make_condition([make_rule("{{node.count}}", ConditionOperators.LESS_THAN, "5")])
    assert evaluate_condition(condition, ctx) is False


# ---------------------------------------------------------------------------
# match_type: ALL vs ANY
# ---------------------------------------------------------------------------

def test_match_all_both_rules_pass():
    ctx = {"t": {"subject": "Invoice", "from": "alice@example.com"}}
    condition = make_condition(
        [
            make_rule("{{t.subject}}", ConditionOperators.CONTAINS, "invoice"),
            make_rule("{{t.from}}", ConditionOperators.EQUALS, "alice@example.com"),
        ],
        match_type="ALL",
    )
    assert evaluate_condition(condition, ctx) is True


def test_match_all_one_rule_fails():
    ctx = {"t": {"subject": "Invoice", "from": "bob@example.com"}}
    condition = make_condition(
        [
            make_rule("{{t.subject}}", ConditionOperators.CONTAINS, "invoice"),
            make_rule("{{t.from}}", ConditionOperators.EQUALS, "alice@example.com"),
        ],
        match_type="ALL",
    )
    assert evaluate_condition(condition, ctx) is False


def test_match_any_one_rule_passes():
    ctx = {"t": {"subject": "Hello", "from": "alice@example.com"}}
    condition = make_condition(
        [
            make_rule("{{t.subject}}", ConditionOperators.CONTAINS, "invoice"),
            make_rule("{{t.from}}", ConditionOperators.EQUALS, "alice@example.com"),
        ],
        match_type="ANY",
    )
    assert evaluate_condition(condition, ctx) is True


def test_match_any_all_rules_fail():
    ctx = {"t": {"subject": "Hello", "from": "bob@example.com"}}
    condition = make_condition(
        [
            make_rule("{{t.subject}}", ConditionOperators.CONTAINS, "invoice"),
            make_rule("{{t.from}}", ConditionOperators.EQUALS, "alice@example.com"),
        ],
        match_type="ANY",
    )
    assert evaluate_condition(condition, ctx) is False

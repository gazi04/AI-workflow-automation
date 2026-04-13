from typing import Any, Dict
from email.utils import parseaddr
from utils.resolve_variables import resolve_variables
from workflow.schemas.condition_nodes import IfCondition


def evaluate_condition(condition: IfCondition, run_context: Dict[str, Any]) -> bool:
    """
    Evaluates an IfConditionConfig against the current run_context.
    """
    rules = condition.config.rules
    match_type = condition.config.match_type

    results = []
    for rule in rules:
        actual_value = resolve_variables(rule.variable, run_context)
        expected_value = rule.value
        operator = rule.operator

        res = False

        actual_str = str(actual_value).lower().strip()
        expected_str = str(expected_value).lower().strip()

        if operator == "equals":
            # Extract just the email if it's formatted like "Name <email@domain>"
            _, parsed_actual = parseaddr(actual_str)
            _, parsed_expected = parseaddr(expected_str)

            if parsed_actual and "@" in parsed_actual:
                compare_target = (
                    parsed_expected
                    if (parsed_expected and "@" in parsed_expected)
                    else expected_str
                )
                res = parsed_actual == compare_target
            else:
                res = actual_str == expected_str

        elif operator == "contains":
            res = expected_str in actual_str
        elif operator == "exists":
            res = actual_value != rule.variable
        elif operator == "greater_than":
            try:
                res = float(actual_value) > float(expected_value)
            except (ValueError, TypeError):
                res = False
        elif operator == "less_than":
            try:
                res = float(actual_value) < float(expected_value)
            except (ValueError, TypeError):
                res = False

        results.append(res)

    if match_type == "ANY":
        final_res = any(results)
    else:
        final_res = all(results)
    return final_res

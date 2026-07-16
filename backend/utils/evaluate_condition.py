from typing import Any, Dict
from email.utils import parseaddr
from utils.resolve_variables import resolve_variables, VariableResolutionError
from workflow.schemas.condition_nodes import IfCondition, ConditionOperators


def evaluate_condition(condition: IfCondition, run_context: Dict[str, Any]) -> bool:
    """
    Evaluates an IfConditionConfig against the current run_context.
    """
    rules = condition.config.rules
    match_type = condition.config.match_type

    results = []
    for rule in rules:
        operator = rule.operator

        if operator == ConditionOperators.EXISTS:
            # "exists" = the variable path resolves to a value (incl. empty string).
            # A missing path makes resolve_variables raise → treat as does-not-exist.
            try:
                resolve_variables(rule.variable, run_context)
                res = True
            except VariableResolutionError:
                res = False
            results.append(res)
            continue

        actual_value = resolve_variables(rule.variable, run_context)
        expected_value = rule.value

        res = False

        actual_str = str(actual_value).lower().strip()
        expected_str = str(expected_value).lower().strip()

        if operator == ConditionOperators.EQUALS:
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

        elif operator == ConditionOperators.CONTAINS:
            res = expected_str in actual_str
        elif operator == ConditionOperators.GREATER_THAN:
            try:
                res = float(actual_value) > float(expected_value)
            except (ValueError, TypeError):
                res = False
        elif operator == ConditionOperators.LESS_THAN:
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

from typing import Any, Dict
from utils.resolve_variables import resolve_variables


def evaluate_condition(condition_config: Any, run_context: Dict[str, Any]) -> bool:
    """
    Evaluates an IfConditionConfig against the current run_context.
    """
    rules = condition_config.rules
    match_type = condition_config.match_type

    results = []
    for rule in rules:
        actual_value = resolve_variables(rule.variable, run_context)
        expected_value = rule.value
        operator = rule.operator

        if operator == "equals":
            res = str(actual_value).lower() == str(expected_value).lower()
        elif operator == "contains":
            res = str(expected_value).lower() in str(actual_value).lower()
        elif operator == "exists":
            res = (actual_value != rule.variable)
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
        else:
            res = False
            
        results.append(res)

    if match_type == "ANY":
        return any(results)
    return all(results)

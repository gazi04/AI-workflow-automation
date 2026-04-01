import re
from typing import Any, Dict


def resolve_variables(value: Any, context: Dict[str, Any]) -> Any:
    """
    Recursively scans for {{path.to.variable}} in strings, dicts, and lists, 
    and replaces them with actual values from the context.
    """
    if isinstance(value, str):
        def repl(match):
            # E.g., extracts "node_1.summary" and splits into ["node_1", "summary"]
            raw_match = match.group(0)
            path = match.group(1).strip().split('.')
            current = context
            try:
                for p in path:
                    # Handle both dictionary keys and object attributes
                    current = current[p] if isinstance(current, dict) else getattr(current, p)
                return str(current)
            except (KeyError, AttributeError, TypeError):
                raise Exception(
                    f"Could not resolve variable '{raw_match}'. "
                    f"The path '{path}' does not exist in the current context."
                )
        
        # Regex to find {{ anything }}
        return re.sub(r"\{\{\s*(.*?)\s*\}\}", repl, value)
    
    elif isinstance(value, dict):
        return {k: resolve_variables(v, context) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_variables(v, context) for v in value]
    
    return value

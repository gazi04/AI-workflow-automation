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
            path = match.group(1).strip().split('.')
            current = context
            try:
                for p in path:
                    # Handle both dictionary keys and object attributes
                    current = current[p] if isinstance(current, dict) else getattr(current, p)
                return str(current)
            except (KeyError, AttributeError, TypeError):
                # If the variable isn't found in the context, leave it unresolved (or handle the error)
                return match.group(0) 
        
        # Regex to find {{ anything }}
        return re.sub(r"\{\{\s*(.*?)\s*\}\}", repl, value)
    
    elif isinstance(value, dict):
        return {k: resolve_variables(v, context) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_variables(v, context) for v in value]
    
    return value

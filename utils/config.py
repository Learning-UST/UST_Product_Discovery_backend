import os
from dotenv import load_dotenv
import ast
load_dotenv()


def get_config_value(key, default=None):
    """
    Get a config value from environment variables.
    Automatically parses lists, ints, floats, and bools.
    Removes quotes for strings.
    """
    value = os.getenv(key)
    if value is None:
        return default
    # Remove surrounding quotes if present (single or double).
    if isinstance(value, str):
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1].strip()
    # Try to parse as list
    try:
        if value.startswith("[") and value.endswith("]"):
            return ast.literal_eval(value)
    except Exception:
        pass
    # Try to parse as int
    try:
        return int(value)
    except ValueError:
        pass
    # Try to parse as float
    try:
        return float(value)
    except ValueError:
        pass
    # Try to parse as bool
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    # Return as string
    return value

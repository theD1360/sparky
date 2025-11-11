"""Utility helper functions."""

import json
from typing import Any


def to_plain_obj(x: Any) -> Any:
    """Recursively converts an object to plain Python types (dicts, lists, primitives).

    Converts complex objects to basic types suitable for JSON serialization.

    Args:
        x: The object to convert

    Returns:
        A plain Python object (dict, list, str, int, float, bool, or None)
    """
    if isinstance(x, float) and x.is_integer():
        return int(x)
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    if isinstance(x, dict) or hasattr(x, "items"):
        try:
            items = x.items()
            return {str(k): to_plain_obj(v) for k, v in items}
        except Exception:
            return {str(k): to_plain_obj(v) for k, v in dict(x).items()}
    if isinstance(x, (list, tuple, set)) or (
        hasattr(x, "__iter__") and not isinstance(x, (str, bytes))
    ):
        try:
            return [to_plain_obj(v) for v in list(x)]
        except Exception:
            return [to_plain_obj(v) for v in x]
    try:
        return json.loads(json.dumps(x))
    except Exception:
        return str(x)

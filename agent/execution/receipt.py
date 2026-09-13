"""Durable, inert serialization for normalized provider evidence."""

from dataclasses import asdict, is_dataclass
from enum import Enum


def normalized_result_payload(result):
    """Convert an immutable ``ExecutionResult`` to JSON-safe inert evidence."""
    return _json_value(asdict(result))


def _json_value(value):
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, frozenset)):
        return [_json_value(item) for item in value]
    return value

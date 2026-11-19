"""A tiny JSON-schema validator.

Skills declare small schemas; this validates just enough to catch the failure
mode that matters: a model returning plausible prose in the wrong shape. It is
deliberately not a full JSON Schema implementation — supported keywords are
``type``, ``required``, ``properties``, ``items``, ``enum``, ``min_len``,
``max_len`` and ``nullable``.
"""

from __future__ import annotations

from typing import Any

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


class ValidationError(ValueError):
    """Raised with every failing path, so a repair prompt can name them."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors[:8]))


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return isinstance(value, _TYPES[expected])


def validate(payload: Any, schema: dict, *, path: str = "$") -> None:
    errors: list[str] = []
    _validate(payload, schema, path, errors)
    if errors:
        raise ValidationError(errors)


def is_valid(payload: Any, schema: dict) -> bool:
    try:
        validate(payload, schema)
        return True
    except ValidationError:
        return False


def _validate(value: Any, schema: dict, path: str, errors: list[str]) -> None:
    if value is None and schema.get("nullable"):
        return

    expected = schema.get("type")
    if expected:
        variants = expected if isinstance(expected, list) else [expected]
        if not any(_type_ok(value, variant) for variant in variants):
            errors.append(f"{path}: expected {' or '.join(variants)}")
            return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']}")

    if isinstance(value, str):
        if "min_len" in schema and len(value) < schema["min_len"]:
            errors.append(f"{path}: shorter than {schema['min_len']} characters")
        if "max_len" in schema and len(value) > schema["max_len"]:
            errors.append(f"{path}: longer than {schema['max_len']} characters")

    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            _validate(item, schema["items"], f"{path}[{index}]", errors)

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value or value[key] is None:
                errors.append(f"{path}.{key}: required")
        for key, child in schema.get("properties", {}).items():
            if key in value:
                _validate(value[key], child, f"{path}.{key}", errors)

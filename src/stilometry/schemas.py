"""Draft 2020-12 validation with optional jsonschema and offline fallback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "schemas"

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - exercised in minimal installs
    Draft202012Validator = None


def validation_backend() -> str:
    return "jsonschema-draft2020-12" if Draft202012Validator is not None else "stdlib-draft2020-12-fallback"


def _type_ok(value: Any, expected: str) -> bool:
    if isinstance(expected, list):
        return any(_type_ok(value, option) for option in expected)
    if expected == "null":
        return value is None
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
    }.get(expected, True)


def _fallback_validate(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []
    expected = schema.get("type")
    if expected and not _type_ok(value, expected):
        return [f"{path} must be {expected}"]
    if isinstance(value, dict):
        for field in schema.get("required", []):
            if field not in value:
                errors.append(f"{path}: missing required field {field}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            errors.extend(f"{path}: unknown field {key}" for key in value if key not in properties)
        for key, spec in properties.items():
            if key in value:
                errors.extend(_fallback_validate(value[key], spec, f"{path}.{key}"))
    if isinstance(value, list) and schema.get("items"):
        for index, item in enumerate(value):
            errors.extend(_fallback_validate(item, schema["items"], f"{path}[{index}]"))
    return errors


def validate_artifact(kind: str, data: dict[str, Any]) -> list[str]:
    schema = json.loads((SCHEMA_ROOT / f"{kind}.schema.json").read_text(encoding="utf-8"))
    if Draft202012Validator is not None:
        Draft202012Validator.check_schema(schema)
        return [error.message for error in Draft202012Validator(schema).iter_errors(data)]
    return _fallback_validate(data, schema)

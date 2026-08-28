"""A small JSON-Schema subset validator for the shipped closed schemas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import SchemaValidationError

SCHEMA_FILES = {
    "initial": "initial.schema.json",
    "question-review": "question-review.schema.json",
    "prompt-review": "prompt-review.schema.json",
    "manifest": "manifest.schema.json",
}


def schema_directory() -> Path:
    module = Path(__file__).resolve()
    candidates = (module.parents[2] / "schemas", module.parents[1] / "schemas")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("unable to locate shipped schemas")


def load_schema(name: str) -> dict[str, Any]:
    filename = SCHEMA_FILES[name]
    value = json.loads((schema_directory() / filename).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SchemaValidationError(f"schema {name} is not an object")
    return value


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def validate_schema(
    value: Any,
    schema: dict[str, Any],
    path: str = "$",
    root_schema: dict[str, Any] | None = None,
) -> None:
    root = root_schema or schema
    reference = schema.get("$ref")
    if isinstance(reference, str):
        if not reference.startswith("#/"):
            raise SchemaValidationError(f"{path}: unsupported schema reference {reference}")
        resolved: Any = root
        for component in reference[2:].split("/"):
            resolved = resolved[component.replace("~1", "/").replace("~0", "~")]
        if not isinstance(resolved, dict):
            raise SchemaValidationError(f"{path}: schema reference is not an object")
        validate_schema(value, resolved, path, root)
        return
    expected = schema.get("type")
    if isinstance(expected, str) and not _matches_type(value, expected):
        raise SchemaValidationError(f"{path}: expected {expected}")
    if "enum" in schema and value not in schema["enum"]:
        raise SchemaValidationError(f"{path}: value is outside enum")
    if isinstance(value, int | float) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaValidationError(f"{path}: below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaValidationError(f"{path}: above maximum")
    if isinstance(value, str) and "minLength" in schema and len(value) < schema["minLength"]:
        raise SchemaValidationError(f"{path}: string too short")
    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                validate_schema(item, item_schema, f"{path}[{index}]", root)
    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                raise SchemaValidationError(f"{path}: missing required field {key}")
        properties = schema.get("properties", {})
        for key, item in value.items():
            child = properties.get(key)
            if isinstance(child, dict):
                validate_schema(item, child, f"{path}.{key}", root)
            elif schema.get("additionalProperties") is False:
                raise SchemaValidationError(f"{path}: unexpected field {key}")


def validate_named(value: Any, name: str) -> None:
    validate_schema(value, load_schema(name))

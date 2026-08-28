"""Fail-closed schema normalization for the Claude Code provider boundary."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .errors import SchemaCompatibilityError

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
REMOVED_ROOT_METADATA = ("$schema", "$id")

# This is deliberately the subset implemented by schema_validation.py and used by
# the shipped output contracts. Expanding it requires matching host validation and
# provider compatibility tests; silently forwarding a new dialect feature could
# otherwise make Claude and the host enforce different contracts.
_SUPPORTED_KEYWORDS = frozenset(
    {
        "$defs",
        "$ref",
        "additionalProperties",
        "description",
        "enum",
        "items",
        "maximum",
        "minimum",
        "minLength",
        "properties",
        "required",
        "title",
        "type",
    }
)
_ROOT_METADATA = frozenset(REMOVED_ROOT_METADATA)
_SCALAR_TYPES = frozenset({"array", "boolean", "integer", "null", "number", "object", "string"})


def _fail(path: str, message: str) -> None:
    raise SchemaCompatibilityError(f"{path}: {message}")


def _validate_schema_node(node: Any, path: str, *, root: bool = False) -> None:
    if not isinstance(node, dict):
        _fail(path, "boolean and non-object schemas are not supported")

    allowed = _SUPPORTED_KEYWORDS | (_ROOT_METADATA if root else frozenset())
    unsupported = sorted(set(node) - allowed)
    if unsupported:
        _fail(path, f"unsupported schema keyword(s): {', '.join(unsupported)}")

    if "$ref" in node:
        reference = node["$ref"]
        if not isinstance(reference, str) or not reference.startswith("#/"):
            _fail(path, "only local JSON Pointer references are supported")
        semantic_siblings = set(node) - {"$ref", "title", "description"}
        if semantic_siblings:
            _fail(path, "$ref cannot have semantic sibling keywords in the supported subset")

    expected_type = node.get("type")
    if expected_type is not None and expected_type not in _SCALAR_TYPES:
        _fail(path, "type must be one supported scalar type name")

    for keyword in ("title", "description"):
        if keyword in node and not isinstance(node[keyword], str):
            _fail(path, f"{keyword} must be a string")

    required = node.get("required")
    if required is not None and (
        not isinstance(required, list) or any(not isinstance(item, str) for item in required)
    ):
        _fail(path, "required must be an array of strings")

    enum = node.get("enum")
    if enum is not None and not isinstance(enum, list):
        _fail(path, "enum must be an array")

    for keyword in ("minimum", "maximum", "minLength"):
        if keyword in node and (
            not isinstance(node[keyword], int | float) or isinstance(node[keyword], bool)
        ):
            _fail(path, f"{keyword} must be numeric")

    for keyword in ("properties", "$defs"):
        mapping = node.get(keyword)
        if mapping is None:
            continue
        if not isinstance(mapping, dict):
            _fail(path, f"{keyword} must be an object")
        for name, child in mapping.items():
            if not isinstance(name, str):
                _fail(path, f"{keyword} names must be strings")
            _validate_schema_node(child, f"{path}.{keyword}.{name}")

    if "items" in node:
        _validate_schema_node(node["items"], f"{path}.items")

    additional = node.get("additionalProperties")
    if additional is not None and not isinstance(additional, bool):
        _fail(path, "additionalProperties must be boolean in the supported subset")


def normalize_schema_for_claude(canonical_schema: dict[str, Any]) -> dict[str, Any]:
    """Return a validated deep copy safe for Claude Code's ``--json-schema`` flag.

    Canonical Draft 2020-12 identity remains on the caller's object. Claude Code
    2.1.247 cannot resolve that metaschema URI, so only the two root identity fields
    are removed from the provider-boundary copy. No nested constraint is deleted.
    """

    if canonical_schema.get("$schema") != DRAFT_2020_12:
        _fail("$", f"expected canonical dialect {DRAFT_2020_12!r}")
    schema_id = canonical_schema.get("$id")
    if not isinstance(schema_id, str) or not schema_id:
        _fail("$", "canonical schema requires a non-empty $id")
    _validate_schema_node(canonical_schema, "$", root=True)

    runtime_schema = deepcopy(canonical_schema)
    for keyword in REMOVED_ROOT_METADATA:
        runtime_schema.pop(keyword)
    return runtime_schema

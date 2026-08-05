#!/usr/bin/env python3
"""JSON Schema validator for codex-debate report JSON (schemaVersion 1).

Usage: python3 validate_debate_report.py input.json [--schema <path>]

Stdlib only. The schema file (schema/debate-report.schema.json next to the
scripts directory, by default) is the single source of truth: this module
loads and interprets it rather than duplicating its rules in code. Only the
JSON Schema (draft 2020-12) subset the schema actually uses is implemented:
type, properties, required, additionalProperties, enum, const, items,
minItems, pattern, oneOf, and $ref into $defs. A schema keyword outside that
subset raises SchemaError (exit 2) instead of being skipped, so the schema
can never silently promise more than is enforced.

Exit codes: 0 valid, 1 invalid, 2 usage or schema errors. All violations are
reported at once, each prefixed with a JSON-pointer path into the input
(e.g. /rounds/0/messages/2/objection/status).
"""

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "debate-report.schema.json"

# Keywords the interpreter enforces; anything else in a schema is an error.
SUPPORTED = (
    "type", "properties", "required", "additionalProperties",
    "enum", "const", "items", "minItems", "pattern", "oneOf", "$ref",
)
# Annotation-only keywords: legal in a schema, never affect validation.
# ($defs is a definition container, reached only through $ref.)
ANNOTATIONS = ("$schema", "$id", "$defs", "title", "description", "$comment")


class SchemaError(Exception):
    """The schema file is unreadable, malformed, or outside the supported subset."""


# ------------------------------------------------------------------ helpers

def _type_name(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _matches_type(value, name):
    if name == "null":
        return value is None
    if name == "boolean":
        return isinstance(value, bool)
    if name == "integer":
        return (isinstance(value, int) and not isinstance(value, bool)) or (
            isinstance(value, float) and value.is_integer()
        )
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "string":
        return isinstance(value, str)
    if name == "array":
        return isinstance(value, list)
    if name == "object":
        return isinstance(value, dict)
    raise SchemaError(f"unsupported type name {name!r} in schema")


def _json_eq(a, b):
    """Equality with JSON semantics: true/false never equal 1/0."""
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    return a == b


def _token(key):
    """Escape one JSON-pointer reference token (RFC 6901)."""
    return str(key).replace("~", "~0").replace("/", "~1")


def _at(ptr):
    return ptr or "/"


def _fmt_options(values):
    return ", ".join(repr(v) for v in values)


def _resolve(schema, root):
    """Follow $ref chains ('#/...' fragments only) to the target subschema."""
    seen = set()
    while isinstance(schema, dict) and "$ref" in schema:
        if id(schema) in seen:
            raise SchemaError(f"circular $ref chain at {schema.get('$ref')!r}")
        seen.add(id(schema))
        ref = schema["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            raise SchemaError(f"unsupported $ref {ref!r}; only '#/...' fragments are supported")
        siblings = [k for k in schema if k != "$ref" and k not in ANNOTATIONS]
        if siblings:
            raise SchemaError(f"$ref {ref!r} with sibling keywords {siblings} is not supported")
        target = root
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(target, dict) or part not in target:
                raise SchemaError(f"$ref {ref!r} does not resolve")
            target = target[part]
        schema = target
    return schema


# --------------------------------------------------------------- validation

def _discriminator(branches):
    """A property every branch declares with a const (e.g. block 'type'), or None."""
    common = None
    for branch in branches:
        props = branch.get("properties")
        if not isinstance(props, dict):
            return None
        keys = {k for k, sub in props.items() if isinstance(sub, dict) and "const" in sub}
        common = keys if common is None else common & keys
        if not common:
            return None
    return sorted(common)[0]


def _validate_one_of(value, branches, root, ptr, errors):
    matched = 0
    per_branch = []
    for branch in branches:
        branch_errors = []
        _validate(value, branch, root, ptr, branch_errors)
        per_branch.append(branch_errors)
        if not branch_errors:
            matched += 1
    if matched == 1:
        return
    if matched > 1:
        errors.append(f"{_at(ptr)}: matches {matched} oneOf variants; exactly one required")
        return
    # No branch matched. When the branches share a const-discriminated
    # property (the content-block 'type'), blame the discriminator: either
    # its value names no variant, or the named variant's own errors apply.
    resolved = [_resolve(branch, root) for branch in branches]
    disc = _discriminator(resolved)
    if disc is not None and isinstance(value, dict) and disc in value:
        consts = [branch["properties"][disc]["const"] for branch in resolved]
        for i, const in enumerate(consts):
            if _json_eq(value[disc], const):
                errors.extend(per_branch[i])
                return
        errors.append(f"{ptr}/{_token(disc)}: {value[disc]!r} is not one of ({_fmt_options(consts)})")
        return
    errors.append(f"{_at(ptr)}: does not match any allowed variant")
    errors.extend(min(per_branch, key=len))


def _validate(value, schema, root, ptr, errors):
    schema = _resolve(schema, root)
    if not isinstance(schema, dict):
        raise SchemaError(f"subschema at instance path {_at(ptr)} must be an object")
    for keyword in schema:
        if keyword not in SUPPORTED and keyword not in ANNOTATIONS:
            raise SchemaError(
                f"schema keyword {keyword!r} (reached at instance path {_at(ptr)}) "
                "is outside the supported subset"
            )

    if "type" in schema:
        names = schema["type"]
        names = [names] if isinstance(names, str) else names
        if not any(_matches_type(value, name) for name in names):
            errors.append(
                f"{_at(ptr)}: expected {' or '.join(names)}, got {_type_name(value)}"
            )
            return
    if "const" in schema and not _json_eq(value, schema["const"]):
        errors.append(f"{_at(ptr)}: {value!r} does not equal const {schema['const']!r}")
        return
    if "enum" in schema and not any(_json_eq(value, option) for option in schema["enum"]):
        errors.append(f"{_at(ptr)}: {value!r} is not one of ({_fmt_options(schema['enum'])})")
        return
    if "pattern" in schema and isinstance(value, str):
        if re.search(schema["pattern"], value) is None:
            errors.append(f"{_at(ptr)}: {value!r} does not match pattern {schema['pattern']!r}")
    if "oneOf" in schema:
        _validate_one_of(value, schema["oneOf"], root, ptr, errors)

    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", ()):
            if key not in value:
                errors.append(f"{ptr}/{_token(key)}: missing required property")
        for key, subschema in props.items():
            if key in value:
                _validate(value[key], subschema, root, f"{ptr}/{_token(key)}", errors)
        if "additionalProperties" in schema:
            extra_schema = schema["additionalProperties"]
            for key in value:
                if key in props:
                    continue
                if extra_schema is False:
                    errors.append(f"{ptr}/{_token(key)}: unknown property")
                elif isinstance(extra_schema, dict):
                    _validate(value[key], extra_schema, root, f"{ptr}/{_token(key)}", errors)
                elif extra_schema is not True:
                    raise SchemaError("additionalProperties must be a boolean or a schema")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(
                f"{_at(ptr)}: array must have at least {schema['minItems']} "
                f"item(s), got {len(value)}"
            )
        if "items" in schema:
            for i, item in enumerate(value):
                _validate(item, schema["items"], root, f"{ptr}/{i}", errors)


# ---------------------------------------------------------------- interface

def load_schema(path=DEFAULT_SCHEMA):
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as err:
        raise SchemaError(f"cannot read schema {path}: {err}") from err
    try:
        schema = json.loads(raw)
    except json.JSONDecodeError as err:
        raise SchemaError(f"schema {path} is not valid JSON: {err}") from err
    if not isinstance(schema, dict):
        raise SchemaError(f"schema {path} must be a JSON object")
    return schema


def validate(data, schema):
    """Return all violations as JSON-pointer-prefixed messages (empty when valid).

    Raises SchemaError if the schema strays outside the supported subset.
    """
    errors = []
    _validate(data, schema, schema, "", errors)
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate a codex-debate report JSON file against its schema."
    )
    parser.add_argument("input", help="path to the debate-report JSON file")
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA),
        help="path to the JSON Schema file (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    try:
        schema = load_schema(args.schema)
    except SchemaError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    in_path = Path(args.input)
    try:
        raw = in_path.read_text(encoding="utf-8")
    except OSError as err:
        print(f"error: cannot read {in_path}: {err}", file=sys.stderr)
        return 2
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as err:
        print(f"error: {in_path} is not valid JSON: {err}", file=sys.stderr)
        return 2

    try:
        violations = validate(data, schema)
    except SchemaError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    if violations:
        for violation in violations:
            print(f"error: {violation}", file=sys.stderr)
        return 1
    print(f"{in_path}: valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())

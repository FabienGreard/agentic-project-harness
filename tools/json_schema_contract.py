#!/usr/bin/env python3
"""Dependency-free executor for the JSON Schema subset committed by APH."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import re
from typing import Any


class SchemaContractError(RuntimeError):
    """A committed schema or reference is unsafe or unsupported."""


def _load(path: Path, cache: dict[Path, dict[str, Any]]) -> dict[str, Any]:
    resolved = path.resolve()
    if resolved in cache:
        return cache[resolved]
    try:
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SchemaContractError(f"cannot load schema {resolved.name}: {error}") from error
    if not isinstance(value, dict):
        raise SchemaContractError(f"schema {resolved.name} must be an object")
    cache[resolved] = value
    return value


def _pointer(document: dict[str, Any], pointer: str) -> dict[str, Any]:
    current: Any = document
    for raw in pointer.removeprefix("#/").split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            raise SchemaContractError(f"unresolved internal schema reference: {pointer}")
        current = current[token]
    if not isinstance(current, dict):
        raise SchemaContractError(f"schema reference is not an object: {pointer}")
    return current


def _resolve(
    reference: str,
    *,
    schema_path: Path,
    root_schema: dict[str, Any],
    cache: dict[Path, dict[str, Any]],
) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    if reference.startswith("#/"):
        return _pointer(root_schema, reference), schema_path, root_schema
    if "#" in reference or "/" in reference or "\\" in reference:
        raise SchemaContractError(f"unsupported external schema reference: {reference}")
    target_path = (schema_path.parent / reference).resolve()
    if target_path.parent != schema_path.parent.resolve():
        raise SchemaContractError(f"schema reference escapes its directory: {reference}")
    target = _load(target_path, cache)
    return target, target_path, target


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    raise SchemaContractError(f"unsupported schema type: {expected}")


def _json_equal(left: Any, right: Any) -> bool:
    """Compare values with JSON Schema equality, keeping booleans distinct from numbers."""
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left is right
    if isinstance(left, (int, float)) or isinstance(right, (int, float)):
        return (
            isinstance(left, (int, float))
            and not isinstance(left, bool)
            and isinstance(right, (int, float))
            and not isinstance(right, bool)
            and left == right
        )
    if isinstance(left, list) or isinstance(right, list):
        return (
            isinstance(left, list)
            and isinstance(right, list)
            and len(left) == len(right)
            and all(_json_equal(a, b) for a, b in zip(left, right))
        )
    if isinstance(left, dict) or isinstance(right, dict):
        return (
            isinstance(left, dict)
            and isinstance(right, dict)
            and set(left) == set(right)
            and all(_json_equal(left[key], right[key]) for key in left)
        )
    return type(left) is type(right) and left == right


def _validate(
    value: Any,
    schema: dict[str, Any],
    *,
    location: str,
    schema_path: Path,
    root_schema: dict[str, Any],
    cache: dict[Path, dict[str, Any]],
) -> list[str]:
    if "$ref" in schema:
        target, target_path, target_root = _resolve(
            schema["$ref"],
            schema_path=schema_path,
            root_schema=root_schema,
            cache=cache,
        )
        return _validate(
            value,
            target,
            location=location,
            schema_path=target_path,
            root_schema=target_root,
            cache=cache,
        )

    errors: list[str] = []
    if "const" in schema and not _json_equal(value, schema["const"]):
        errors.append(f"{location}: must equal {schema['const']!r}")
    if "enum" in schema and not any(
        _json_equal(value, candidate) for candidate in schema["enum"]
    ):
        errors.append(f"{location}: value is not in the allowed set")

    expected_type = schema.get("type")
    if expected_type is not None:
        if not isinstance(expected_type, str):
            raise SchemaContractError("schema type must be a string")
        if not _type_matches(value, expected_type):
            return [f"{location}: expected {expected_type}"]

    for branch in schema.get("allOf", []):
        errors.extend(
            _validate(
                value,
                branch,
                location=location,
                schema_path=schema_path,
                root_schema=root_schema,
                cache=cache,
            )
        )
    condition = schema.get("if")
    if isinstance(condition, dict):
        condition_errors = _validate(
            value,
            condition,
            location=location,
            schema_path=schema_path,
            root_schema=root_schema,
            cache=cache,
        )
        then = schema.get("then")
        if not condition_errors and isinstance(then, dict):
            errors.extend(
                _validate(
                    value,
                    then,
                    location=location,
                    schema_path=schema_path,
                    root_schema=root_schema,
                    cache=cache,
                )
            )

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{location}: missing required property {key!r}")
        min_properties = schema.get("minProperties")
        if isinstance(min_properties, int) and len(value) < min_properties:
            errors.append(f"{location}: requires at least {min_properties} properties")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            if schema.get("additionalProperties") is False:
                for key in sorted(set(value) - set(properties)):
                    errors.append(f"{location}: unsupported property {key!r}")
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, dict):
                    errors.extend(
                        _validate(
                            value[key],
                            child_schema,
                            location=f"{location}.{key}",
                            schema_path=schema_path,
                            root_schema=root_schema,
                            cache=cache,
                        )
                    )

    if isinstance(value, list):
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            errors.append(f"{location}: requires at least {min_items} items")
        if schema.get("uniqueItems") is True:
            if any(
                _json_equal(item, previous)
                for index, item in enumerate(value)
                for previous in value[:index]
            ):
                errors.append(f"{location}: items must be unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    _validate(
                        item,
                        item_schema,
                        location=f"{location}[{index}]",
                        schema_path=schema_path,
                        root_schema=root_schema,
                        cache=cache,
                    )
                )

    if isinstance(value, str):
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            errors.append(f"{location}: must contain at least {min_length} characters")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            errors.append(f"{location}: does not match the required pattern")
        if schema.get("format") == "date":
            try:
                date.fromisoformat(value)
            except ValueError:
                errors.append(f"{location}: must be an ISO date")

    return errors


def schema_errors(value: Any, schema_path: Path) -> list[str]:
    """Validate a value against one committed APH schema."""
    cache: dict[Path, dict[str, Any]] = {}
    root = _load(schema_path, cache)
    return _validate(
        value,
        root,
        location="$",
        schema_path=schema_path.resolve(),
        root_schema=root,
        cache=cache,
    )

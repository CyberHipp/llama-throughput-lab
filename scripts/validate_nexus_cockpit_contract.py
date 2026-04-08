#!/usr/bin/env python3
"""Validate NEXUS cockpit contract payloads against versioned JSON schemas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA_FILES = {
    "snapshot": "schemas/nexus_cockpit_snapshot_v1.json",
    "action": "schemas/nexus_cockpit_action_v1.json",
    "result": "schemas/nexus_cockpit_action_result_v1.json",
    "capabilities": "schemas/nexus_cockpit_capabilities_v1.json",
    "action_specs": "schemas/nexus_cockpit_action_specs_v1.json",
}


class SchemaValidationError(ValueError):
    pass


def _load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _type_ok(value, expected: str) -> bool:
    mapping = {
        "object": dict,
        "array": list,
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "null": type(None),
    }
    return isinstance(value, mapping[expected])


def _validate(schema: dict, payload, path: str = "$") -> None:
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        if not any(_type_ok(payload, t) for t in schema_type):
            raise SchemaValidationError(f"{path}: expected one of {schema_type}, got {type(payload).__name__}")
    elif isinstance(schema_type, str):
        if not _type_ok(payload, schema_type):
            raise SchemaValidationError(f"{path}: expected {schema_type}, got {type(payload).__name__}")

    if "const" in schema and payload != schema["const"]:
        raise SchemaValidationError(f"{path}: expected const {schema['const']!r}, got {payload!r}")

    if "enum" in schema and payload not in schema["enum"]:
        raise SchemaValidationError(f"{path}: expected one of {schema['enum']!r}, got {payload!r}")

    if isinstance(payload, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in payload:
                raise SchemaValidationError(f"{path}: missing required key '{key}'")

        properties = schema.get("properties", {})
        for key, value in payload.items():
            if key in properties:
                _validate(properties[key], value, f"{path}.{key}")
            elif schema.get("additionalProperties") is False:
                raise SchemaValidationError(f"{path}: unexpected key '{key}'")

    if isinstance(payload, list) and "items" in schema:
        for idx, item in enumerate(payload):
            _validate(schema["items"], item, f"{path}[{idx}]")


def validate_payload(kind: str, payload: dict) -> None:
    schema = _load_json(SCHEMA_FILES[kind])
    _validate(schema, payload)


def validate_receipt(payload: dict) -> None:
    required = ["receipt_version", "action_result_version", "action", "status", "timestamp_utc", "session_state_path", "snapshot"]
    for key in required:
        if key not in payload:
            raise SchemaValidationError(f"$.{key}: missing in receipt")
    validate_payload("snapshot", payload["snapshot"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate NEXUS cockpit artifacts")
    parser.add_argument(
        "--kind",
        choices=["snapshot", "action", "result", "receipt", "capabilities", "action_specs"],
        required=True,
    )
    parser.add_argument("--json-file", required=True)
    args = parser.parse_args(argv)

    payload = _load_json(args.json_file)
    if args.kind == "receipt":
        validate_receipt(payload)
    else:
        validate_payload(args.kind, payload)

    print(json.dumps({"status": "ok", "kind": args.kind, "json_file": args.json_file}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

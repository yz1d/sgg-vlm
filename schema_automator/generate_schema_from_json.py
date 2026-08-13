from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from schema_automator.generalizers.json_instance_generalizer import JsonDataGeneralizer
from schema_automator.utils.schemautils import write_schema

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "schema_automator" / "data" / "JSON_example.json"
DEFAULT_OUTPUT = ROOT / "schema_automator" / "schema" / "generated_from_json.yaml"
ID_KEY_PATTERN = re.compile(
    r"^(?:\d+|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})$"
)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        id_items = {
            str(key): item for key, item in value.items() if ID_KEY_PATTERN.match(str(key))
        }
        if id_items:
            normalized_rows: list[dict[str, Any]] = []
            for key, item in id_items.items():
                if isinstance(item, dict):
                    normalized_rows.append({"id": key, **_normalize_value(item)})
                else:
                    normalized_rows.append({"id": key, "value": _normalize_value(item)})
            if len(id_items) == len(value):
                return normalized_rows
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if str(key) in id_items:
                continue
            if key == "map_lanes" and isinstance(item, dict):
                normalized[key] = [
                    {"id": lane_id, **_normalize_value(lane_data)}
                    for lane_id, lane_data in item.items()
                    if isinstance(lane_data, dict)
                ]
            else:
                normalized[key] = _normalize_value(item)
        if id_items:
            normalized["entries"] = normalized_rows
        return normalized
    if isinstance(value, list):
        if all(not isinstance(item, (dict, list)) for item in value):
            return " | ".join(str(item) for item in value)
        return [_normalize_value(item) for item in value]
    return value


def _normalize_json_example(data: dict[str, Any]) -> dict[str, Any]:
    return _normalize_value(data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a LinkML schema from a JSON example using schema-automator."
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"JSON input file [default: {DEFAULT_INPUT.relative_to(ROOT)}]",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output schema file [default: {DEFAULT_OUTPUT.relative_to(ROOT)}]",
    )
    parser.add_argument(
        "-n",
        "--schema-name",
        default="SceneGraphBootstrap",
        help="Schema name",
    )
    parser.add_argument(
        "--container-class-name",
        default="SceneGraph",
        help="Name of the root class",
    )
    parser.add_argument(
        "-f",
        "--format",
        default="json",
        choices=("json", "yaml", "json.gz", "yaml.gz", "frontmatter"),
        help="Input file format",
    )
    parser.add_argument(
        "--omit-null",
        action="store_true",
        help="Ignore null values while inferring the schema",
    )
    parser.add_argument(
        "--depluralize",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Auto-depluralize class names to singular form",
    )
    parser.add_argument(
        "--inlined-map",
        action="append",
        default=[],
        metavar="SLOT.KEY",
        help="Mark a slot as an inlined dict using SLOT.KEY",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    generalizer = JsonDataGeneralizer(
        omit_null=args.omit_null,
        depluralize_class_names=args.depluralize,
    )
    if args.inlined_map:
        generalizer.inline_as_dict_slot_keys = dict(
            pair.split(".", 1) for pair in args.inlined_map
        )

    input_value: Any
    input_format = args.format
    if input_format == "json":
        with args.input.open(encoding="utf-8") as stream:
            input_value = _normalize_json_example(json.load(stream))
    else:
        input_value = str(args.input)

    schema = generalizer.convert(
        input_value,
        format=input_format,
        schema_name=args.schema_name,
        container_class_name=args.container_class_name,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_schema(schema, args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
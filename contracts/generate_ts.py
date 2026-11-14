"""Generate contracts/generated/types.ts from the Pydantic v2 models.

Run: python -m contracts.generate_ts          (write)
     python -m contracts.generate_ts --check  (fail if the file is stale)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import TypeAdapter

from .schemas import (
    CONTRACT_VERSION,
    CalendarArtifact,
    ClaimAuditRecord,
    ComparisonResult,
    EvaluationSummary,
    FirmsHotspotArtifact,
    ProvenanceManifest,
    RegionSelectorArtifact,
)

OUTPUT = Path(__file__).parent / "generated" / "types.ts"
ROOTS = [
    CalendarArtifact,
    ComparisonResult,
    ClaimAuditRecord,
    EvaluationSummary,
    FirmsHotspotArtifact,
    ProvenanceManifest,
    RegionSelectorArtifact,
]


def ts_type(node: dict) -> str:
    if "$ref" in node:
        return node["$ref"].rsplit("/", 1)[-1]
    if "const" in node:
        return json.dumps(node["const"])
    if "enum" in node:
        return " | ".join(json.dumps(v) for v in node["enum"])
    if "anyOf" in node:
        parts = list(dict.fromkeys(ts_type(n) for n in node["anyOf"]))
        return " | ".join(parts)
    kind = node.get("type")
    if kind == "string":
        return "string"
    if kind in ("integer", "number"):
        return "number"
    if kind == "boolean":
        return "boolean"
    if kind == "null":
        return "null"
    if kind == "array":
        inner = ts_type(node.get("items", {}))
        return f"Array<{inner}>" if any(c in inner for c in " |") else f"{inner}[]"
    if kind == "object":
        if node.get("properties"):
            return inline_object(node)
        return "Record<string, unknown>"
    return "unknown"


def inline_object(node: dict) -> str:
    required = set(node.get("required", []))
    fields = []
    for name, prop in node.get("properties", {}).items():
        optional = "" if name in required else "?"
        fields.append(f"{name}{optional}: {ts_type(prop)}")
    return "{ " + "; ".join(fields) + " }"


def render_definition(name: str, node: dict) -> str:
    if node.get("type") == "object" and node.get("properties"):
        required = set(node.get("required", []))
        lines = [f"export interface {name} {{"]
        for prop_name, prop in node["properties"].items():
            optional = "" if prop_name in required else "?"
            lines.append(f"  {prop_name}{optional}: {ts_type(prop)};")
        lines.append("}")
        return "\n".join(lines)
    return f"export type {name} = {ts_type(node)};"


def build() -> str:
    defs: dict[str, dict] = {}
    for model in ROOTS:
        schema = TypeAdapter(model).json_schema(mode="serialization", ref_template="#/$defs/{model}")
        for name, node in schema.get("$defs", {}).items():
            defs[name] = node
        defs[model.__name__] = {k: v for k, v in schema.items() if k != "$defs"}
    header = (
        "/**\n"
        " * THE THIRD EYE auto-generated TypeScript contract types.\n"
        f" * Contract version {CONTRACT_VERSION}. DO NOT EDIT.\n"
        " * Source: contracts/schemas/*.py via `python -m contracts.generate_ts`.\n"
        " */\n\n"
    )
    body = "\n\n".join(render_definition(n, defs[n]) for n in sorted(defs))
    return header + body + "\n"


def main() -> int:
    text = build()
    if "--check" in sys.argv:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != text:
            print("contracts/generated/types.ts is stale; run python -m contracts.generate_ts")
            return 1
        print("types.ts is current")
        return 0
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

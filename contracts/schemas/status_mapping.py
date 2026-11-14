"""Mapping from P1-A science status names to contract enums (export adapter boundary).

The mapping lives in contracts/config/p1a_status_mapping.json and is PROPOSED, not approved.
Rules:
- While the mapping is unregistered, only synthetic artifacts may use it (allow_unregistered).
- A P1-A name without an agreed target (insufficient_evidence) always raises; it is never
  folded into another state.
- Unknown names raise; nothing is coerced to a default.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

MAPPING_PATH = Path(__file__).resolve().parents[1] / "config" / "p1a_status_mapping.json"


class UnregisteredMappingError(ValueError):
    """The P1-A mapping has no recorded P1 approval, so it cannot feed a production export."""


class UnmappedStatusError(ValueError):
    """A P1-A status has no agreed contract target (or is unknown)."""


@dataclass(frozen=True)
class MappedStatuses:
    sensitivity_status: str
    applicability_status: str
    headline_direction: str
    practical_change_category: str
    inference_status: str


def load_mapping(path: Path = MAPPING_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _lookup(table: dict, name: str, dimension: str) -> str:
    if name not in table:
        raise UnmappedStatusError(f"unknown P1-A {dimension} status: {name!r}")
    target = table[name]
    if target is None:
        raise UnmappedStatusError(f"P1-A {dimension} status {name!r} has no agreed contract target (P1 decision)")
    return target


def map_p1a_statuses(
    *,
    sensitivity: str,
    applicability: str,
    headline: str,
    practical_change: str,
    inference: str = "not_established",
    applicability_passed: bool | None = None,
    allow_unregistered: bool = False,
    mapping: dict | None = None,
) -> MappedStatuses:
    """Map one P1-A result. `allow_unregistered` is for synthetic artifacts only."""
    table = mapping if mapping is not None else load_mapping()
    if not table.get("registered") and not allow_unregistered:
        raise UnregisteredMappingError("P1-A status mapping is not registered; production export refused")
    if table.get("registered") and not (table.get("decision_at") and table.get("reference")):
        raise UnregisteredMappingError("a registered mapping needs decision_at and reference")
    if applicability == "evaluated_for_conditions":
        if applicability_passed is None:
            raise UnmappedStatusError("evaluated_for_conditions needs applicability_passed; evaluated is not passed")
        key = "evaluated_for_conditions+passed" if applicability_passed else "evaluated_for_conditions+not_passed"
    else:
        if applicability_passed is not None:
            raise UnmappedStatusError("applicability_passed only qualifies evaluated_for_conditions")
        key = applicability
    return MappedStatuses(
        sensitivity_status=_lookup(table["sensitivity"], sensitivity, "sensitivity"),
        applicability_status=_lookup(table["applicability"], key, "applicability"),
        headline_direction=_lookup(table["headline"], headline, "headline"),
        practical_change_category=_lookup(table["practical_change"], practical_change, "practical change"),
        inference_status=_lookup(table["inference"], inference, "inference"),
    )

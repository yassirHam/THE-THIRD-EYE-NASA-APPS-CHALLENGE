"""Test shims for contract 1.4.0 coverage fields (P2 r9).

Many older tests mutate a period's dates, file days or partial flags and then check one rule.
Contract 1.4.0 also requires coverage_state / coverage_reasons to match those fields, so a
mutated record would fail on stale coverage fields instead of on the rule under test. These
shims recompute the coverage fields with the fixture builder first, so each older test keeps
checking its own rule.

Coverage validation itself is tested WITHOUT these shims in test_coverage_reasons.py, and the
committed fixtures are validated raw there as well.
"""

from __future__ import annotations

import json

from contracts import build_fixtures as bf
from contracts.schemas.calendar import CalendarArtifact, WeeklyCalendarSeries


def _try(fill, data):
    try:
        fill(data)
    except (KeyError, TypeError, ValueError, AttributeError):
        pass  # malformed on purpose: let the schema report it
    return data


class CalendarWithDerivedCoverage:
    @staticmethod
    def model_validate_json(text: str):
        data = _try(bf.fill_coverage, json.loads(text))
        return CalendarArtifact.model_validate_json(json.dumps(data))


class WeeklySeriesWithDerivedCoverage:
    @staticmethod
    def model_validate_json(text: str):
        data = json.loads(text)
        for rec in data.get("records", []):
            _try(bf.fill_record_coverage, rec)
        return WeeklyCalendarSeries.model_validate_json(json.dumps(data))

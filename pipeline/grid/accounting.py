"""Reference D/O block accounting and pooled rates.

Pure-Python (numpy) reference for ``daily_stack()`` / ``check_year()`` /
``rates()`` in notebooks/AFTERIMAGE_EE_V2.ipynb, governed by
docs/DECISIONS.md record 2026-11-14-05, docs/DATA_CARD.md sections 6-7 and
plan Sections 4B / 5A.

Accounting rules:
- A pixel belongs to the block whose ADM1_CODE is painted at its centre on
  the native 1 km grid (unweighted count, no fractional weighting).
- File absent for a sensor -> that sensor's D, O, D_nh are None (never 0).
  Common-support columns need both files; otherwise they are None.
- File present with no usable pixel -> O = 0 (a valid processed value).
- R = 1000 * sum(D) / sum(O): counts are summed over every required unit
  (blocks and/or days) BEFORE dividing; rates are never averaged.
- sum(O) == 0 -> R unavailable (status "zero_support"), never 0.
- Any required unit missing -> R unavailable (status "incomplete"). Remaining
  units are not silently pooled or reweighted (plan 4B/5A: a partially
  extracted footprint is unavailable for a whole-area conclusion).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Sequence

import numpy as np

from pipeline.masks.firemask import (
    common_support,
    fire_mask,
    fire_nh_mask,
    usable_mask,
)

__all__ = [
    "COUNT_COLUMNS",
    "AQUA_COLUMNS",
    "VIIRS_COLUMNS",
    "COMMON_COLUMNS",
    "AQUA_PRODUCT",
    "VIIRS_PRODUCT",
    "OUTSIDE_DOMAIN",
    "block_day_counts",
    "check_row",
    "sum_column",
    "RateResult",
    "pooled_rate",
    "pooled_rate_from_rows",
]

AQUA_PRODUCT = "MYD14A1.061"
VIIRS_PRODUCT = "VNP14A1.002"
OUTSIDE_DOMAIN = -1  # block-id value for pixels whose centre is in no block

# Column names match docs/DATA_CARD.md section 6 exactly.
AQUA_COLUMNS = ("D_aqua", "O_aqua", "D_aqua_nh")
VIIRS_COLUMNS = ("D_viirs", "O_viirs", "D_viirs_nh")
COMMON_COLUMNS = ("O_common", "D_aqua_common", "D_viirs_common")
COUNT_COLUMNS = (
    "D_aqua", "O_aqua", "D_viirs", "O_viirs",
    "O_common", "D_aqua_common", "D_viirs_common",
    "D_aqua_nh", "D_viirs_nh",
)

STATUS_AVAILABLE = "available"
STATUS_ZERO_SUPPORT = "zero_support"
STATUS_INCOMPLETE = "incomplete"
STATUS_NO_DATA = "no_data"


# --------------------------------------------------------------------------- #
# pixels -> one row per block and UTC day
# --------------------------------------------------------------------------- #
def _sensor_masks(day, product):
    """day is None (file absent) or a (FireMask, QA) pair."""
    if day is None:
        return None
    fm, qa = day
    return (
        fire_mask(fm, qa, product),
        fire_nh_mask(fm, qa, product),
        usable_mask(fm, qa, product),
    )


def block_day_counts(
    block_ids,
    blocks: Iterable[int],
    aqua: Optional[tuple] = None,
    viirs: Optional[tuple] = None,
) -> dict:
    """Count D/O per block for one UTC day on an aligned grid.

    block_ids : integer array, ADM1_CODE at each pixel centre, or
                OUTSIDE_DOMAIN (-1) for pixels in no block.
    blocks    : the registered block codes; every one gets a row, even if
                it has no pixel on this grid (counts then 0 when present).
    aqua, viirs : (FireMask, QA) arrays for that sensor's daily file, or
                None when the file is absent.

    Returns {ADM1_CODE: row} with the DATA_CARD columns plus
    aqua_file_present / viirs_file_present.
    """
    ids = np.asarray(block_ids)
    if ids.dtype.kind not in "ui":
        raise TypeError("block_ids must be an integer array")
    blocks = list(blocks)
    if len(set(blocks)) != len(blocks):
        raise ValueError("duplicate block codes")
    if OUTSIDE_DOMAIN in blocks:
        raise ValueError(f"{OUTSIDE_DOMAIN} is reserved for outside-domain pixels")
    stray = set(np.unique(ids).tolist()) - set(blocks) - {OUTSIDE_DOMAIN}
    if stray:
        raise ValueError(f"block_ids contain unregistered codes {sorted(stray)}")

    a = _sensor_masks(aqua, AQUA_PRODUCT)
    v = _sensor_masks(viirs, VIIRS_PRODUCT)
    for m in (a, v):
        if m is not None and m[0].shape != ids.shape:
            raise ValueError("sensor arrays and block_ids must share one aligned grid")
    common = common_support(a[2], v[2]) if a is not None and v is not None else None

    def n(mask, sel):
        return int(np.count_nonzero(mask & sel))

    rows = {}
    for code in blocks:
        sel = ids == code
        row = {"aqua_file_present": int(a is not None),
               "viirs_file_present": int(v is not None)}
        if a is None:
            row.update(dict.fromkeys(AQUA_COLUMNS))
        else:
            row.update(D_aqua=n(a[0], sel), O_aqua=n(a[2], sel), D_aqua_nh=n(a[1], sel))
        if v is None:
            row.update(dict.fromkeys(VIIRS_COLUMNS))
        else:
            row.update(D_viirs=n(v[0], sel), O_viirs=n(v[2], sel), D_viirs_nh=n(v[1], sel))
        if common is None:
            row.update(dict.fromkeys(COMMON_COLUMNS))
        else:
            row.update(O_common=n(common, sel),
                       D_aqua_common=n(a[0] & common, sel),
                       D_viirs_common=n(v[0] & common, sel))
        rows[code] = {k: row[k] for k in ("aqua_file_present", "viirs_file_present") + COUNT_COLUMNS}
    return rows


# --------------------------------------------------------------------------- #
# row invariants (mirror of check_year, per row)
# --------------------------------------------------------------------------- #
_LE_PAIRS = (
    ("D_aqua_nh", "D_aqua"), ("D_aqua", "O_aqua"),
    ("D_viirs_nh", "D_viirs"), ("D_viirs", "O_viirs"),
    ("D_aqua_common", "O_common"), ("D_viirs_common", "O_common"),
    ("D_aqua_common", "D_aqua"), ("D_viirs_common", "D_viirs"),
    ("O_common", "O_aqua"), ("O_common", "O_viirs"),
)


def check_row(row: Mapping) -> list:
    """Return a list of contract violations for one block-day row (empty = OK)."""
    issues = []
    a_ok, v_ok = row.get("aqua_file_present"), row.get("viirs_file_present")
    for flag in ("aqua_file_present", "viirs_file_present"):
        if row.get(flag) not in (0, 1):
            issues.append(f"{flag} must be 0 or 1")
    expect_null = {c: a_ok != 1 for c in AQUA_COLUMNS}
    expect_null.update({c: v_ok != 1 for c in VIIRS_COLUMNS})
    expect_null.update({c: not (a_ok == 1 and v_ok == 1) for c in COMMON_COLUMNS})
    for col, null in expect_null.items():
        val = row.get(col)
        if null and val is not None:
            issues.append(f"{col} must be null when its file is absent (got {val!r})")
        elif not null:
            if val is None:
                issues.append(f"{col} is null although its file is present")
            elif val < 0:
                issues.append(f"{col} is negative")
    for small, big in _LE_PAIRS:
        s, b = row.get(small), row.get(big)
        if s is not None and b is not None and s > b:
            issues.append(f"{small} > {big}")
    return issues


# --------------------------------------------------------------------------- #
# sums and pooled rates
# --------------------------------------------------------------------------- #
def sum_column(rows: Iterable[Mapping], column: str) -> Optional[int]:
    """Exact sum over required units; any null unit makes the total null."""
    total = 0
    for r in rows:
        v = r[column]
        if v is None:
            return None
        total += v
    return total


@dataclass(frozen=True)
class RateResult:
    """Pooled rate with the status that explains a null value."""

    value: Optional[float]      # 1000 * D_sum / O_sum, or None
    status: str                 # available | zero_support | incomplete | no_data
    d_sum: Optional[int]        # None unless every unit is present
    o_sum: Optional[int]
    n_units: int
    n_missing: int


def pooled_rate(d: Sequence[Optional[int]], o: Sequence[Optional[int]]) -> RateResult:
    """R = 1000 * sum(D) / sum(O) over all required units (blocks/days).

    Each unit is a (D, O) pair; None means unavailable (file absent). D and O
    of one unit must be null together and satisfy 0 <= D <= O.
    """
    d, o = list(d), list(o)
    if len(d) != len(o):
        raise ValueError("D and O must have one value per unit")
    if not d:
        return RateResult(None, STATUS_NO_DATA, None, None, 0, 0)
    n_missing = 0
    for i, (di, oi) in enumerate(zip(d, o)):
        if (di is None) != (oi is None):
            raise ValueError(f"unit {i}: D and O must be null together")
        if di is None:
            n_missing += 1
            continue
        if isinstance(di, float) and np.isnan(di) or isinstance(oi, float) and np.isnan(oi):
            raise ValueError(f"unit {i}: use None, not NaN, for unavailable counts")
        if di < 0 or oi < 0:
            raise ValueError(f"unit {i}: counts must be non-negative")
        if di > oi:
            raise ValueError(f"unit {i}: D ({di}) > O ({oi}); fire pixels are a subset of usable")
    if n_missing:
        return RateResult(None, STATUS_INCOMPLETE, None, None, len(d), n_missing)
    d_sum, o_sum = sum(d), sum(o)
    if o_sum == 0:
        return RateResult(None, STATUS_ZERO_SUPPORT, d_sum, o_sum, len(d), 0)
    return RateResult(1000.0 * d_sum / o_sum, STATUS_AVAILABLE, d_sum, o_sum, len(d), 0)


def pooled_rate_from_rows(rows: Iterable[Mapping], d_col: str, o_col: str) -> RateResult:
    """pooled_rate over block-day rows, e.g. ('D_aqua', 'O_aqua') or
    ('D_viirs_common', 'O_common')."""
    rows = list(rows)
    return pooled_rate([r[d_col] for r in rows], [r[o_col] for r in rows])

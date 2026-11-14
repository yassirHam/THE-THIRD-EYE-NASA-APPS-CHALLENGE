"""Reference FireMask / QA decoders for the daily 1 km fire grids.

Pure-Python (numpy) reference for the masks applied in
notebooks/AFTERIMAGE_EE_V2.ipynb (``masks()``), governed by
docs/DECISIONS.md record 2026-11-14-05 and plan Section 4A.

Rules (frozen, Nov 14):
- land    : QA bits 0-1 == 2 (binary 10). Water (00), coast (01) and the
            unused state (11) are NOT land. Coast is excluded
            (notebook INCLUDE_COAST = False).
- fire    : FireMask in {7, 8, 9} on land                -> D
- fire_nh : FireMask in {8, 9} on land                   -> D_nh
- usable  : (FireMask == 5 or fire) on land              -> O
            cloud (4), unknown/unclassified (6), water (3) and
            not-processed (0-2) are excluded.
- common  : usable in BOTH sensors on the same cell and UTC day.

Plan 4A: "Never share a decoder merely because class numbers look similar."
Each product therefore has its own registered decoder, even though the
class numbers used here coincide. Only the two products in scope are
registered; Terra MOD14A1 and NOAA-20 VJ114A1 are deliberately absent
and raise instead of silently reusing a decoder.

Values outside the documented FireMask range (0-9) are rejected, not
mapped to "not usable": unknown/reserved classes must be captured
explicitly (plan 4A).
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

import numpy as np

__all__ = [
    "ProductDecoder",
    "DECODERS",
    "get_decoder",
    "land_mask",
    "fire_mask",
    "fire_nh_mask",
    "usable_mask",
    "common_support",
    "class_audit",
]

QA_LANDWATER_BITS = 0b11  # QA bits 0-1
LANDWATER_STATES = MappingProxyType({0: "water", 1: "coast", 2: "land", 3: "unused"})


@dataclass(frozen=True)
class ProductDecoder:
    """Registered class semantics for one product/collection version."""

    product_id: str
    class_names: Mapping[int, str]
    fire_classes: frozenset
    fire_nh_classes: frozenset
    clear_land_class: int
    land_state: int = 2  # QA bits 0-1 value that counts as land

    def __post_init__(self) -> None:
        if not self.fire_nh_classes <= self.fire_classes:
            raise ValueError("fire_nh classes must be a subset of fire classes")
        if self.clear_land_class in self.fire_classes:
            raise ValueError("clear-land class cannot be a fire class")
        known = set(self.class_names)
        if not (self.fire_classes | {self.clear_land_class}) <= known:
            raise ValueError("decoder references undocumented classes")

    @property
    def max_class(self) -> int:
        return max(self.class_names)


# Class labels follow the Earth Engine catalog pages for the two collections
# (P2 human verifies them against the exact LP DAAC user guides; plan 4A).
_MYD14A1_061 = ProductDecoder(
    product_id="MYD14A1.061",
    class_names=MappingProxyType({
        0: "not processed (missing input data)",
        1: "not processed (obsolete; not used since Collection 1)",
        2: "not processed (other reason)",
        3: "non-fire water pixel",
        4: "cloud (land or water)",
        5: "non-fire land pixel",
        6: "unknown (land or water)",
        7: "fire (low confidence, land or water)",
        8: "fire (nominal confidence, land or water)",
        9: "fire (high confidence, land or water)",
    }),
    fire_classes=frozenset({7, 8, 9}),
    fire_nh_classes=frozenset({8, 9}),
    clear_land_class=5,
)

_VNP14A1_002 = ProductDecoder(
    product_id="VNP14A1.002",
    class_names=MappingProxyType({
        0: "not processed (non-zero QF)",
        1: "not processed (bowtie deletion)",
        2: "not processed (sun glint)",
        3: "non-fire water pixel",
        4: "cloud (land or water)",
        5: "non-fire land pixel",
        6: "unclassified (land or water)",
        7: "fire (low confidence, land or water)",
        8: "fire (nominal confidence, land or water)",
        9: "fire (high confidence, land or water)",
    }),
    fire_classes=frozenset({7, 8, 9}),
    fire_nh_classes=frozenset({8, 9}),
    clear_land_class=5,
)

DECODERS: Mapping[str, ProductDecoder] = MappingProxyType({
    _MYD14A1_061.product_id: _MYD14A1_061,
    _VNP14A1_002.product_id: _VNP14A1_002,
})


def get_decoder(product_id: str) -> ProductDecoder:
    """Return the registered decoder; unregistered products raise KeyError."""
    try:
        return DECODERS[product_id]
    except KeyError:
        raise KeyError(
            f"no registered decoder for {product_id!r}; in scope: {sorted(DECODERS)}. "
            "A new product needs its own verified decoder and fixtures (plan 4A)."
        ) from None


# --------------------------------------------------------------------------- #
# validation helpers
# --------------------------------------------------------------------------- #
def _as_int_array(a, name: str) -> np.ndarray:
    arr = np.asarray(a)
    if arr.dtype.kind not in "ui":
        raise TypeError(f"{name} must be an integer array, got dtype {arr.dtype}")
    return arr


def _check_firemask(fm, decoder: ProductDecoder) -> np.ndarray:
    fm = _as_int_array(fm, "FireMask")
    if fm.size and (fm.min() < 0 or fm.max() > decoder.max_class):
        bad = np.unique(fm[(fm < 0) | (fm > decoder.max_class)])
        raise ValueError(
            f"{decoder.product_id}: FireMask values {bad.tolist()} are outside the "
            f"documented classes 0-{decoder.max_class}"
        )
    return fm


def _check_qa(qa) -> np.ndarray:
    qa = _as_int_array(qa, "QA")
    if qa.size and qa.min() < 0:
        raise ValueError("QA must be non-negative (bit field)")
    return qa


def _check_shapes(*arrays: np.ndarray) -> None:
    shapes = {a.shape for a in arrays}
    if len(shapes) != 1:
        raise ValueError(f"arrays must share one aligned grid shape, got {sorted(shapes)}")


def _resolve(decoder) -> ProductDecoder:
    return get_decoder(decoder) if isinstance(decoder, str) else decoder


# --------------------------------------------------------------------------- #
# masks
# --------------------------------------------------------------------------- #
def land_mask(qa, decoder="MYD14A1.061") -> np.ndarray:
    """True where QA bits 0-1 == land (2). Higher QA bits are ignored."""
    decoder = _resolve(decoder)
    qa = _check_qa(qa)
    return (qa & QA_LANDWATER_BITS) == decoder.land_state


def _prepared(fm, qa, decoder):
    decoder = _resolve(decoder)
    fm = _check_firemask(fm, decoder)
    qa = _check_qa(qa)
    _check_shapes(fm, qa)
    return fm, land_mask(qa, decoder), decoder


def fire_mask(fm, qa, decoder="MYD14A1.061") -> np.ndarray:
    """D pixels: FireMask in fire classes (7-9) on land."""
    fm, land, dec = _prepared(fm, qa, decoder)
    return np.isin(fm, sorted(dec.fire_classes)) & land


def fire_nh_mask(fm, qa, decoder="MYD14A1.061") -> np.ndarray:
    """D_nh pixels: FireMask in nominal/high classes (8-9) on land."""
    fm, land, dec = _prepared(fm, qa, decoder)
    return np.isin(fm, sorted(dec.fire_nh_classes)) & land


def usable_mask(fm, qa, decoder="MYD14A1.061") -> np.ndarray:
    """O pixels: (clear non-fire land or fire) on land."""
    fm, land, dec = _prepared(fm, qa, decoder)
    observed = (fm == dec.clear_land_class) | np.isin(fm, sorted(dec.fire_classes))
    return observed & land


def common_support(usable_a, usable_b) -> np.ndarray:
    """Cells usable in both sensors on the same aligned grid and UTC day."""
    a, b = np.asarray(usable_a), np.asarray(usable_b)
    if a.dtype != bool or b.dtype != bool:
        raise TypeError("common_support expects boolean usable masks")
    _check_shapes(a, b)
    return a & b


def class_audit(fm, qa, decoder="MYD14A1.061") -> dict:
    """Pixel counts per (land/water state, FireMask class) for opportunity QA.

    Every pixel lands in exactly one cell of the table, so the counts sum to
    the input size; excluded pixels stay visible instead of disappearing.
    """
    decoder = _resolve(decoder)
    fm = _check_firemask(fm, decoder)
    qa = _check_qa(qa)
    _check_shapes(fm, qa)
    state = qa & QA_LANDWATER_BITS
    out = {}
    for s, s_name in LANDWATER_STATES.items():
        for c in decoder.class_names:
            out[(s_name, c)] = int(np.count_nonzero((state == s) & (fm == c)))
    return out

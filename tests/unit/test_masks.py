"""P2-A mask reference tests (synthetic fixtures only)."""
import numpy as np
import pytest

from pipeline.masks.firemask import (
    DECODERS,
    class_audit,
    common_support,
    fire_mask,
    fire_nh_mask,
    get_decoder,
    land_mask,
    usable_mask,
)
from tests.unit.fixtures import COAST, EXPECTED_ON_LAND, LAND, UNUSED, WATER

PRODUCTS = ["MYD14A1.061", "VNP14A1.002"]


def _one(fm, qa):
    return np.array([fm], dtype=np.uint8), np.array([qa], dtype=np.uint8)


@pytest.mark.parametrize("product", PRODUCTS)
@pytest.mark.parametrize("cls", range(10))
def test_each_firemask_class_on_land(product, cls):
    fm, qa = _one(cls, LAND)
    expected = EXPECTED_ON_LAND[cls]
    got = (fire_mask(fm, qa, product)[0], fire_nh_mask(fm, qa, product)[0],
           usable_mask(fm, qa, product)[0])
    assert got == expected


@pytest.mark.parametrize("product", PRODUCTS)
@pytest.mark.parametrize("state", [WATER, COAST, UNUSED])
@pytest.mark.parametrize("cls", range(10))
def test_non_land_pixels_never_count(product, state, cls):
    """Coast and water pixels are excluded from D, D_nh and O, even fire classes."""
    fm, qa = _one(cls, state)
    assert not fire_mask(fm, qa, product)[0]
    assert not fire_nh_mask(fm, qa, product)[0]
    assert not usable_mask(fm, qa, product)[0]


@pytest.mark.parametrize("qa, is_land", [
    (0b00000010, True),
    (0b11111110, True),    # higher bits set, bits 0-1 == 10
    (0b00000110, True),
    (0b00000101, False),   # bits 0-1 == 01 coast
    (0b11111100, False),   # bits 0-1 == 00 water
    (0b00000011, False),   # bits 0-1 == 11 unused
])
def test_land_uses_only_qa_bits_0_1(qa, is_land):
    assert land_mask(np.array([qa], dtype=np.uint8))[0] == is_land


def test_low_confidence_is_fire_but_not_nh_and_stays_in_O():
    fm, qa = _one(7, LAND)
    assert fire_mask(fm, qa)[0] and not fire_nh_mask(fm, qa)[0] and usable_mask(fm, qa)[0]


@pytest.mark.parametrize("product", PRODUCTS)
def test_mask_invariants_on_every_combination(product):
    fm = np.repeat(np.arange(10, dtype=np.uint8), 4)
    qa = np.tile(np.arange(4, dtype=np.uint8), 10)
    f, nh, u = fire_mask(fm, qa, product), fire_nh_mask(fm, qa, product), usable_mask(fm, qa, product)
    assert np.all(nh <= f) and np.all(f <= u)
    assert np.all(u <= land_mask(qa, product))
    assert f.sum() == 3 and nh.sum() == 2 and u.sum() == 4  # land only: classes 7-9 / 8-9 / 5,7-9


def test_decoders_are_registered_separately():
    assert set(DECODERS) == set(PRODUCTS)
    assert DECODERS["MYD14A1.061"] is not DECODERS["VNP14A1.002"]
    assert "bowtie" in DECODERS["VNP14A1.002"].class_names[1]


@pytest.mark.parametrize("product", ["MOD14A1.061", "VJ114A1.002", "VNP14A1.001"])
def test_unregistered_products_are_refused(product):
    with pytest.raises(KeyError):
        get_decoder(product)
    with pytest.raises(KeyError):
        usable_mask(*_one(5, LAND), product)


@pytest.mark.parametrize("bad", [10, 255])
def test_undocumented_classes_raise(bad):
    with pytest.raises(ValueError, match="outside the documented classes"):
        usable_mask(*_one(bad, LAND))


def test_negative_firemask_raises():
    with pytest.raises(ValueError):
        usable_mask(np.array([-1], dtype=np.int8), np.array([LAND], dtype=np.uint8))


def test_float_inputs_rejected_no_silent_nan():
    with pytest.raises(TypeError):
        usable_mask(np.array([5.0]), np.array([LAND], dtype=np.uint8))
    with pytest.raises(TypeError):
        land_mask(np.array([np.nan]))


def test_shape_mismatch_raises():
    with pytest.raises(ValueError, match="aligned grid"):
        usable_mask(np.zeros((2, 2), np.uint8), np.zeros((2, 3), np.uint8))


def test_common_support_is_logical_and():
    a = np.array([True, True, False, False])
    b = np.array([True, False, True, False])
    assert common_support(a, b).tolist() == [True, False, False, False]
    with pytest.raises(TypeError):
        common_support(a.astype(np.uint8), b)
    with pytest.raises(ValueError):
        common_support(a, b[:3])


def test_empty_grid_gives_empty_masks():
    fm = np.zeros((0,), np.uint8)
    assert usable_mask(fm, fm).sum() == 0


def test_class_audit_keeps_every_pixel_visible():
    fm = np.array([9, 9, 5, 4, 3], np.uint8)
    qa = np.array([COAST, LAND, LAND, LAND, WATER], np.uint8)
    audit = class_audit(fm, qa)
    assert sum(audit.values()) == fm.size
    assert audit[("coast", 9)] == 1      # coastal fire is recorded, not lost
    assert audit[("land", 9)] == 1
    assert audit[("water", 3)] == 1

"""Clearly SYNTHETIC pixel fixtures for P2-A mask/accounting tests.

Hand-built arrays only; no real export, no Earth Engine, no 2020-2021 data.
QA values below set only the land/water bits (0-1) unless a test says otherwise.
"""
import numpy as np

WATER, COAST, LAND, UNUSED = 0, 1, 2, 3

# Every FireMask class 0-9 with the expected result ON LAND.
#            class: (fire, fire_nh, usable)
EXPECTED_ON_LAND = {
    0: (False, False, False),  # not processed
    1: (False, False, False),  # not processed
    2: (False, False, False),  # not processed
    3: (False, False, False),  # water class
    4: (False, False, False),  # cloud
    5: (False, False, True),   # clear non-fire land
    6: (False, False, False),  # unknown / unclassified
    7: (True, False, True),    # fire, low confidence
    8: (True, True, True),     # fire, nominal
    9: (True, True, True),     # fire, high
}

BLOCK_A, BLOCK_B = 101, 202
OUT = -1

# 3 x 4 aligned grid. Column 3 is outside the domain.
BLOCK_IDS = np.array([
    [BLOCK_A, BLOCK_A, BLOCK_B, OUT],
    [BLOCK_A, BLOCK_A, BLOCK_B, OUT],
    [BLOCK_A, BLOCK_B, BLOCK_B, OUT],
], dtype=np.int32)

AQUA_FM = np.array([
    [9, 5, 8, 9],   # A fire-high, A clear, B fire-nominal, OUT fire (ignored)
    [7, 4, 5, 5],   # A fire-low,  A cloud, B clear,       OUT clear
    [8, 6, 9, 5],   # A fire on COAST (excluded), B unknown, B fire on WATER (excluded)
], dtype=np.uint8)
AQUA_QA = np.array([
    [LAND, LAND, LAND, LAND],
    [LAND, LAND, LAND, LAND],
    [COAST, LAND, WATER, LAND],
], dtype=np.uint8)

VIIRS_FM = np.array([
    [8, 4, 5, 9],   # A fire-nominal, A cloud, B clear
    [5, 5, 7, 5],   # A clear, A clear, B fire-low
    [5, 5, 3, 5],   # A clear on COAST (excluded), B clear, B water
], dtype=np.uint8)
VIIRS_QA = AQUA_QA.copy()

# Hand-computed expectations for the grid above.
#   Aqua  A: D = {9,7} = 2, D_nh = {9} = 1, O = {9,5,7} = 3
#   Aqua  B: D = {8} = 1,   D_nh = 1,       O = {8,5} = 2
#   VIIRS A: D = {8} = 1,   D_nh = 1,       O = {8,5,5} = 3
#   VIIRS B: D = {7} = 1,   D_nh = 0,       O = {5,7,5} = 3
#   common A: (0,0) and (1,0) -> 2 ; D_aqua_common = 2 (9,7), D_viirs_common = 1 (8)
#   common B: (0,2) and (1,2) -> 2 ; D_aqua_common = 1 (8),   D_viirs_common = 1 (7)
EXPECTED_BOTH = {
    BLOCK_A: dict(D_aqua=2, O_aqua=3, D_aqua_nh=1, D_viirs=1, O_viirs=3, D_viirs_nh=1,
                  O_common=2, D_aqua_common=2, D_viirs_common=1),
    BLOCK_B: dict(D_aqua=1, O_aqua=2, D_aqua_nh=1, D_viirs=1, O_viirs=3, D_viirs_nh=0,
                  O_common=2, D_aqua_common=1, D_viirs_common=1),
}


def all_cloud(shape=(3, 4)):
    """A processed day with no usable pixel (FireMask 4 everywhere, all land)."""
    return (np.full(shape, 4, dtype=np.uint8), np.full(shape, LAND, dtype=np.uint8))

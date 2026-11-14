"""
Shared pytest configuration for tests/science/.

Registers custom markers so --strict-markers does not reject them.
No fixtures that touch science/ paths are defined here.
"""
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow (deselect with -m 'not slow')",
    )

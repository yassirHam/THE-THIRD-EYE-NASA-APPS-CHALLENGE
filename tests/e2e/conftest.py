"""Shared fixtures for the P5 end-to-end suite. Public synthetic fixtures only."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


def _load_local(name: str):
    """Import a sibling module by path, independent of how pytest set sys.path."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contract_source = _load_local("contract_source")
replay_bundle = _load_local("replay_bundle")


@pytest.fixture(scope="session")
def contracts(tmp_path_factory) -> "contract_source.ContractSource":
    src = contract_source.resolve(tmp_path_factory.mktemp("contracts"))
    version = contract_source.declared_version(src.root)
    assert version == contract_source.EXPECTED_CONTRACT_VERSION, (
        f"{src.description} declares contract {version!r}, expected {contract_source.EXPECTED_CONTRACT_VERSION}"
    )
    return src


@pytest.fixture(scope="session")
def fixtures(contracts) -> dict[str, dict]:
    return {
        p.stem: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(contracts.fixtures.glob("*.json"))
    }


@pytest.fixture(scope="session")
def replay():
    return replay_bundle

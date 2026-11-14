"""Locate the contract 1.5.0 package that the parity suite verifies.

P5 lane B may only edit tests/e2e/**, so it never copies P4's contracts into this
branch. Resolution order:

1. ``$env:E2E_CONTRACTS_DIR``: a directory that contains ``contracts/``.
2. This repository's own ``contracts/`` if it declares contract 1.5.0.
3. A read-only ``git archive`` of ``$env:E2E_CONTRACT_REF`` (default: the pinned
   P4 commit below) extracted to a temporary directory.

Once P4's contract lands on this branch, step 2 applies automatically.
"""

from __future__ import annotations

import os
import re
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_CONTRACT_VERSION = "1.5.0"
# origin/task/P4-B-001 edf9d65 "feat(contracts): 1.5.0 replayable manifest partitions":
# contract 1.4.0 REVIEW CHECKPOINT (P4-B Round 10). Not yet approved by P1/P2 or verified by P5;
# repin to the approved SHA before any exact-SHA verdict.
PINNED_CONTRACT_COMMIT = "edf9d65255377320b0a544e69f64db897e2960bd"


@dataclass(frozen=True)
class ContractSource:
    root: Path  # directory that contains contracts/
    description: str

    @property
    def fixtures(self) -> Path:
        return self.root / "contracts" / "fixtures"

    @property
    def types_ts(self) -> Path:
        return self.root / "contracts" / "generated" / "types.ts"


def declared_version(root: Path) -> str | None:
    common = root / "contracts" / "schemas" / "common.py"
    if not common.is_file():
        return None
    m = re.search(r'^CONTRACT_VERSION\s*=\s*"([^"]+)"', common.read_text(encoding="utf-8"), re.MULTILINE)
    return m.group(1) if m else None


def _extract_git_ref(ref: str, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / "contracts.tar"
    subprocess.run(
        ["git", "-C", str(REPO_ROOT), "archive", "-o", str(archive), ref, "contracts"],
        check=True, capture_output=True, timeout=60,
    )
    with tarfile.open(archive) as tar:
        tar.extractall(dest, filter="data")
    archive.unlink()
    return dest


def resolve(tmp_dir: Path) -> ContractSource:
    override = os.environ.get("E2E_CONTRACTS_DIR")
    if override:
        root = Path(override).resolve()
        return ContractSource(root, f"E2E_CONTRACTS_DIR={root}")
    if declared_version(REPO_ROOT) == EXPECTED_CONTRACT_VERSION:
        return ContractSource(REPO_ROOT, "repository contracts/")
    ref = os.environ.get("E2E_CONTRACT_REF", PINNED_CONTRACT_COMMIT)
    try:
        root = _extract_git_ref(ref, tmp_dir / "contract_src")
    except (OSError, subprocess.SubprocessError, tarfile.TarError) as exc:
        raise RuntimeError(
            f"contract {EXPECTED_CONTRACT_VERSION} not found locally and git ref {ref!r} is unreadable: {exc}. "
            "Fetch P4's branch or set E2E_CONTRACTS_DIR."
        ) from exc
    return ContractSource(root, f"git archive {ref}")

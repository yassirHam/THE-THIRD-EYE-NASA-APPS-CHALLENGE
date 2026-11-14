"""Combined pre-integration checks (local or CI). Exits non-zero on the first failure.

    python CI/check_all.py

Runs: contract tests, generated-TypeScript currency, TypeScript typecheck (if npx/tsc is
available), artifact pipeline tests, deploy tests, then builds the skeleton site into a
temporary directory and runs the smoke check. Nothing is deployed or published.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    py = sys.executable
    run([py, "-m", "pytest", "contracts", "-q", "-p", "no:cacheprovider"])
    run([py, "-m", "contracts.generate_ts", "--check"])
    npx = shutil.which("npx")
    has_tsc = npx is not None and subprocess.run(
        [npx, "--no-install", "tsc", "--version"], cwd=ROOT, capture_output=True).returncode == 0
    if has_tsc:
        run([npx, "--no-install", "tsc", "-p", "contracts/tsconfig.json", "--noEmit"])
    else:
        # Reported, not hidden: install the pinned TypeScript (5.9.3 in P4-B checks) to run it.
        print("SKIPPED: TypeScript typecheck (no local tsc; run `npm i --no-save typescript@5.9.3`)")
    run([py, "-m", "pytest", "artifact_pipeline", "deploy", "-q", "-p", "no:cacheprovider"])
    with tempfile.TemporaryDirectory() as tmp:
        site = Path(tmp) / "site"
        run([py, "-m", "deploy.build_site", "--out", str(site)])
        run([py, "-m", "deploy.smoke", "--site", str(site)])
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"FAILED: {' '.join(map(str, exc.cmd))} (exit {exc.returncode})", file=sys.stderr)
        raise SystemExit(1)

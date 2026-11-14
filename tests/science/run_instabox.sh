#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== THE THIRD EYE - P1-C Science Tests ==="
echo "Repo root : $REPO_ROOT"
echo "Python    : $(python3 --version)"
echo "pytest    : $(python3 -m pytest --version)"
echo

cd "$REPO_ROOT"

python3 -m pytest tests/science/ \
    -v \
    --tb=short \
    --strict-markers \
    -q \
    2>&1 | tee /tmp/p1c_test_results.txt

EXIT_CODE=${PIPESTATUS[0]}

echo
if [ "$EXIT_CODE" -eq 0 ]; then
    echo "✓ ALL TESTS PASSED (exit 0)"
else
    echo "✗ TESTS FAILED (exit $EXIT_CODE)"
fi

exit "$EXIT_CODE"

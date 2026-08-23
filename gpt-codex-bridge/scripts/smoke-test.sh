#!/usr/bin/env bash

set -euo pipefail

ROOT=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m compileall -q bridge adapters tests

while IFS= read -r script; do
    bash -n "$script"
done < <(find bin scripts -type f -perm -u+x -print | sort)

git diff --check
printf '%s\n' 'SMOKE_TEST=PASS'

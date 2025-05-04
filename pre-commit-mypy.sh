#!/usr/bin/env bash
FILES="$@"
if [[ -z "$FILES" ]]; then
  echo "No files to check."
  exit 0
fi
OUT=$(mypy --python-executable .venv/bin/python $FILES 2>&1)
STATUS=$?

if [[ $STATUS -ne 0 ]]; then
  echo "$OUT"
  exit $STATUS
fi
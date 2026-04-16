"""Keep a stable snapshot while a JSON response is still streaming."""

from __future__ import annotations

import json
import sys

from json_repair import repair_json

CHUNKS = [
    '{"items":[{"id":1,"name":"Ada"},',
    '{"id":2,"name":"Grace"},',
    '{"id":3,"name":"Linus"',
    '],"complete":tr',
    "ue}",
]


def main() -> None:
    partial = ""
    snapshots = []

    for chunk in CHUNKS:
        partial += chunk
        snapshots.append(repair_json(partial, return_objects=True, stream_stable=True))

    sys.stdout.write(json.dumps(snapshots, indent=2) + "\n")


if __name__ == "__main__":
    main()

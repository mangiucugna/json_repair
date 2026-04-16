"""Repair JSON wrapped in extra prose from an LLM response."""

from __future__ import annotations

import json
import sys

from json_repair import loads

LLM_OUTPUT = """
I analyzed the ticket and extracted the fields you asked for.

```json
{
  customer_id: 42,
  "sentiment": "positive",
  "summary": "Customer confirmed the fix worked",
  "tags": ["billing", "vip",],
}
```

Let me know if you want the confidence score too.
"""


def main() -> None:
    repaired = loads(LLM_OUTPUT)
    sys.stdout.write(json.dumps(repaired, indent=2) + "\n")


if __name__ == "__main__":
    main()

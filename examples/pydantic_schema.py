"""Repair malformed JSON with Pydantic v2 schema guidance."""

from __future__ import annotations

import sys

from pydantic import BaseModel, Field

from json_repair import repair_json

BAD_OUTPUT = """
{
  "customer_id": "42",
  "sentiment": "positive",
  "summary": "Customer confirmed the fix worked",
  "tags": ,
}
"""


class SupportTicket(BaseModel):
    customer_id: int
    sentiment: str
    summary: str
    tags: list[str] = Field(default_factory=list)


def main() -> None:
    repaired = repair_json(
        BAD_OUTPUT,
        return_objects=True,
        schema=SupportTicket,
        skip_json_loads=True,
    )
    payload = SupportTicket.model_validate(repaired)
    sys.stdout.write(payload.model_dump_json(indent=2) + "\n")


if __name__ == "__main__":
    main()

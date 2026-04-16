"""Repair and validate LLM output inside a FastAPI endpoint."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from json_repair import loads

app = FastAPI()


class IncomingLLMResponse(BaseModel):
    raw_output: str


class SupportTicket(BaseModel):
    customer_id: int
    sentiment: str
    summary: str
    tags: list[str] = Field(default_factory=list)


@app.post("/parse-ticket", response_model=SupportTicket)
def parse_ticket(body: IncomingLLMResponse) -> SupportTicket:
    try:
        repaired = loads(
            body.raw_output,
            skip_json_loads=True,
            schema=SupportTicket,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Could not repair JSON payload: {exc}") from exc

    return SupportTicket.model_validate(repaired)

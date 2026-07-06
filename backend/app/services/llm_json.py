"""Shared JSON contract with the LLM: parse, validate, retry once.

Every structured model call in Scranton (Dwight proposals, Smart
Summaries) goes through this single function, so the tolerance rules -
markdown fences stripped, one formatting retry with the failed answer
in context - stay identical everywhere and are tested once.
"""

import json

from pydantic import BaseModel, ValidationError

from backend.app.adapters.llm.base import LLMProvider
from backend.app.services.prompts import RETRY_REMINDER


class LLMContractError(Exception):
    """The model could not honor the JSON contract (after one retry)."""


def extract_json(text: str) -> dict:
    """Parse a JSON object out of an LLM answer, tolerating markdown fences.

    Small models sometimes wrap JSON in ```json fences despite explicit
    instructions. Stripping them here is cheaper and more reliable than
    prompt-engineering the habit away.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Drop the opening fence line (``` or ```json) and the closing fence.
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    return json.loads(cleaned)


def complete_validated[SchemaT: BaseModel](
    llm: LLMProvider, messages: list[dict], schema: type[SchemaT]
) -> SchemaT:
    """Call the model and validate its answer against a Pydantic schema.

    One retry with the failed answer in context: cheap, and it recovers
    most formatting slips from small models. A second failure raises
    LLMContractError for the caller to translate.
    """
    answer = llm.complete(messages)
    try:
        return schema.model_validate(extract_json(answer))
    except (json.JSONDecodeError, ValidationError):
        retry_messages = messages + [
            {"role": "assistant", "content": answer},
            {"role": "user", "content": RETRY_REMINDER},
        ]
        answer = llm.complete(retry_messages)
        try:
            return schema.model_validate(extract_json(answer))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise LLMContractError(
                "The model could not produce a valid answer for this request."
            ) from exc

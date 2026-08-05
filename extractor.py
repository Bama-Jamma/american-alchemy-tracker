"""Uses the Claude API to extract book and non-book document references from a transcript."""

import json

from anthropic import Anthropic

MODEL = "claude-opus-5"

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["book", "document"],
                        "description": (
                            "'book' for published books. 'document' for non-book real-world "
                            "references such as FBI memos, declassified documents, government "
                            "reports, court filings, or similar records."
                        ),
                    },
                    "title": {
                        "type": "string",
                        "description": "Title of the book or document as referenced in the transcript.",
                    },
                    "author_or_source": {
                        "type": "string",
                        "description": (
                            "Author for a book, or the originating agency/organization for a "
                            "document (e.g. 'FBI', 'CIA', 'U.S. Air Force'). Empty string if not stated."
                        ),
                    },
                    "context": {
                        "type": "string",
                        "description": "One to two sentences on how/why it was mentioned in the conversation.",
                    },
                },
                "required": ["type", "title", "author_or_source", "context"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are analyzing a transcript of an episode of American Alchemy, a podcast hosted \
by Jesse Michels covering UFOs, declassified government programs, and fringe science history.

Extract every real-world book and non-book document referenced in the conversation:
- "book": any published book mentioned by title (fiction or nonfiction).
- "document": any other real-world document mentioned, such as FBI memos, declassified files, \
government reports, court records, congressional testimony transcripts, patents, or similar records.

Only include items that are actually named or clearly identifiable in the transcript. Do not invent \
titles. If the same item is mentioned multiple times, include it once."""


def extract_references(transcript_text: str) -> list[dict]:
    """Return a list of {type, title, author_or_source, context} dicts for one transcript."""
    client = Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": f"Transcript:\n\n{transcript_text}",
            }
        ],
    )

    if response.stop_reason == "refusal":
        return []

    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)["items"]

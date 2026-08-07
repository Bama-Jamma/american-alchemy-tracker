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
                    "subcategory": {
                        "type": "string",
                        "enum": [
                            "government_document",
                            "testimony",
                            "news_media",
                            "legal_personal_record",
                            "scientific_data",
                            "essay_paper",
                        ],
                        "description": (
                            "Only for type == 'document'. Omit this field entirely for type == 'book'. "
                            "government_document: memos, declassified files, agency reports, patents. "
                            "testimony: congressional/court testimony, sworn statements, depositions. "
                            "news_media: news articles, broadcasts, documentaries. "
                            "legal_personal_record: court filings, personal correspondence/diaries, contracts. "
                            "scientific_data: datasets, study results, lab/technical reports. "
                            "essay_paper: academic papers, essays, whitepapers, theses."
                        ),
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

Every item of type "document" must also have a "subcategory" from the fixed list in the schema. Never \
include a "subcategory" on an item of type "book" — omit that field for books entirely.

Only include items that are actually named or clearly identifiable in the transcript. Do not invent \
titles. If the same item is mentioned multiple times, include it once."""


def extract_references(transcript_text: str) -> tuple[list[dict], dict]:
    """Return (items, usage) for one transcript.

    items: list of {type, title, author_or_source, context, subcategory?} dicts.
    subcategory is present only on items where type == "document".
    usage: real token counts from the API response, for cost tracking.
    """
    client = Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": f"Transcript:\n\n{transcript_text}",
            }
        ],
    )

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_creation_input_tokens": response.usage.cache_creation_input_tokens or 0,
        "cache_read_input_tokens": response.usage.cache_read_input_tokens or 0,
    }

    if response.stop_reason == "refusal":
        return [], usage

    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)["items"], usage

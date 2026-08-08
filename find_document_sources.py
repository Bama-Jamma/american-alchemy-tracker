"""Search for and verify public source URLs for extracted document references.

Uses Claude's web_search tool to look for the official/most authoritative publicly
accessible location for each document (government reading rooms, archives, FOIA
releases, etc.). Never guesses -- a document gets a URL only if the model found and
cites real search-result evidence for it; otherwise it's left unmatched.

Usage:
    python find_document_sources.py --limit N [--batch-size N] [--source PATH] [--output PATH]
"""

import argparse
import csv
import json
import os
import re
from datetime import datetime, timezone

from anthropic import Anthropic
from dotenv import load_dotenv

from build_site import _compute_data, _normalize_title
from usage import log_usage

MODEL = "claude-opus-5"
SOURCES_PATH_DEFAULT = "state/document_sources.csv"
USAGE_LOG_PATH = "state/source_search_usage_log.csv"

SOURCES_FIELDS = ["normalized_title", "title", "access_type", "source_url", "evidence", "searched_at"]

SYSTEM_PROMPT = """You are a research assistant helping people actually obtain documents referenced \
on a podcast about declassified government programs, UFOs, and fringe science history.

For each document listed below, search the web to determine the best way someone could obtain or \
view it. There are three possible outcomes -- try them in this order:

1. "direct": You find an actual publicly accessible copy of the document itself -- an official \
government site (e.g. cia.gov, archives.gov, nsa.gov, dtic.mil, congress.gov, foia.state.gov), a \
reputable archive or already-fulfilled FOIA-release repository (e.g. The Black Vault, MuckRock, \
Internet Archive, NICAP), or any other credible source hosting the actual document.

2. "request": You cannot find the document itself online, but the document is the kind of thing \
that plausibly exists as an official record (e.g. a police report, personnel file, internal memo, \
personal correspondence, medical record) -- in this case, identify which government agency, \
department, or office would most likely hold it, and find the URL of that agency's FOIA / public-\
records-request portal (or the general https://www.foia.gov/ request page if you can't confidently \
pin down a specific agency). The url here is the REQUEST portal, not the document.

3. "not_found": Neither applies -- e.g. the document was described too vaguely to identify a \
holding agency, or it doesn't sound like the kind of thing any agency would hold a filable record \
of. Return null for url in this case.

Critical rule: only include a url (for either "direct" or "request") if your search actually \
surfaced real evidence supporting it -- a real page hosting the document, or a real, verifiable \
agency FOIA/records portal. Do not guess, do not construct a plausible-looking URL, and do not \
reuse a URL from memory without having found it in this session's search results. An honest \
"not_found" is much better than a wrong or fabricated link.

After searching, output ONLY a JSON array as your final response, wrapped in a ```json code \
block, with one object per document in the same order given, each shaped exactly like:
{"title": "<the exact title as given>", "access_type": "direct"|"request"|"not_found", \
"url": "<url or null>", "evidence": "<one sentence on what you found and why you're confident, \
or null if url is null>"}"""


def load_sources(path: str) -> dict[str, dict]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {row["normalized_title"]: row for row in csv.DictReader(f)}


def append_source(path: str, record: dict) -> None:
    file_exists = os.path.exists(path) and os.path.getsize(path) > 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SOURCES_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)


def get_unique_documents(input_path: str) -> list[dict]:
    """Return unique documents (by normalized title), sorted by mention count descending --
    highest-value (most-referenced) documents get searched first."""
    data = _compute_data(input_path)
    by_norm: dict[str, dict] = {}
    for d in data["all_documents"]:
        key = _normalize_title(d["title"])
        by_norm.setdefault(key, {"title": d["title"], "source": d["source"], "count": 0})
        by_norm[key]["count"] += 1
    docs = list(by_norm.values())
    docs.sort(key=lambda d: -d["count"])
    return docs


def extract_json_block(text: str) -> list:
    match = re.search(r"```json\s*(\[.*?\])\s*```", text, re.DOTALL)
    if not match:
        match = re.search(r"(\[.*\])", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON array found in response")
    return json.loads(match.group(1))


def search_batch(documents: list[dict]) -> tuple[list[dict], dict]:
    client = Anthropic()
    doc_list = "\n".join(f"- {d['title']} (source/author: {d['source'] or 'unknown'})" for d in documents)

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20260209", "name": "web_search"}],
        messages=[{"role": "user", "content": f"Documents:\n{doc_list}"}],
    )

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_creation_input_tokens": response.usage.cache_creation_input_tokens or 0,
        "cache_read_input_tokens": response.usage.cache_read_input_tokens or 0,
    }

    text_blocks = [b.text for b in response.content if b.type == "text"]
    results = extract_json_block("\n".join(text_blocks))
    return results, usage


def run(limit: int, batch_size: int, source_path: str, output_path: str) -> None:
    load_dotenv()

    all_docs = get_unique_documents(source_path)
    already_searched = load_sources(output_path)
    todo = [d for d in all_docs if _normalize_title(d["title"]) not in already_searched][:limit]

    print(f"{len(all_docs)} unique documents total, {len(already_searched)} already searched.")
    print(f"Searching the next {len(todo)}...")

    counts = {"direct": 0, "request": 0, "not_found": 0}
    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        print(f"\nBatch {i // batch_size + 1}: {len(batch)} documents...")
        try:
            results, usage = search_batch(batch)
        except Exception as exc:
            print(f"  -> batch failed: {exc}")
            continue

        log_usage(USAGE_LOG_PATH, f"batch_{i // batch_size + 1}", usage)

        for r in results:
            norm = _normalize_title(r["title"])
            access_type = r.get("access_type") or "not_found"
            counts[access_type] = counts.get(access_type, 0) + 1
            append_source(
                output_path,
                {
                    "normalized_title": norm,
                    "title": r["title"],
                    "access_type": access_type,
                    "source_url": r.get("url") or "",
                    "evidence": r.get("evidence") or "",
                    "searched_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            label = {"direct": "DIRECT", "request": "REQUEST", "not_found": "not found"}[access_type]
            print(f"  [{label}] {r['title']}")

    print(f"\nDone. {counts['direct']} direct, {counts['request']} request-only, {counts['not_found']} not found (of {len(todo)}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=15, help="Max documents to search this run")
    parser.add_argument("--batch-size", type=int, default=15, help="Documents per API call")
    parser.add_argument("--source", default="output/references.csv", help="Source references CSV")
    parser.add_argument("--output", default=SOURCES_PATH_DEFAULT, help="Document sources lookup CSV")
    args = parser.parse_args()

    run(args.limit, args.batch_size, args.source, args.output)

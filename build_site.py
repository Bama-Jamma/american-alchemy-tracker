"""Build docs/data.json for the static site from output/references.csv.

Usage:
    python build_site.py [--input PATH] [--output PATH]
"""

import argparse
import csv
import json
import os
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import quote_plus

DOCUMENT_SOURCES_PATH = "state/document_sources.csv"

SUBCATEGORY_ORDER = [
    "government_document",
    "testimony",
    "news_media",
    "legal_personal_record",
    "scientific_data",
    "essay_paper",
]

SUBCATEGORY_LABELS = {
    "government_document": "Government documents",
    "testimony": "Testimony",
    "news_media": "News & media",
    "legal_personal_record": "Legal & personal records",
    "scientific_data": "Scientific data",
    "essay_paper": "Essays & papers",
}


def amazon_search_url(title: str, author: str) -> str:
    query = f"{title} {author}".strip() if author else title
    return f"https://www.amazon.com/s?k={quote_plus(query)}"


def _normalize_title(title: str) -> str:
    """Loose key for grouping the same item mentioned across episodes -- lowercase,
    strip punctuation/whitespace differences. Exact-match only; doesn't try to catch
    paraphrased titles, which would risk false-grouping unrelated items."""
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _load_document_sources(path: str = DOCUMENT_SOURCES_PATH) -> dict[str, dict]:
    """{normalized_title: {access_type, source_url, evidence}} for documents that have
    been searched via find_document_sources.py. Only entries with a real url are kept --
    "not_found" rows exist in the CSV as a record of what's been searched, but carry
    nothing worth attaching to the site data."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {
            row["normalized_title"]: {
                "access_type": row["access_type"],
                "source_url": row["source_url"],
                "evidence": row["evidence"],
            }
            for row in csv.DictReader(f)
            if row.get("source_url")
        }


def _compute_data(input_path: str) -> dict:
    """Build the site data dict, minus `generated_at` -- callers stamp that separately
    so content-only comparisons (does the actual data differ?) aren't defeated by a
    timestamp that changes on every call."""
    episodes_by_id: dict[str, dict] = {}
    order: list[str] = []
    all_books: list[dict] = []
    all_documents: list[dict] = []
    mention_groups: dict[str, dict] = {}
    document_sources = _load_document_sources()

    with open(input_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            video_id = row["video_id"]
            if video_id not in episodes_by_id:
                episodes_by_id[video_id] = {
                    "video_id": video_id,
                    "title": row["episode"],
                    "upload_date": row["upload_date"] or None,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "books": [],
                    "documents": {},
                }
                order.append(video_id)

            episode = episodes_by_id[video_id]
            episode_ref = {
                "video_id": video_id,
                "episode_title": row["episode"],
                "upload_date": row["upload_date"] or None,
            }

            if row["type"] == "book":
                book = {
                    "title": row["title"],
                    "author": row["author_or_source"],
                    "context": row["context"],
                    "amazon_url": amazon_search_url(row["title"], row["author_or_source"]),
                }
                episode["books"].append(book)
                all_books.append({**book, **episode_ref})
            else:
                subcat = row["subcategory"] or "government_document"
                found_source = document_sources.get(_normalize_title(row["title"]))
                doc = {
                    "title": row["title"],
                    "source": row["author_or_source"],
                    "context": row["context"],
                    "subcategory": subcat,
                    "access_type": found_source["access_type"] if found_source else None,
                    "source_url": found_source["source_url"] if found_source else None,
                    "source_evidence": found_source["evidence"] if found_source else None,
                }
                episode["documents"].setdefault(subcat, []).append(
                    {k: v for k, v in doc.items() if k != "subcategory"}
                )
                all_documents.append({**doc, **episode_ref})

            key = (row["type"], _normalize_title(row["title"]))
            if key not in mention_groups:
                mention_groups[key] = {
                    "type": row["type"],
                    "title": row["title"],
                    "author_or_source": row["author_or_source"],
                    "subcategory": row["subcategory"] or None,
                    "episodes": [],
                    "amazon_url": amazon_search_url(row["title"], row["author_or_source"]) if row["type"] == "book" else None,
                    "access_type": doc["access_type"] if row["type"] == "document" else None,
                    "source_url": doc["source_url"] if row["type"] == "document" else None,
                }
            mention_groups[key]["episodes"].append(episode_ref)

    episodes = [episodes_by_id[vid] for vid in order]

    # Sort chronologically (oldest first). Episodes with an unknown upload_date sort last.
    episodes.sort(key=lambda e: e["upload_date"] or "9999-99-99")
    all_books.sort(key=lambda b: b["title"].lower())
    all_documents.sort(key=lambda d: d["title"].lower())

    # Order each episode's document subcategories consistently.
    for episode in episodes:
        episode["documents"] = {
            key: episode["documents"][key] for key in SUBCATEGORY_ORDER if key in episode["documents"]
        }

    most_referenced = [g for g in mention_groups.values() if len(g["episodes"]) >= 2]
    most_referenced.sort(key=lambda g: (-len(g["episodes"]), g["title"].lower()))

    return {
        "generated_episode_count": len(episodes),
        "subcategory_labels": SUBCATEGORY_LABELS,
        "episodes": episodes,
        "all_books": all_books,
        "all_documents": all_documents,
        "most_referenced": most_referenced,
    }


def build(input_path: str, output_path: str) -> dict:
    """Compute site data, stamp it with the current time, and write it -- always,
    regardless of whether the content changed. Used by the CLI entrypoint, where a
    fresh timestamp on every explicit run is the expected behavior."""
    data = {"generated_at": datetime.now(timezone.utc).isoformat(), **_compute_data(input_path)}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data


def publish(input_path: str = "output/references.csv", output_path: str = "docs/data.json") -> bool:
    """Rebuild docs/data.json and commit + push it, but only if the actual content
    changed (ignores the generated_at timestamp, which always differs). Returns True
    on success, including the no-op case where nothing needed publishing.

    Never raises -- a publish failure (e.g. no network) shouldn't take down a pipeline
    run that otherwise succeeded; it just prints a warning so the gap is visible.
    """
    try:
        new_data = _compute_data(input_path)

        old_data = {}
        try:
            with open(output_path, encoding="utf-8") as f:
                old_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        old_data.pop("generated_at", None)

        if old_data == new_data:
            print(f"Site data unchanged ({new_data['generated_episode_count']} episodes) -- nothing to publish.")
            return True

        stamped = {"generated_at": datetime.now(timezone.utc).isoformat(), **new_data}
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(stamped, f, indent=2, ensure_ascii=False)

        subprocess.run(["git", "add", output_path], check=True)
        subprocess.run(
            ["git", "commit", "-m", f"Auto-update site data ({new_data['generated_episode_count']} episodes)"],
            check=True,
        )
        subprocess.run(["git", "push"], check=True)
        print(f"Published site data: {new_data['generated_episode_count']} episodes.")
        return True
    except Exception as exc:
        print(f"WARNING: failed to publish site data ({type(exc).__name__}: {exc}). Run `python build_site.py` and push manually.")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="output/references.csv", help="Source CSV path")
    parser.add_argument("--output", default="docs/data.json", help="Generated JSON output path")
    args = parser.parse_args()

    data = build(args.input, args.output)
    print(f"Wrote {data['generated_episode_count']} episode(s) to {args.output}")

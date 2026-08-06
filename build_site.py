"""Build docs/data.json for the static site from output/references.csv.

Usage:
    python build_site.py [--input PATH] [--output PATH]
"""

import argparse
import csv
import json
from datetime import datetime, timezone
from urllib.parse import quote_plus

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


def build(input_path: str, output_path: str) -> dict:
    episodes_by_id: dict[str, dict] = {}
    order: list[str] = []

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
            if row["type"] == "book":
                episode["books"].append(
                    {
                        "title": row["title"],
                        "author": row["author_or_source"],
                        "context": row["context"],
                        "amazon_url": amazon_search_url(row["title"], row["author_or_source"]),
                    }
                )
            else:
                subcat = row["subcategory"] or "government_document"
                episode["documents"].setdefault(subcat, []).append(
                    {
                        "title": row["title"],
                        "source": row["author_or_source"],
                        "context": row["context"],
                    }
                )

    episodes = [episodes_by_id[vid] for vid in order]

    # Sort chronologically (oldest first). Episodes with an unknown upload_date sort last.
    episodes.sort(key=lambda e: e["upload_date"] or "9999-99-99")

    # Order each episode's document subcategories consistently.
    for episode in episodes:
        episode["documents"] = {
            key: episode["documents"][key] for key in SUBCATEGORY_ORDER if key in episode["documents"]
        }

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_episode_count": len(episodes),
        "subcategory_labels": SUBCATEGORY_LABELS,
        "episodes": episodes,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="output/references.csv", help="Source CSV path")
    parser.add_argument("--output", default="docs/data.json", help="Generated JSON output path")
    args = parser.parse_args()

    data = build(args.input, args.output)
    print(f"Wrote {data['generated_episode_count']} episode(s) to {args.output}")

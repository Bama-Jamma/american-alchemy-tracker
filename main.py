"""Pull transcripts from the American Alchemy channel and extract books/documents mentioned.

Usage:
    python main.py [--limit N] [--output PATH]
"""

import argparse
import csv
import sys

from dotenv import load_dotenv

from extractor import extract_references
from youtube_source import get_transcript, list_episodes

CSV_FIELDS = ["type", "title", "author_or_source", "context", "episode", "video_id"]


def run(limit: int, output_path: str) -> None:
    load_dotenv()

    print(f"Fetching episode list (limit={limit})...")
    episodes = list_episodes(limit)
    print(f"Found {len(episodes)} episode(s).")

    rows = []
    for i, episode in enumerate(episodes, start=1):
        title = episode["title"]
        video_id = episode["video_id"]
        print(f"[{i}/{len(episodes)}] {title} ({video_id})")

        transcript = get_transcript(video_id)
        if transcript is None:
            print("  -> no transcript available, skipping")
            continue

        print(f"  -> transcript fetched ({len(transcript)} chars), extracting references...")
        try:
            items = extract_references(transcript)
        except Exception as exc:
            print(f"  -> extraction failed: {exc}", file=sys.stderr)
            continue

        print(f"  -> found {len(items)} reference(s)")
        for item in items:
            rows.append(
                {
                    "type": item["type"],
                    "title": item["title"],
                    "author_or_source": item["author_or_source"],
                    "context": item["context"],
                    "episode": title,
                    "video_id": video_id,
                }
            )

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} row(s) to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5, help="Number of episodes to process")
    parser.add_argument("--output", default="output/references.csv", help="CSV output path")
    args = parser.parse_args()

    run(args.limit, args.output)

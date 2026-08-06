"""Pull transcripts from the American Alchemy channel and extract books/documents mentioned.

Usage:
    python main.py [--limit N] [--output PATH] [--oldest-first] [--append]
"""

import argparse
import csv
import os
import sys

from dotenv import load_dotenv

from extractor import extract_references
from youtube_source import get_transcript, get_upload_date, list_episodes

CSV_FIELDS = [
    "type",
    "subcategory",
    "title",
    "author_or_source",
    "context",
    "episode",
    "video_id",
    "upload_date",
]


def run(limit: int, output_path: str, oldest_first: bool = False, append: bool = False) -> None:
    load_dotenv()

    print(f"Fetching episode list (limit={limit}, oldest_first={oldest_first})...")
    episodes = list_episodes(limit, oldest_first=oldest_first)
    print(f"Found {len(episodes)} episode(s).")

    rows = []
    for i, episode in enumerate(episodes, start=1):
        title = episode["title"]
        video_id = episode["video_id"]
        print(f"[{i}/{len(episodes)}] {title} ({video_id})")

        upload_date = get_upload_date(video_id)

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
                    "subcategory": item.get("subcategory", ""),
                    "title": item["title"],
                    "author_or_source": item["author_or_source"],
                    "context": item["context"],
                    "episode": title,
                    "video_id": video_id,
                    "upload_date": upload_date or "",
                }
            )

    file_exists = os.path.exists(output_path) and os.path.getsize(output_path) > 0
    mode = "a" if append and file_exists else "w"
    with open(output_path, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if mode == "w":
            writer.writeheader()
        writer.writerows(rows)

    verb = "Appended" if mode == "a" else "Wrote"
    print(f"\n{verb} {len(rows)} row(s) to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5, help="Number of episodes to process")
    parser.add_argument("--output", default="output/references.csv", help="CSV output path")
    parser.add_argument(
        "--oldest-first",
        action="store_true",
        help="Process the earliest episodes on the channel instead of the most recent",
    )
    parser.add_argument("--append", action="store_true", help="Append to the output CSV instead of overwriting it")
    args = parser.parse_args()

    run(args.limit, args.output, oldest_first=args.oldest_first, append=args.append)

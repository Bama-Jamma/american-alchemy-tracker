"""Pull transcripts from the American Alchemy channel and extract books/documents mentioned.

Usage:
    python main.py --next N [--output PATH] [--ledger PATH]
    python main.py --limit N [--output PATH] [--oldest-first] [--append] [--ledger PATH]
"""

import argparse
import csv
import os
import sys

from dotenv import load_dotenv

from extractor import extract_references
from progress import append_processed, load_processed, make_record
from usage import log_usage
from youtube_source import CHANNEL_URL, get_transcript, get_upload_date, list_episodes

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

LEDGER_PATH_DEFAULT = "state/processed_episodes.csv"
USAGE_LOG_PATH_DEFAULT = "state/usage_log.csv"


def select_next_unprocessed(count: int, ledger_path: str) -> list[dict]:
    """Return the next `count` oldest episodes not already present in the ledger."""
    processed = load_processed(ledger_path)
    all_episodes = list_episodes(10_000, oldest_first=True)  # full channel, ascending
    unprocessed = [ep for ep in all_episodes if ep["video_id"] not in processed]
    return unprocessed[:count]


def run(
    episodes: list[dict],
    output_path: str,
    ledger_path: str,
    usage_log_path: str = USAGE_LOG_PATH_DEFAULT,
    append: bool = True,
) -> None:
    load_dotenv()

    rows = []
    for i, episode in enumerate(episodes, start=1):
        title = episode["title"]
        video_id = episode["video_id"]
        print(f"[{i}/{len(episodes)}] {title} ({video_id})")

        upload_date = get_upload_date(video_id)

        try:
            transcript = get_transcript(video_id)
        except Exception as exc:
            print(f"\nSTOPPING: transcript fetch failed for {video_id} ({type(exc).__name__}): {exc}", file=sys.stderr)
            print("This looks like an infrastructure problem (e.g. YouTube rate-limiting this IP), not a fact", file=sys.stderr)
            print("about the video, so it was NOT recorded in the ledger. Re-run later to resume from here.", file=sys.stderr)
            break

        reference_count = 0
        if transcript is None:
            print("  -> no transcript available, skipping")
        else:
            print(f"  -> transcript fetched ({len(transcript)} chars), extracting references...")
            try:
                items, api_usage = extract_references(transcript)
            except Exception as exc:
                print(f"  -> extraction failed: {exc}", file=sys.stderr)
                items = None

            if items is None:
                continue  # don't mark as processed; retry this one next time

            log_usage(usage_log_path, video_id, api_usage)

            reference_count = len(items)
            print(f"  -> found {reference_count} reference(s)")
            for item in items:
                subcategory = item.get("subcategory", "")
                if item["type"] == "document" and not subcategory:
                    subcategory = "government_document"
                    print(f"  -> WARNING: model omitted subcategory for document {item['title']!r}, defaulted to {subcategory!r}")
                rows.append(
                    {
                        "type": item["type"],
                        "subcategory": subcategory,
                        "title": item["title"],
                        "author_or_source": item["author_or_source"],
                        "context": item["context"],
                        "episode": title,
                        "video_id": video_id,
                        "upload_date": upload_date or "",
                    }
                )

        append_processed(
            ledger_path,
            make_record(video_id, title, upload_date, has_transcript=transcript is not None, reference_count=reference_count),
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
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--next", type=int, metavar="N", help="Process the next N not-yet-attempted episodes, oldest first")
    mode.add_argument("--limit", type=int, metavar="N", help="Process N episodes (manual mode, ignores the ledger's skip logic)")
    parser.add_argument("--output", default="output/references.csv", help="CSV output path")
    parser.add_argument("--ledger", default=LEDGER_PATH_DEFAULT, help="Processed-episodes ledger path")
    parser.add_argument("--usage-log", default=USAGE_LOG_PATH_DEFAULT, help="Per-call API token usage log path")
    parser.add_argument(
        "--oldest-first",
        action="store_true",
        help="(--limit mode only) process the earliest episodes instead of the most recent",
    )
    parser.add_argument("--append", action="store_true", help="(--limit mode only) append to the output CSV instead of overwriting it")
    args = parser.parse_args()

    if args.next is not None:
        print(f"Finding the next {args.next} unprocessed episode(s) on {CHANNEL_URL} ...")
        episodes = select_next_unprocessed(args.next, args.ledger)
        print(f"Selected {len(episodes)} episode(s).")
        run(episodes, args.output, args.ledger, args.usage_log, append=True)
    else:
        print(f"Fetching episode list (limit={args.limit}, oldest_first={args.oldest_first})...")
        episodes = list_episodes(args.limit, oldest_first=args.oldest_first)
        print(f"Found {len(episodes)} episode(s).")
        run(episodes, args.output, args.ledger, args.usage_log, append=args.append)

"""Tracks every episode we've attempted (regardless of outcome) so a sweep across the
channel can resume without re-processing episodes that had no transcript or yielded
zero references — neither of which leaves a row in output/references.csv."""

import csv
import os
from datetime import datetime, timezone

LEDGER_FIELDS = ["video_id", "title", "upload_date", "has_transcript", "reference_count", "processed_at"]


def load_processed(path: str) -> dict[str, dict]:
    """Return {video_id: record} for every episode already attempted."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {row["video_id"]: row for row in csv.DictReader(f)}


def append_processed(path: str, record: dict) -> None:
    file_exists = os.path.exists(path) and os.path.getsize(path) > 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)


def make_record(
    video_id: str, title: str, upload_date: str | None, has_transcript: bool, reference_count: int
) -> dict:
    return {
        "video_id": video_id,
        "title": title,
        "upload_date": upload_date or "",
        "has_transcript": "true" if has_transcript else "false",
        "reference_count": reference_count,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }

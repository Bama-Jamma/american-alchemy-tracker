"""Logs real per-call Claude API token usage so spend can be computed from actual data
instead of estimates."""

import csv
import os
from datetime import datetime, timezone

USAGE_LOG_FIELDS = [
    "video_id",
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "logged_at",
]

# Claude Opus 5 pricing, per million tokens.
INPUT_PRICE_PER_MTOK = 5.00
OUTPUT_PRICE_PER_MTOK = 25.00
CACHE_WRITE_PRICE_PER_MTOK = 6.25  # 1.25x input
CACHE_READ_PRICE_PER_MTOK = 0.50  # 0.1x input


def log_usage(path: str, video_id: str, usage: dict) -> None:
    file_exists = os.path.exists(path) and os.path.getsize(path) > 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=USAGE_LOG_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(
            {
                "video_id": video_id,
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
                "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
                "logged_at": datetime.now(timezone.utc).isoformat(),
            }
        )


def cost_for_row(row: dict) -> float:
    return (
        int(row["input_tokens"]) / 1_000_000 * INPUT_PRICE_PER_MTOK
        + int(row["output_tokens"]) / 1_000_000 * OUTPUT_PRICE_PER_MTOK
        + int(row["cache_creation_input_tokens"]) / 1_000_000 * CACHE_WRITE_PRICE_PER_MTOK
        + int(row["cache_read_input_tokens"]) / 1_000_000 * CACHE_READ_PRICE_PER_MTOK
    )


def load_usage(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))

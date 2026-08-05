"""Episode listing and transcript retrieval for the American Alchemy channel."""

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import CouldNotRetrieveTranscript

CHANNEL_URL = "https://www.youtube.com/@JesseMichels/videos"


def list_episodes(limit: int, channel_url: str = CHANNEL_URL) -> list[dict]:
    """Return the `limit` most recent videos from the channel via yt-dlp (no API key needed)."""
    ydl_opts = {
        "extract_flat": True,
        "playlistend": limit,
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)

    episodes = []
    for entry in info.get("entries", [])[:limit]:
        video_id = entry.get("id")
        episodes.append(
            {
                "video_id": video_id,
                "title": entry.get("title"),
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
        )
    return episodes


def get_transcript(video_id: str) -> str | None:
    """Return the full transcript text for a video, or None if unavailable."""
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id)
        return " ".join(snippet.text for snippet in fetched)
    except CouldNotRetrieveTranscript:
        return None

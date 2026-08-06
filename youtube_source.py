"""Episode listing and transcript retrieval for the American Alchemy channel."""

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import CouldNotRetrieveTranscript

CHANNEL_URL = "https://www.youtube.com/@JesseMichels/videos"


def list_episodes(limit: int, channel_url: str = CHANNEL_URL, oldest_first: bool = False) -> list[dict]:
    """Return `limit` videos from the channel via yt-dlp (no API key needed).

    The channel listing is newest-first by default. With oldest_first=True, the full
    listing is fetched so the true oldest `limit` videos can be selected and returned
    in ascending (oldest-to-newest) order.
    """
    ydl_opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    if not oldest_first:
        ydl_opts["playlistend"] = limit

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)

    entries = info.get("entries", [])
    if oldest_first:
        selected = list(reversed(entries[-limit:]))
    else:
        selected = entries[:limit]

    episodes = []
    for entry in selected:
        video_id = entry.get("id")
        episodes.append(
            {
                "video_id": video_id,
                "title": entry.get("title"),
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
        )
    return episodes


def get_upload_date(video_id: str) -> str | None:
    """Return the video's upload date as 'YYYY-MM-DD', or None if it can't be determined."""
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": False}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
    except yt_dlp.utils.DownloadError:
        return None

    upload_date = info.get("upload_date")  # 'YYYYMMDD' or None
    if not upload_date:
        return None
    return f"{upload_date[0:4]}-{upload_date[4:6]}-{upload_date[6:8]}"


def get_transcript(video_id: str) -> str | None:
    """Return the full transcript text for a video, or None if unavailable."""
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id)
        return " ".join(snippet.text for snippet in fetched)
    except CouldNotRetrieveTranscript:
        return None

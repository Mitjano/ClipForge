"""Phase 3 — Downloader. Fetches MP4 files via yt-dlp."""
import json
import logging
from pathlib import Path

import yt_dlp

import config

logger = logging.getLogger("downloader")


def download_clip(clip: dict) -> str | None:
    """Download a single clip. Returns path to MP4 or None on failure."""
    out_template = str(config.DOWNLOADS_DIR / f"{clip['id']}.%(ext)s")
    expected_path = config.DOWNLOADS_DIR / f"{clip['id']}.mp4"

    if expected_path.exists() and expected_path.stat().st_size > 0:
        logger.info(f"  Already downloaded: {clip['id']}")
        return str(expected_path)

    ydl_opts = {
        "outtmpl": out_template,
        "format": "bestvideo[height<=1080]+bestaudio/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "retries": 3,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([clip["url"]])

        if expected_path.exists() and expected_path.stat().st_size > 0:
            logger.info(f"  Downloaded: {clip['id']} ({expected_path.stat().st_size // 1024}KB)")
            return str(expected_path)
        else:
            logger.warning(f"  File missing after download: {clip['id']}")
            return None
    except Exception as e:
        logger.warning(f"  Download failed {clip['id']}: {e}")
        return None


def run(ranked: list[dict]) -> list[dict]:
    """Download all ranked clips. Returns list with added 'file_path' field."""
    downloaded = []

    for i, clip in enumerate(ranked, 1):
        logger.info(f"[{i}/{len(ranked)}] {clip['title'][:60]}")
        path = download_clip(clip)
        if path:
            clip["file_path"] = path
            downloaded.append(clip)

    logger.info(f"Downloaded {len(downloaded)}/{len(ranked)} clips")

    out_path = config.DOWNLOADS_DIR / "downloaded.json"
    out_path.write_text(json.dumps(downloaded, indent=2, ensure_ascii=False))

    return downloaded


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    ranked_path = config.DOWNLOADS_DIR / "ranked.json"
    if not ranked_path.exists():
        print("Run scorer.py first")
        exit(1)
    ranked = json.loads(ranked_path.read_text())
    downloaded = run(ranked)
    print(f"{len(downloaded)} clips downloaded")

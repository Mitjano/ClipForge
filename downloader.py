"""Phase 3 — Downloader. Fetches MP4 files via yt-dlp with audio."""
import json
import logging
import subprocess
from pathlib import Path

import yt_dlp

import config

logger = logging.getLogger("downloader")


def has_audio(filepath: str) -> bool:
    """Check if MP4 file contains an audio stream."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_streams", filepath],
            capture_output=True, text=True, timeout=10
        )
        return "codec_type=audio" in result.stdout
    except Exception:
        return False


def download_clip(clip: dict) -> str | None:
    """Download a single clip with audio. Returns path to MP4 or None."""
    expected_path = config.DOWNLOADS_DIR / f"{clip['id']}.mp4"

    if expected_path.exists() and expected_path.stat().st_size > 0 and has_audio(str(expected_path)):
        logger.info(f"  Already downloaded (with audio): {clip['id']}")
        return str(expected_path)

    # Clean up any previous video-only download
    if expected_path.exists():
        expected_path.unlink()

    out_template = str(config.DOWNLOADS_DIR / f"{clip['id']}.%(ext)s")

    # Method 1: Download via v.redd.it base URL (yt-dlp handles DASH merge)
    base_url = clip.get("url", "")  # e.g. https://v.redd.it/xxxxx
    if "v.redd.it" in base_url:
        try:
            ydl_opts = {
                "outtmpl": out_template,
                "format": "bestvideo[height<=1080]+bestaudio/best",
                "merge_output_format": "mp4",
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": 30,
                "retries": 3,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([base_url])
            if expected_path.exists() and has_audio(str(expected_path)):
                logger.info(f"  Downloaded (v.redd.it DASH): {clip['id']} ({expected_path.stat().st_size // 1024}KB)")
                return str(expected_path)
        except Exception as e:
            logger.debug(f"  v.redd.it failed: {e}")

    # Method 2: Download video from fallback URL + audio separately, merge with ffmpeg
    video_url = clip.get("video_url", "")
    if video_url and "v.redd.it" in video_url:
        try:
            # Extract base URL for audio: replace CMAF_XXX.mp4 with CMAF_AUDIO_128.mp4
            base = video_url.rsplit("/", 1)[0]  # https://v.redd.it/xxxxx
            audio_url = f"{base}/DASH_AUDIO_128.mp4"

            video_tmp = config.DOWNLOADS_DIR / f"{clip['id']}_video.mp4"
            audio_tmp = config.DOWNLOADS_DIR / f"{clip['id']}_audio.mp4"

            # Download video
            ydl_v = {"outtmpl": str(video_tmp), "quiet": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(ydl_v) as ydl:
                ydl.download([video_url])

            # Download audio
            ydl_a = {"outtmpl": str(audio_tmp), "quiet": True, "no_warnings": True}
            try:
                with yt_dlp.YoutubeDL(ydl_a) as ydl:
                    ydl.download([audio_url])
            except Exception:
                # Try alternative audio URL format
                audio_url2 = f"{base}/DASH_audio.mp4"
                try:
                    with yt_dlp.YoutubeDL(ydl_a) as ydl:
                        ydl.download([audio_url2])
                except Exception:
                    pass

            if video_tmp.exists() and audio_tmp.exists():
                # Merge with ffmpeg
                subprocess.run([
                    "ffmpeg", "-y", "-i", str(video_tmp), "-i", str(audio_tmp),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                    str(expected_path)
                ], capture_output=True, timeout=60)
                video_tmp.unlink(missing_ok=True)
                audio_tmp.unlink(missing_ok=True)

                if expected_path.exists() and has_audio(str(expected_path)):
                    logger.info(f"  Downloaded (manual merge): {clip['id']} ({expected_path.stat().st_size // 1024}KB)")
                    return str(expected_path)
            elif video_tmp.exists():
                # No audio available — use video only
                video_tmp.rename(expected_path)
                logger.info(f"  Downloaded (video only, no audio): {clip['id']}")
                return str(expected_path)

            # Cleanup
            video_tmp.unlink(missing_ok=True)
            audio_tmp.unlink(missing_ok=True)

        except Exception as e:
            logger.debug(f"  Manual merge failed: {e}")

    # Method 3: Direct fallback URL (video only, last resort)
    if not expected_path.exists() and video_url:
        try:
            ydl_opts = {"outtmpl": out_template, "quiet": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            if expected_path.exists():
                logger.info(f"  Downloaded (fallback, no audio): {clip['id']}")
                return str(expected_path)
        except Exception:
            pass

    if expected_path.exists() and expected_path.stat().st_size > 0:
        return str(expected_path)

    logger.warning(f"  All download methods failed: {clip['id']}")
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

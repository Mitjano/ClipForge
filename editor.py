"""Phase 4 — Editor. Assembles compilation via FFmpeg."""
import json
import logging
import subprocess
import tempfile
from pathlib import Path

from openai import OpenAI

import config

logger = logging.getLogger("editor")


def generate_countdown_plate(number: int, category: str, out_path: Path):
    """Generate a 2-second countdown plate image via FFmpeg."""
    text = f"#{number}"
    sub_text = category.upper() if category else ""
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c=black:s=1920x1080:d=2",
        "-vf", (
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"text='{text}':fontsize=200:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2-60,"
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
            f"text='{sub_text}':fontsize=48:fontcolor=gray:x=(w-text_w)/2:y=(h-text_h)/2+100"
        ),
        "-c:v", "libx264", "-t", "2", "-pix_fmt", "yuv420p",
        str(out_path)
    ]
    subprocess.run(cmd, capture_output=True, timeout=30)


def normalize_clip(input_path: str, output_path: Path, target_w=1920, target_h=1080, max_duration=30):
    """Normalize clip: scale, pad, normalize audio, trim."""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-t", str(max_duration),
        "-vf", f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-r", "30", "-pix_fmt", "yuv420p",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    return output_path.exists()


def generate_title_and_metadata(clips: list[dict]) -> dict:
    """Use Claude to generate YouTube title, description, and tags."""
    categories = [c.get("category", "unknown") for c in clips]
    top_category = max(set(categories), key=categories.count)

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    prompt = f"""Generate YouTube metadata for a "Top {len(clips)} funny fails" compilation.
Top category: {top_category}
Clip titles: {', '.join(c['title'][:40] for c in clips[:5])}

Respond ONLY with JSON:
{{"title": "catchy title under 70 chars with emoji", "description": "500 char description with hashtags", "tags": ["tag1", "tag2", ...]}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        logger.warning(f"Metadata generation failed: {e}")
        return {
            "title": f"Top {len(clips)} Funniest Moments That Broke The Internet 😂",
            "description": "The best funny fails compilation from across the internet!",
            "tags": ["funny", "fails", "compilation", "top15", "best of"],
        }


def run(downloaded: list[dict]) -> dict:
    """Assemble the final compilation."""
    work_dir = Path(tempfile.mkdtemp(prefix="clipforge_"))
    concat_list = []

    # Reverse order: #15 first, #1 last (countdown)
    clips = list(reversed(downloaded))

    for i, clip in enumerate(clips):
        number = len(clips) - i
        category = clip.get("category", "")
        logger.info(f"Processing #{number}: {clip['title'][:50]}")

        # Generate countdown plate
        plate_path = work_dir / f"plate_{number:02d}.mp4"
        generate_countdown_plate(number, category, plate_path)
        if plate_path.exists():
            concat_list.append(plate_path)

        # Normalize clip
        norm_path = work_dir / f"clip_{number:02d}.mp4"
        if normalize_clip(clip["file_path"], norm_path):
            concat_list.append(norm_path)
        else:
            logger.warning(f"  Failed to normalize clip #{number}")

    # Build concat file
    concat_file = work_dir / "concat.txt"
    with open(concat_file, "w") as f:
        for p in concat_list:
            f.write(f"file '{p}'\n")

    # Concatenate all segments
    output_path = config.OUTPUT_DIR / "compilation.mp4"
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=600)

    if not output_path.exists():
        logger.error(f"Compilation failed: {result.stderr.decode()[-200:]}")
        return {}

    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"Compilation ready: {output_path} ({size_mb:.1f}MB)")

    # Generate metadata
    metadata = generate_title_and_metadata(downloaded)
    metadata["file_path"] = str(output_path)

    # Add credits disclaimer
    metadata["description"] += (
        "\n\n---\nCredits to original creators. "
        "If you own any clip and want it removed, contact us."
    )

    meta_path = config.OUTPUT_DIR / "metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))

    return metadata


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    dl_path = config.DOWNLOADS_DIR / "downloaded.json"
    if not dl_path.exists():
        print("Run downloader.py first")
        exit(1)
    downloaded = json.loads(dl_path.read_text())
    result = run(downloaded)
    print(f"Title: {result.get('title', 'N/A')}")

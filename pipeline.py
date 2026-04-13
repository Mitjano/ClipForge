"""Phase 6 — Pipeline orchestrator. Runs all phases in sequence."""
import json
import logging
import shutil
import sys
from pathlib import Path

import config
import scraper
import scorer
import downloader
import editor
import uploader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.LOGS_DIR / "pipeline.log"),
    ],
)
logger = logging.getLogger("pipeline")


def cleanup():
    """Remove temporary files after successful upload."""
    for f in config.DOWNLOADS_DIR.glob("*.mp4"):
        f.unlink()
    for f in config.DOWNLOADS_DIR.glob("*.json"):
        f.unlink()
    for f in config.OUTPUT_DIR.glob("*.mp4"):
        f.unlink()
    for f in config.OUTPUT_DIR.glob("*.json"):
        f.unlink()
    logger.info("Cleanup complete")


def run_pipeline(dry_run=False):
    """Execute the full pipeline."""
    logger.info("=" * 60)
    logger.info("ClipForge Pipeline — Starting")
    logger.info("=" * 60)

    try:
        # Phase 1: Scrape
        logger.info("[1/5] Scraping Reddit...")
        candidates = scraper.run()
        if not candidates:
            logger.error("No candidates found. Aborting.")
            return

        # Phase 2: Score
        logger.info(f"[2/5] Scoring {len(candidates)} candidates...")
        ranked = scorer.run(candidates)
        if not ranked:
            logger.error("No clips scored. Aborting.")
            return

        # Phase 3: Download
        logger.info(f"[3/5] Downloading top {len(ranked)} clips...")
        downloaded = downloader.run(ranked)
        if len(downloaded) < 5:
            logger.error(f"Only {len(downloaded)} clips downloaded. Need at least 5. Aborting.")
            return

        # Phase 4: Edit
        logger.info(f"[4/5] Assembling compilation from {len(downloaded)} clips...")
        metadata = editor.run(downloaded)
        if not metadata.get("file_path"):
            logger.error("Compilation failed. Aborting.")
            return

        if dry_run:
            logger.info(f"[DRY RUN] Would upload: {metadata.get('title')}")
            logger.info(f"[DRY RUN] File: {metadata.get('file_path')}")
            return

        # Phase 5: Upload
        logger.info("[5/5] Uploading to YouTube...")
        video_id = uploader.run(metadata)
        if video_id:
            logger.info(f"SUCCESS: https://youtube.com/watch?v={video_id}")
        else:
            logger.error("Upload failed.")
            return

        # Cleanup
        cleanup()

    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        raise


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    run_pipeline(dry_run=dry_run)

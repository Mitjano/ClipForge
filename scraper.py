"""Phase 1 — Reddit scraper. Fetches top video posts from selected subreddits."""
import json
import logging
from pathlib import Path

import praw

import config

logger = logging.getLogger("scraper")


def run() -> list[dict]:
    """Scrape top video posts from the last 7 days."""
    reddit = praw.Reddit(
        client_id=config.REDDIT_CLIENT_ID,
        client_secret=config.REDDIT_SECRET,
        user_agent=config.REDDIT_USER_AGENT,
    )

    candidates = []
    seen_ids = set()

    for sub_name in config.SUBREDDITS:
        logger.info(f"Scanning r/{sub_name}...")
        subreddit = reddit.subreddit(sub_name)

        for post in subreddit.top(time_filter="week", limit=100):
            if post.id in seen_ids:
                continue
            seen_ids.add(post.id)

            # Must be a video
            if not post.is_video:
                continue

            # Score/ratio filters
            if post.score < config.MIN_SCORE:
                continue
            if post.upvote_ratio < config.MIN_UPVOTE_RATIO:
                continue

            # Skip unwanted flairs
            flair = (post.link_flair_text or "").lower()
            if any(skip in flair for skip in config.SKIP_FLAIRS):
                continue

            # Duration filter
            media = post.media
            if not media or "reddit_video" not in media:
                continue
            duration = media["reddit_video"].get("duration", 0)
            if duration < config.MIN_DURATION or duration > config.MAX_DURATION:
                continue

            video_url = media["reddit_video"].get("fallback_url", post.url)

            candidates.append({
                "id": post.id,
                "title": post.title,
                "url": post.url,
                "video_url": video_url,
                "score": post.score,
                "ratio": post.upvote_ratio,
                "comments": post.num_comments,
                "subreddit": str(post.subreddit),
                "author": str(post.author),
                "duration": duration,
                "flair": post.link_flair_text,
            })

    # Sort by score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)
    logger.info(f"Found {len(candidates)} candidates across {len(config.SUBREDDITS)} subreddits")

    # Save
    out_path = config.DOWNLOADS_DIR / "candidates.json"
    out_path.write_text(json.dumps(candidates, indent=2, ensure_ascii=False))
    logger.info(f"Saved to {out_path}")

    return candidates


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    results = run()
    print(f"{len(results)} candidates found")

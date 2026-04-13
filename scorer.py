"""Phase 2 — AI scorer. Uses Claude API to evaluate and rank clips."""
import json
import logging

import anthropic

import config

logger = logging.getLogger("scorer")

SCORING_PROMPT = """Oceń potencjał viralowy tego klipu do kompilacji YouTube (funny fails).
Tytuł: {title}
Subreddit: r/{subreddit}
Upvoty: {score}
Komentarze: {comments}
Długość: {duration}s

Odpowiedz TYLKO JSONem bez żadnego dodatkowego tekstu:
{{"score": 1-10, "category": "fail|animal|cringe|unexpected|wholesome", "reason": "1 zdanie"}}"""


def score_clip(client: anthropic.Anthropic, clip: dict) -> dict:
    """Score a single clip using Claude API."""
    prompt = SCORING_PROMPT.format(
        title=clip["title"],
        subreddit=clip["subreddit"],
        score=clip["score"],
        comments=clip["comments"],
        duration=clip["duration"],
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        result = json.loads(text)
        return {
            "ai_score": int(result.get("score", 5)),
            "category": result.get("category", "unknown"),
            "reason": result.get("reason", ""),
        }
    except Exception as e:
        logger.warning(f"Scoring failed for {clip['id']}: {e}")
        return {"ai_score": 5, "category": "unknown", "reason": "scoring failed"}


def run(candidates: list[dict]) -> list[dict]:
    """Score all candidates and return top N ranked."""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    # Normalize reddit scores for ranking
    max_score = max(c["score"] for c in candidates) if candidates else 1
    max_comments = max(c["comments"] for c in candidates) if candidates else 1

    for clip in candidates:
        result = score_clip(client, clip)
        clip.update(result)

        # Final composite score
        norm_reddit = clip["score"] / max_score
        norm_ai = clip["ai_score"] / 10.0
        norm_comments = clip["comments"] / max_comments
        clip["final_score"] = (norm_reddit * 0.4) + (norm_ai * 0.4) + (norm_comments * 0.2)

        logger.info(f"  [{clip['ai_score']}/10] {clip['category']:12s} | {clip['title'][:60]}")

    # Sort by final score, take top N
    candidates.sort(key=lambda x: x.get("final_score", 0), reverse=True)
    ranked = candidates[:config.TOP_N]

    logger.info(f"Top {len(ranked)} clips selected")

    out_path = config.DOWNLOADS_DIR / "ranked.json"
    out_path.write_text(json.dumps(ranked, indent=2, ensure_ascii=False))
    logger.info(f"Saved to {out_path}")

    return ranked


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    candidates_path = config.DOWNLOADS_DIR / "candidates.json"
    if not candidates_path.exists():
        print("Run scraper.py first")
        exit(1)
    candidates = json.loads(candidates_path.read_text())
    ranked = run(candidates)
    for i, clip in enumerate(ranked, 1):
        print(f"#{i} [{clip.get('ai_score', '?')}/10] {clip['title'][:70]}")

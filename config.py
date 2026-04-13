"""Configuration — loads from .env file."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Reddit
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_SECRET = os.getenv("REDDIT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "CompilationBot/1.0")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# YouTube
YOUTUBE_CREDENTIALS_PATH = os.getenv("YOUTUBE_CREDENTIALS_PATH", "/app/credentials.json")

# Paths
BASE_DIR = Path(__file__).parent
DOWNLOADS_DIR = Path(os.getenv("DOWNLOADS_DIR", BASE_DIR / "downloads"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", BASE_DIR / "output"))
ASSETS_DIR = Path(os.getenv("ASSETS_DIR", BASE_DIR / "assets"))
LOGS_DIR = BASE_DIR / "logs"

# Ensure dirs exist
for d in [DOWNLOADS_DIR, OUTPUT_DIR, ASSETS_DIR, LOGS_DIR,
          ASSETS_DIR / "countdown", ASSETS_DIR / "music"]:
    d.mkdir(parents=True, exist_ok=True)

# Scraper settings
SUBREDDITS = [
    "funny",
    "instantregret",
    "Unexpected",
    "Whatcouldgowrong",
    "AnimalsBeingDerps",
    "therewasanattempt",
    "PublicFreakout",
]
MIN_SCORE = 1000
MIN_UPVOTE_RATIO = 0.90
MIN_DURATION = 5
MAX_DURATION = 45
SKIP_FLAIRS = ["sports", "news", "political"]
TOP_N = 15

"""Phase 5 — YouTube uploader via Data API v3."""
import json
import logging
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import config

logger = logging.getLogger("uploader")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_PATH = Path(config.YOUTUBE_CREDENTIALS_PATH).parent / "token.json"


def get_youtube_service():
    """Authenticate and return YouTube API service."""
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.YOUTUBE_CREDENTIALS_PATH, SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def run(metadata: dict) -> str | None:
    """Upload compilation to YouTube. Returns video ID or None."""
    file_path = metadata.get("file_path")
    if not file_path or not Path(file_path).exists():
        logger.error(f"Video file not found: {file_path}")
        return None

    youtube = get_youtube_service()

    body = {
        "snippet": {
            "title": metadata.get("title", "Funny Compilation")[:100],
            "description": metadata.get("description", "")[:5000],
            "tags": metadata.get("tags", [])[:15],
            "categoryId": "23",  # Comedy
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(file_path, chunksize=10 * 1024 * 1024, resumable=True)

    logger.info(f"Uploading: {metadata.get('title', 'unknown')}")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info(f"  Upload progress: {int(status.progress() * 100)}%")

    video_id = response.get("id")
    logger.info(f"Upload complete: https://youtube.com/watch?v={video_id}")
    return video_id


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    meta_path = config.OUTPUT_DIR / "metadata.json"
    if not meta_path.exists():
        print("Run editor.py first")
        exit(1)
    metadata = json.loads(meta_path.read_text())
    video_id = run(metadata)
    if video_id:
        print(f"Uploaded: https://youtube.com/watch?v={video_id}")

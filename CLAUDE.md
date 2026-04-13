# Compilation Bot — Kontekst Projektu

## Cel
Automatyczny pipeline który:
1. Scrape'uje top filmy z Reddit (funny/fails)
2. Ocenia i rankinguje klipy przez Claude API
3. Pobiera pliki MP4 przez yt-dlp
4. Składa kompilację z planszami countdown przez FFmpeg
5. Uploaduje automatycznie na YouTube
6. Wszystko sterowane przez CRON na serwerze Hetzner

## Serwer
- Hetzner VPS (Linux/Ubuntu)
- Wszystko zarządzane przez crontab
- Środowisko: Python 3, FFmpeg zainstalowany systemowo

## Stack
- **Scraping:** PRAW (Reddit API)
- **Download:** yt-dlp
- **Scoring:** Anthropic Claude API (claude-sonnet-4-20250514)
- **Editing:** FFmpeg
- **Upload:** YouTube Data API v3
- **Scheduler:** cron

## Struktura plików

```
/app/
├── CLAUDE.md
├── scraper.py          # Reddit scraping — pobiera kandydatów
├── scorer.py           # Claude API — ocenia i rankinguje klipy
├── downloader.py       # yt-dlp — pobiera MP4 z audio
├── editor.py           # FFmpeg — składa kompilację
├── uploader.py         # YouTube API — publikuje film
├── pipeline.py         # Główny orchestrator (wywołuje wszystko po kolei)
├── shorts_pipeline.py  # Osobny pipeline dla YouTube Shorts
├── config.py           # API keys, ustawienia (ładowane z .env)
├── .env                # Sekrety — NIE commitować do git
├── /downloads/         # Tymczasowe pliki MP4 (czyszczone po uploadzie)
├── /output/            # Gotowe skompilowane filmy
├── /assets/
│   ├── intro.mp4
│   ├── outro.mp4
│   ├── countdown/      # Plansze #1–#15 (generowane przez FFmpeg)
│   └── music/          # Royalty-free podkłady muzyczne
└── /logs/
    ├── scraper.log
    └── pipeline.log
```

## Zmienne środowiskowe (.env)

```
REDDIT_CLIENT_ID=...
REDDIT_SECRET=...
REDDIT_USER_AGENT=CompilationBot/1.0
ANTHROPIC_API_KEY=...
YOUTUBE_CREDENTIALS_PATH=/app/credentials.json
DOWNLOADS_DIR=/app/downloads
OUTPUT_DIR=/app/output
ASSETS_DIR=/app/assets
```

## Faza 1 — Scraper (scraper.py)

Pobiera top filmy z ostatnich 7 dni z wybranych subredditów.

**Subreddity:**
- r/funny
- r/instantregret
- r/Unexpected
- r/Whatcouldgowrong
- r/AnimalsBeingDerps
- r/therewasanattempt
- r/PublicFreakout

**Filtry:**
- `post.is_video == True`
- `post.score > 1000`
- `post.upvote_ratio > 0.90`
- Długość klipu: 5–45 sekund (`post.media["reddit_video"]["duration"]`)
- Pomijaj posty z flair zawierającym: "sports", "news", "political"

**Output:** lista słowników z polami:
```python
{
    "id": post.id,
    "title": post.title,
    "url": post.url,
    "score": post.score,
    "ratio": post.upvote_ratio,
    "comments": post.num_comments,
    "subreddit": str(post.subreddit),
    "author": str(post.author),
    "duration": post.media["reddit_video"]["duration"]
}
```

Zapisuje wyniki do `downloads/candidates.json`.

## Faza 2 — Scorer (scorer.py)

Używa Claude API do oceny każdego kandydata i wyboru top 15.

**Prompt do Claude:**
```
Oceń potencjał viralowy tego klipu do kompilacji YouTube (funny fails).
Tytuł: {title}
Upvoty: {score}
Komentarze: {comments}
Długość: {duration}s

Odpowiedz TYLKO JSONem bez żadnego dodatkowego tekstu:
{"score": 1-10, "category": "fail|animal|cringe|unexpected|wholesome", "reason": "1 zdanie"}
```

**Algorytm finalnego rankingu:**
```python
final_score = (normalized_reddit_score * 0.4) + (ai_score * 0.4) + (comment_ratio * 0.2)
```

Bierz top 15 po `final_score`. Zapisuje ranking do `downloads/ranked.json`.

## Faza 3 — Downloader (downloader.py)

Pobiera MP4 z audio dla top 15 klipów przez yt-dlp.

**Ważne:** Reddit przechowuje video i audio osobno (format DASH). yt-dlp merguje je automatycznie przez FFmpeg.

```python
ydl_opts = {
    "outtmpl": f"{DOWNLOADS_DIR}/{clip_id}.%(ext)s",
    "format": "bestvideo[height<=1080]+bestaudio/best",
    "merge_output_format": "mp4",
    "quiet": True,
}
```

Po pobraniu weryfikuj że plik istnieje i ma rozmiar > 0.

## Faza 4 — Editor (editor.py)

Składa finalną kompilację przez FFmpeg.

**Format wyjściowy:**
- Long-form: 1920x1080, 30fps, H.264 + AAC
- Shorts: 1080x1920, 30fps, H.264 + AAC

**Struktura kompilacji:**
```
[intro.mp4 3s] → [Plansza #15, 2s] → [klip_15] → [Plansza #14, 2s] → [klip_14] → ... → [Plansza #1, 2s] → [klip_1] → [outro.mp4 3s]
```

**Plansze countdown:** generowane dynamicznie przez FFmpeg (`drawtext` filter), czarne tło, biały tekst z numerem i nazwą kategorii klipu.

**Normalizacja klipów przed montażem:**
- Scale do docelowej rozdzielczości (pad jeśli inny aspect ratio)
- Normalize audio do -16 LUFS
- Trim do max 30 sekund jeśli klip dłuższy

**Muzyka w tle:** royalty-free MP3 z `/assets/music/`, -20dB pod oryginalne audio klipu, fade in/out.

**Auto-generowanie tytułu przez Claude API:**
- Format: `"Top 15 [kategoria] That Made The Internet Explode 😂 #[rok]"`
- Generuj też opis (500 znaków) i tagi (max 15 tagów)

## Faza 5 — Uploader (uploader.py)

Uploaduje gotowy film na YouTube przez YouTube Data API v3.

**Auth:** OAuth2, `credentials.json` generowany jednorazowo ręcznie przez `auth_youtube.py`, token odnawiany automatycznie.

**Parametry uploadu:**
```python
{
    "snippet": {
        "title": auto_generated_title,
        "description": auto_generated_description,
        "tags": auto_generated_tags,
        "categoryId": "23",  # Comedy
        "defaultLanguage": "en"
    },
    "status": {
        "privacyStatus": "public",
        "selfDeclaredMadeForKids": False,
    }
}
```

**Opis zawiera zawsze na końcu:**
```
Credits to original creators. If you own any clip and want it removed, contact us.
```

Po uploadzie usuwa pliki z `/downloads/` i `/output/` żeby oszczędzać miejsce na dysku.

## Faza 6 — Pipeline Orchestrator (pipeline.py)

Wywołuje wszystkie moduły po kolei z error handlingiem.

```python
def run_pipeline():
    try:
        candidates = scraper.run()          # → candidates.json
        ranked = scorer.run(candidates)     # → ranked.json
        downloaded = downloader.run(ranked) # → /downloads/*.mp4
        output = editor.run(downloaded)     # → /output/compilation.mp4
        uploader.run(output)                # → YouTube
        cleanup()                           # → usuwa tymczasowe pliki
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        # wyślij notyfikację (opcjonalnie przez email lub Telegram)
```

## Harmonogram CRON

```bash
# Long-form — każdy poniedziałek 10:00
0 10 * * 1 /usr/bin/python3 /app/pipeline.py >> /app/logs/pipeline.log 2>&1

# Shorts — każdy czwartek 18:00
0 18 * * 4 /usr/bin/python3 /app/shorts_pipeline.py >> /app/logs/shorts.log 2>&1
```

Docelowo: 2x long-form + 3x Shorts tygodniowo.

## Status wdrożenia

- [ ] Faza 1 — scraper.py
- [ ] Faza 2 — scorer.py
- [ ] Faza 3 — downloader.py
- [ ] Faza 4 — editor.py (long-form)
- [ ] Faza 5 — uploader.py
- [ ] Faza 6 — pipeline.py (orchestrator)
- [ ] Shorts pipeline
- [ ] CRON setup na Hetzner
- [ ] Monitoring / alerty błędów

## Zależności (requirements.txt)

```
praw
yt-dlp
anthropic
google-api-python-client
google-auth-httplib2
google-auth-oauthlib
python-dotenv
```

## Instalacja na Hetzner

```bash
sudo apt update && sudo apt install -y python3-pip ffmpeg
pip3 install -r requirements.txt
cp .env.example .env  # uzupełnij klucze API
python3 auth_youtube.py  # jednorazowa autoryzacja YouTube OAuth2
python3 pipeline.py --dry-run  # test bez uploadu
```

## Uwagi i ryzyka

- Muzyka w tle klipów to główne źródło Content ID strikes — scorer powinien preferować klipy bez głośnej muzyki w tle
- Reddit DASH wymaga FFmpeg do mergowania audio+video — musi być zainstalowany systemowo
- YouTube API quota: 10k units/dzień (darmowe) — 1 upload kosztuje ~1600 units, bezpieczne
- yt-dlp wymaga regularnych aktualizacji — dodaj `pip install -U yt-dlp` do cron co tydzień
- Nie commituj `.env` ani `credentials.json` do git

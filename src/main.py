import os, json, base64, random, subprocess, tempfile
from pathlib import Path
import requests

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

REGION_CODE = os.getenv("REGION_CODE", "AE").upper()
YOUTUBE_PRIVACY = os.getenv("YOUTUBE_PRIVACY", "private")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
TOKEN_B64 = os.getenv("YOUTUBE_TOKEN_B64", "")

# Retention-first formats:
# - one clear subject per Short
# - 14–22 seconds
# - 4 clips
# - strongest/relevant clip first
# - start clips inside the action instead of at the slow beginning
CONTENT = {
    "asmr": {
        "trend_keywords": ["asmr", "satisfying", "relaxing", "oddly satisfying", "soap", "sand", "texture"],
        "formats": [
            {"query": "soap cutting satisfying close up", "title": "Soap Cutting ASMR"},
            {"query": "kinetic sand satisfying close up", "title": "Kinetic Sand ASMR"},
            {"query": "satisfying texture macro close up", "title": "Visual ASMR Close-Up"},
            {"query": "oddly satisfying close up", "title": "Oddly Satisfying ASMR"},
        ],
        "hashtags": ["#Shorts", "#ASMR", "#Satisfying"],
    },
    "color_mixing": {
        "trend_keywords": ["paint", "painting", "color", "colour", "mixing", "art", "palette", "acrylic"],
        "formats": [
            {"query": "paint mixing palette knife close up", "title": "Palette Knife Color Mixing"},
            {"query": "acrylic paint mixing close up", "title": "Acrylic Color Mixing ASMR"},
            {"query": "artist mixing paint palette knife", "title": "Satisfying Paint Mixing"},
            {"query": "paint texture palette knife close up", "title": "Paint Mixing Close-Up"},
        ],
        "hashtags": ["#Shorts", "#ColorMixing", "#ASMR", "#Art"],
    },
    "exotic_fruit": {
        "trend_keywords": ["fruit", "food", "cutting", "mango", "pineapple", "papaya", "dragon fruit", "tropical"],
        "formats": [
            {"query": "dragon fruit cutting close up", "title": "Dragon Fruit Cutting ASMR"},
            {"query": "mango cutting close up", "title": "Mango Cutting ASMR"},
            {"query": "pineapple cutting close up", "title": "Pineapple Cutting ASMR"},
            {"query": "papaya cutting close up", "title": "Papaya Cutting ASMR"},
            {"query": "tropical fruit cutting close up", "title": "Exotic Fruit Cutting ASMR"},
        ],
        "hashtags": ["#Shorts", "#FruitCutting", "#ASMR", "#Satisfying"],
    },
    "exotic_cars": {
        "trend_keywords": ["car", "cars", "supercar", "sports car", "luxury car", "automotive", "engine"],
        "formats": [
            {"query": "supercar driving cinematic vertical", "title": "Supercar Cinematic"},
            {"query": "exotic sports car close up", "title": "Exotic Car Details"},
            {"query": "luxury sports car interior close up", "title": "Luxury Car Interior"},
            {"query": "supercar detail cinematic", "title": "Supercar Details"},
        ],
        "hashtags": ["#Shorts", "#Supercars", "#ExoticCars", "#Cars"],
    },
}

BLOCKED = [
    "election", "president", "prime minister", "minister", "war", "attack", "killed", "death",
    "dead", "shooting", "bomb", "earthquake", "flood", "tragedy", "murder", "crime",
    "suicide", "sex", "porn", "drug", "overdose", "hospital", "disease", "investment",
    "crypto", "stock market"
]


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-5000:])
    return p.stdout


def media_duration(path):
    try:
        out = run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path)
        ])
        return max(0.0, float(out.strip()))
    except Exception:
        return 0.0


def write_token():
    if not TOKEN_B64:
        raise RuntimeError("YOUTUBE_TOKEN_B64 secret is missing.")
    token = base64.b64decode(TOKEN_B64).decode("utf-8")
    Path("youtube_token.json").write_text(token, encoding="utf-8")


def youtube_upload_client():
    write_token()
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = Credentials.from_authorized_user_file("youtube_token.json", scopes)
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
    if not creds.valid:
        raise RuntimeError("YouTube upload token is invalid.")
    return build("youtube", "v3", credentials=creds)


def youtube_public_client():
    if not YOUTUBE_API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY secret is missing.")
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


def trending_titles(yt):
    titles = []
    for category_id in ["24", "26", "2", "22"]:
        try:
            resp = yt.videos().list(
                part="snippet",
                chart="mostPopular",
                regionCode=REGION_CODE,
                videoCategoryId=category_id,
                maxResults=20
            ).execute()
        except Exception:
            continue

        for item in resp.get("items", []):
            title = item.get("snippet", {}).get("title", "").strip()
            low = title.lower()
            if title and not any(word in low for word in BLOCKED):
                titles.append(title)
    return titles


def choose_topic(titles):
    joined = " ".join(titles).lower()
    scores = {
        topic: sum(joined.count(k) for k in data["trend_keywords"])
        for topic, data in CONTENT.items()
    }

    # Trends influence the choice, but every format still gets a chance.
    weighted = []
    for topic, score in scores.items():
        weighted.extend([topic] * max(2, min(10, score + 2)))

    return random.choice(weighted or list(CONTENT)), scores


def choose_format(topic):
    return random.choice(CONTENT[topic]["formats"])


def search_pexels(query, per_page=24):
    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY secret is missing.")

    response = requests.get(
        "https://api.pexels.com/v1/videos/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={
            "query": query,
            "per_page": per_page,
            "orientation": "portrait",
            "size": "medium",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("videos", [])


def choose_file(video):
    files = video.get("video_files", [])
    if not files:
        return None

    def rank(file_info):
        w = file_info.get("width") or 0
        h = file_info.get("height") or 0
        portrait_penalty = 0 if h >= w else 100
        resolution_penalty = 0 if min(w, h) >= 720 else 5
        width_penalty = abs((w or 720) - 1080) / 1000
        return portrait_penalty + resolution_penalty + width_penalty

    return sorted(files, key=rank)[0]


def download_clips(topic, selected_format, work, wanted=4):
    # Search the exact subject first so each Short feels coherent.
    queries = [selected_format["query"]]
    queries.extend(
        f["query"] for f in CONTENT[topic]["formats"]
        if f["query"] != selected_format["query"]
    )

    candidates = []
    seen_ids = set()

    for query_index, query in enumerate(queries):
        videos = search_pexels(query)
        for rank_index, video in enumerate(videos):
            video_id = video.get("id")
            if not video_id or video_id in seen_ids:
                continue

            file_info = choose_file(video)
            if not file_info or not file_info.get("link"):
                continue

            duration = float(video.get("duration") or 0)
            if duration and duration < 3.0:
                continue

            seen_ids.add(video_id)
            candidates.append({
                "file": file_info,
                "video": video,
                "query_index": query_index,
                "rank_index": rank_index,
            })

        if len(candidates) >= 10:
            break

    if len(candidates) < 3:
        raise RuntimeError("Not enough suitable Pexels videos found.")

    # Hook: choose from the most relevant top results instead of random stock footage.
    exact = [c for c in candidates if c["query_index"] == 0]
    hook_pool = exact[:4] if exact else candidates[:4]
    hook = random.choice(hook_pool)

    remaining = [c for c in candidates if c["video"].get("id") != hook["video"].get("id")]
    # Prefer relevant results but still vary the montage.
    remaining.sort(key=lambda c: (c["query_index"], c["rank_index"]))
    body_pool = remaining[:14]
    random.shuffle(body_pool)
    selected = [hook] + body_pool[: max(0, wanted - 1)]

    credits = []
    paths = []

    for index, item in enumerate(selected, start=1):
        output = work / f"clip_src_{index}.mp4"
        with requests.get(item["file"]["link"], stream=True, timeout=120) as response:
            response.raise_for_status()
            with open(output, "wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        paths.append(output)

        video = item["video"]
        user = video.get("user") or {}
        credits.append({
            "name": user.get("name", "Pexels contributor"),
            "url": video.get("url") or user.get("url") or "https://www.pexels.com/"
        })

    return paths, credits


def has_audio(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return bool(result.stdout.strip())


def action_start(path, seconds, hook=False):
    duration = media_duration(path)
    if duration <= seconds + 0.25:
        return 0.0

    # Stock footage often has a slow opening. Start deeper inside the clip.
    low = 0.28 if hook else 0.18
    high = 0.58 if hook else 0.52
    start = duration * random.uniform(low, high)
    return max(0.0, min(start, duration - seconds - 0.15))


def normalize_clip(src, dst, seconds, hook=False):
    start = action_start(src, seconds, hook=hook)
    video_filter = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,fps=30,format=yuv420p"
    )

    common = [
        "ffmpeg", "-y",
        "-ss", f"{start:.2f}",
        "-i", str(src),
    ]

    if has_audio(src):
        run(common + [
            "-t", f"{seconds:.2f}",
            "-vf", video_filter,
            "-af", "volume=1.10,alimiter=limit=0.95",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart",
            str(dst)
        ])
    else:
        run(common + [
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", f"{seconds:.2f}",
            "-map", "0:v:0", "-map", "1:a:0",
            "-vf", video_filter,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
            "-shortest", "-movflags", "+faststart",
            str(dst)
        ])


def make_video(clips, work):
    target_duration = random.randint(14, 22)

    # Hook is deliberately short so the visual changes quickly.
    hook_seconds = min(3.0, max(2.2, target_duration * 0.16))
    body_total = target_duration - hook_seconds
    body_seconds = body_total / max(1, len(clips) - 1)

    normalized = []
    for index, src in enumerate(clips, start=1):
        seconds = hook_seconds if index == 1 else body_seconds
        dst = work / f"clip_{index}.mp4"
        normalize_clip(src, dst, seconds, hook=(index == 1))
        normalized.append(dst)

    concat_file = work / "concat.txt"
    concat_file.write_text(
        "\n".join(f"file '{path.as_posix()}'" for path in normalized),
        encoding="utf-8"
    )

    final = work / "final.mp4"
    run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-t", str(target_duration),
        "-c", "copy",
        "-movflags", "+faststart",
        str(final)
    ])

    return final, target_duration


def upload(yt, path, title, description, tags):
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": tags[:15],
            "categoryId": "24",
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": YOUTUBE_PRIVACY,
            "selfDeclaredMadeForKids": False,
        }
    }

    media = MediaFileUpload(str(path), mimetype="video/mp4", resumable=True)
    result = yt.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
        notifySubscribers=False
    ).execute()

    return result.get("id", "")


def main():
    random.seed()

    yt_public = youtube_public_client()
    yt_upload = youtube_upload_client()

    current_titles = trending_titles(yt_public)
    topic, scores = choose_topic(current_titles)
    selected_format = choose_format(topic)

    title = selected_format["title"]
    hashtags = CONTENT[topic]["hashtags"]

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)

        clips, credits = download_clips(
            topic,
            selected_format,
            work,
            wanted=4
        )

        final, duration = make_video(clips, work)

        credit_lines = [
            f"Footage by {credit['name']} on Pexels: {credit['url']}"
            for credit in credits
        ]

        description = (
            f"{title}. Original vertical edit using licensed stock footage. "
            "No trending video is copied.\n\n"
            + "\n".join(credit_lines)
            + "\n\nPhotos/videos provided by Pexels.\n\n"
            + " ".join(hashtags)
        )

        tags = [tag.lstrip("#") for tag in hashtags] + [
            topic.replace("_", " "),
            selected_format["title"],
            "satisfying",
            "shorts"
        ]

        video_id = upload(yt_upload, final, title, description, tags)

    print(json.dumps({
        "status": "uploaded",
        "video_id": video_id,
        "topic": topic,
        "format": selected_format["query"],
        "title": title,
        "duration_seconds": duration,
        "region": REGION_CODE,
        "privacy": YOUTUBE_PRIVACY,
        "trend_scores": scores
    }, indent=2))


if __name__ == "__main__":
    main()

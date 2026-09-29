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

CONTENT = {
    "asmr": {
        "trend_keywords": ["asmr", "satisfying", "relaxing", "oddly satisfying", "slime", "soap", "texture"],
        "pexels": [
            "asmr satisfying close up",
            "satisfying texture close up",
            "slime close up",
            "soap cutting",
            "kinetic sand",
            "relaxing macro"
        ],
        "hashtags": ["#Shorts", "#ASMR", "#Satisfying", "#Relaxing"],
        "titles": [
            "Satisfying ASMR Close-Ups",
            "60 Seconds of Visual ASMR",
            "Satisfying Details You Can Watch on Repeat"
        ],
        "duration": (52, 66),
    },
    "color_mixing": {
        "trend_keywords": ["paint", "painting", "color", "colour", "mixing", "art", "palette", "acrylic"],
        "pexels": [
            "paint mixing palette knife",
            "color mixing paint",
            "acrylic paint palette knife",
            "artist mixing paint",
            "paint texture close up",
            "palette knife painting"
        ],
        "hashtags": ["#Shorts", "#ColorMixing", "#ASMR", "#Satisfying", "#Art"],
        "titles": [
            "Color Mixing With a Palette Knife",
            "Satisfying Paint Mixing Close-Up",
            "Watching These Colors Blend Is So Satisfying"
        ],
        "duration": (52, 68),
    },
    "exotic_fruit": {
        "trend_keywords": ["fruit", "food", "cutting", "mango", "pineapple", "papaya", "dragon fruit", "tropical"],
        "pexels": [
            "exotic fruit cutting",
            "tropical fruit cutting",
            "dragon fruit cutting",
            "mango cutting close up",
            "pineapple cutting",
            "papaya cutting"
        ],
        "hashtags": ["#Shorts", "#FruitCutting", "#ASMR", "#ExoticFruit", "#Satisfying"],
        "titles": [
            "Exotic Fruit Cutting ASMR",
            "Satisfying Tropical Fruit Cutting",
            "Exotic Fruits, Clean Cuts, Pure Satisfaction"
        ],
        "duration": (52, 68),
    },
    "exotic_cars": {
        "trend_keywords": ["car", "cars", "supercar", "sports car", "luxury car", "automotive", "engine"],
        "pexels": [
            "exotic sports car",
            "luxury sports car",
            "supercar driving",
            "sports car cinematic",
            "luxury car interior",
            "sports car detail"
        ],
        "hashtags": ["#Shorts", "#Supercars", "#ExoticCars", "#Cars", "#CarMontage"],
        "titles": [
            "Exotic Car Montage",
            "Supercar Details in 60 Seconds",
            "A Clean Exotic Car Montage"
        ],
        "duration": (48, 62),
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
    # Entertainment, Howto & Style, Autos & Vehicles, People & Blogs.
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
    scores = {}
    for topic, data in CONTENT.items():
        scores[topic] = sum(joined.count(k) for k in data["trend_keywords"])

    best_score = max(scores.values()) if scores else 0
    if best_score == 0:
        topic = random.choice(list(CONTENT))
    else:
        # Bias toward current signals while still allowing variety.
        weighted = []
        for topic_name, score in scores.items():
            weighted.extend([topic_name] * max(1, score + 1))
        topic = random.choice(weighted)

    return topic, scores


def search_pexels(query, per_page=18):
    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY secret is missing.")
    response = requests.get(
        "https://api.pexels.com/v1/videos/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": query, "per_page": per_page, "orientation": "portrait"},
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
        portrait_penalty = 0 if h >= w else 10
        width_penalty = abs((w or 720) - 720) / 1000
        return portrait_penalty + width_penalty

    return sorted(files, key=rank)[0]


def download_clips(topic, work, wanted=6):
    queries = CONTENT[topic]["pexels"][:]
    random.shuffle(queries)

    selected = []
    seen_ids = set()
    credits = []

    for query in queries:
        videos = search_pexels(query)
        random.shuffle(videos)

        for video in videos:
            video_id = video.get("id")
            if not video_id or video_id in seen_ids:
                continue

            file_info = choose_file(video)
            if not file_info or not file_info.get("link"):
                continue

            seen_ids.add(video_id)
            selected.append({"file": file_info, "video": video})

            user = video.get("user") or {}
            credits.append({
                "name": user.get("name", "Pexels contributor"),
                "url": video.get("url") or user.get("url") or "https://www.pexels.com/"
            })

            if len(selected) >= wanted:
                break

        if len(selected) >= wanted:
            break

    if len(selected) < 3:
        raise RuntimeError("Not enough suitable Pexels videos found.")

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


def normalize_clip(src, dst, seconds):
    video_filter = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,fps=30,format=yuv420p"
    )

    if has_audio(src):
        run([
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", str(src),
            "-t", f"{seconds:.2f}",
            "-vf", video_filter,
            "-af", "volume=1.05",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart",
            str(dst)
        ])
    else:
        run([
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", str(src),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", f"{seconds:.2f}",
            "-map", "0:v:0", "-map", "1:a:0",
            "-vf", video_filter,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
            "-shortest", "-movflags", "+faststart",
            str(dst)
        ])


def make_video(clips, topic, work):
    minimum, maximum = CONTENT[topic]["duration"]
    target_duration = random.randint(minimum, maximum)
    per_clip = target_duration / len(clips)

    normalized = []
    for index, src in enumerate(clips, start=1):
        dst = work / f"clip_{index}.mp4"
        normalize_clip(src, dst, per_clip)
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

    title = random.choice(CONTENT[topic]["titles"])
    hashtags = CONTENT[topic]["hashtags"]

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        clips, credits = download_clips(topic, work, wanted=6)
        final, duration = make_video(clips, topic, work)

        credit_lines = [
            f"Footage by {credit['name']} on Pexels: {credit['url']}"
            for credit in credits
        ]

        description = (
            "Original vertical edit using licensed stock footage. "
            "The content format is selected using broad signals from YouTube's current popular videos "
            f"for region {REGION_CODE}; no trending video is copied. "
            "Original audio from stock clips is kept when available.\n\n"
            + "\n".join(credit_lines)
            + "\n\nPhotos/videos provided by Pexels.\n\n"
            + " ".join(hashtags)
        )

        tags = [tag.lstrip("#") for tag in hashtags] + [
            topic.replace("_", " "),
            "satisfying",
            "vertical video",
            "shorts"
        ]

        video_id = upload(yt_upload, final, title, description, tags)

    print(json.dumps({
        "status": "uploaded",
        "video_id": video_id,
        "topic": topic,
        "title": title,
        "duration_seconds": duration,
        "region": REGION_CODE,
        "privacy": YOUTUBE_PRIVACY,
        "trend_scores": scores
    }, indent=2))


if __name__ == "__main__":
    main()

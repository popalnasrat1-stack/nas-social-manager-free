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

# Prompt-first creative system.
# Each Short starts with a strong visual prompt. Until an AI-video API is added,
# the automation converts that prompt into precise stock-footage searches and
# edits the closest matching clips into a retention-focused Short.
CONTENT = {
    "asmr": {
        "trend_keywords": ["asmr", "satisfying", "relaxing", "soap", "sand", "texture", "macro"],
        "hashtags": ["#Shorts", "#ASMR", "#Satisfying"],
        "duration": (13, 19),
        "concepts": [
            {
                "title": "Soap Cutting ASMR",
                "prompt": "Extreme macro ASMR of a crisp soap block being sliced cleanly, bright texture, satisfying fragments, studio lighting, action begins immediately, tight framing, seamless rhythm.",
                "searches": [
                    "soap cutting close up",
                    "satisfying soap cutting",
                    "soap slicing macro",
                    "soap asmr"
                ],
            },
            {
                "title": "Kinetic Sand ASMR",
                "prompt": "Macro kinetic sand ASMR with perfectly clean cuts and compression, vivid texture, tight framing, immediate motion, no setup, hypnotic satisfying rhythm.",
                "searches": [
                    "kinetic sand cutting close up",
                    "kinetic sand satisfying",
                    "sand asmr macro",
                    "satisfying sand"
                ],
            },
            {
                "title": "Visual ASMR Close-Up",
                "prompt": "Ultra-close visual ASMR of glossy material folding and stretching, clean background, controlled movement, rich texture, immediate action, hypnotic loop.",
                "searches": [
                    "satisfying texture close up",
                    "slime macro satisfying",
                    "oddly satisfying macro",
                    "visual asmr texture"
                ],
            },
        ],
    },
    "color_mixing": {
        "trend_keywords": ["paint", "painting", "color", "colour", "mixing", "art", "palette", "acrylic"],
        "hashtags": ["#Shorts", "#ColorMixing", "#ASMR", "#Art"],
        "duration": (14, 20),
        "concepts": [
            {
                "title": "Palette Knife Color Mixing",
                "prompt": "Extreme macro shot of thick cobalt blue and pearl white paint being folded together with a steel palette knife, glossy texture, studio lighting, satisfying slow movement, action starts instantly.",
                "searches": [
                    "paint mixing palette knife close up",
                    "blue white paint mixing",
                    "palette knife paint mixing",
                    "paint texture close up"
                ],
            },
            {
                "title": "Acrylic Color Mixing ASMR",
                "prompt": "Macro acrylic paint mixing with vivid red, yellow and white pigments blending into a smooth gradient, palette knife scraping through thick glossy paint, crisp studio close-up.",
                "searches": [
                    "acrylic paint mixing close up",
                    "color mixing paint",
                    "artist mixing acrylic paint",
                    "palette knife acrylic"
                ],
            },
            {
                "title": "Satisfying Paint Blend",
                "prompt": "Rich purple and metallic silver paint slowly blending under a palette knife, glossy ridges, extreme macro texture, clean dark background, controlled satisfying motion.",
                "searches": [
                    "purple paint mixing",
                    "metallic paint palette knife",
                    "paint mixing macro",
                    "palette knife painting close up"
                ],
            },
        ],
    },
    "exotic_fruit": {
        "trend_keywords": ["fruit", "food", "cutting", "mango", "pineapple", "papaya", "dragon fruit", "tropical"],
        "hashtags": ["#Shorts", "#FruitCutting", "#ASMR", "#Satisfying"],
        "duration": (12, 18),
        "concepts": [
            {
                "title": "Dragon Fruit Cutting ASMR",
                "prompt": "Macro ASMR shot of a chilled dragon fruit being sliced open with a razor-sharp knife, vivid pink skin and white seeded flesh, clean cutting sounds, black background, immediate first cut.",
                "searches": [
                    "dragon fruit cutting close up",
                    "dragon fruit slicing",
                    "pitaya cutting",
                    "exotic fruit cutting"
                ],
            },
            {
                "title": "Mango Cutting ASMR",
                "prompt": "Juicy ripe mango cut into perfect cubes in extreme close-up, glossy golden flesh, clean knife work, bright studio lighting, satisfying first cut immediately.",
                "searches": [
                    "mango cutting close up",
                    "mango slicing",
                    "mango cubes cutting",
                    "tropical fruit cutting"
                ],
            },
            {
                "title": "Pineapple Cutting ASMR",
                "prompt": "Extreme close-up of a ripe pineapple being peeled and sliced with fast precise knife work, bright yellow texture, crisp satisfying cuts, action starts in the first frame.",
                "searches": [
                    "pineapple cutting close up",
                    "pineapple slicing",
                    "pineapple peeling",
                    "fruit cutting asmr"
                ],
            },
            {
                "title": "Exotic Fruit Cutting ASMR",
                "prompt": "A colorful exotic tropical fruit cut open in macro close-up, unusual interior revealed instantly, vivid color, clean knife motion, satisfying texture and seamless pacing.",
                "searches": [
                    "exotic fruit cutting close up",
                    "tropical fruit cutting",
                    "rare fruit cutting",
                    "fruit slicing macro"
                ],
            },
        ],
    },
    "exotic_cars": {
        "trend_keywords": ["car", "cars", "supercar", "sports car", "luxury car", "automotive", "engine"],
        "hashtags": ["#Shorts", "#Supercars", "#ExoticCars", "#Cars"],
        "duration": (12, 18),
        "concepts": [
            {
                "title": "Supercar Cinematic",
                "prompt": "Cinematic vertical montage of an exotic supercar at night, low camera angle, headlights flare, glossy body reflections, fast rolling shot, premium commercial look, strongest motion first.",
                "searches": [
                    "supercar driving cinematic",
                    "exotic sports car night",
                    "luxury car rolling shot",
                    "sports car cinematic"
                ],
            },
            {
                "title": "Exotic Car Details",
                "prompt": "Macro cinematic details of an exotic car: carbon fiber, wheel, brake caliper, headlight and glossy paint, dramatic reflections, premium studio look, fast precise cuts.",
                "searches": [
                    "supercar detail close up",
                    "luxury car detail",
                    "sports car wheel close up",
                    "exotic car close up"
                ],
            },
            {
                "title": "Luxury Car Interior",
                "prompt": "Premium exotic car interior montage with steering wheel, digital cockpit, leather stitching and ambient lighting, shallow depth of field, clean cinematic motion, immediate visual hook.",
                "searches": [
                    "luxury car interior close up",
                    "sports car interior",
                    "supercar cockpit",
                    "car interior cinematic"
                ],
            },
        ],
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

    weighted = []
    for topic, score in scores.items():
        # Every niche stays active, while current YouTube signals influence frequency.
        weighted.extend([topic] * max(2, min(10, score + 2)))

    return random.choice(weighted or list(CONTENT)), scores


def choose_concept(topic):
    return random.choice(CONTENT[topic]["concepts"])


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
        low_res_penalty = 0 if min(w, h) >= 720 else 10
        target_penalty = abs((w or 720) - 1080) / 1000
        return portrait_penalty + low_res_penalty + target_penalty

    return sorted(files, key=rank)[0]


def collect_candidates(concept):
    candidates = []
    seen_ids = set()

    for query_index, query in enumerate(concept["searches"]):
        try:
            videos = search_pexels(query)
        except Exception:
            continue

        for rank_index, video in enumerate(videos):
            video_id = video.get("id")
            if not video_id or video_id in seen_ids:
                continue

            file_info = choose_file(video)
            if not file_info or not file_info.get("link"):
                continue

            duration = float(video.get("duration") or 0)
            if duration and duration < 2.5:
                continue

            seen_ids.add(video_id)
            candidates.append({
                "file": file_info,
                "video": video,
                "query_index": query_index,
                "rank_index": rank_index,
            })

        if len(candidates) >= 16:
            break

    return candidates


def download_clips(concept, work, wanted=4):
    candidates = collect_candidates(concept)
    if len(candidates) < 3:
        raise RuntimeError("Not enough suitable Pexels videos found for the creative prompt.")

    # The hook comes from the closest search to the prompt and from the top results.
    exact = [c for c in candidates if c["query_index"] == 0]
    hook_pool = exact[:3] if exact else candidates[:3]
    hook = random.choice(hook_pool)

    remaining = [
        c for c in candidates
        if c["video"].get("id") != hook["video"].get("id")
    ]
    remaining.sort(key=lambda c: (c["query_index"], c["rank_index"]))

    # Keep the rest highly relevant, with a little variety.
    body_pool = remaining[:12]
    if len(body_pool) > wanted - 1:
        body = random.sample(body_pool, wanted - 1)
    else:
        body = body_pool[: wanted - 1]

    selected = [hook] + body
    paths = []
    credits = []

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

    # Skip stock-footage setup and start where action is likely already happening.
    low = 0.30 if hook else 0.18
    high = 0.62 if hook else 0.55
    start = duration * random.uniform(low, high)
    return max(0.0, min(start, duration - seconds - 0.15))


def normalize_clip(src, dst, seconds, hook=False):
    start = action_start(src, seconds, hook)
    video_filter = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,fps=30,format=yuv420p"
    )

    base = ["ffmpeg", "-y", "-ss", f"{start:.2f}", "-i", str(src)]

    if has_audio(src):
        run(base + [
            "-t", f"{seconds:.2f}",
            "-vf", video_filter,
            "-af", "volume=1.08,alimiter=limit=0.95",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart",
            str(dst)
        ])
    else:
        run(base + [
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", f"{seconds:.2f}",
            "-map", "0:v:0", "-map", "1:a:0",
            "-vf", video_filter,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
            "-shortest", "-movflags", "+faststart",
            str(dst)
        ])


def make_video(clips, topic, work):
    low, high = CONTENT[topic]["duration"]
    target_duration = random.randint(low, high)

    # Make the opening visual change quickly to reduce swipe-away.
    hook_seconds = random.uniform(1.7, 2.4)
    body_total = max(1.0, target_duration - hook_seconds)
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
    concept = choose_concept(topic)

    title = concept["title"]
    hashtags = CONTENT[topic]["hashtags"]

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)

        clips, credits = download_clips(concept, work, wanted=4)
        final, duration = make_video(clips, topic, work)

        credit_lines = [
            f"Footage by {credit['name']} on Pexels: {credit['url']}"
            for credit in credits
        ]

        description = (
            f"{title}. Original prompt-directed vertical edit using licensed stock footage. "
            "No trending video is copied.\n\n"
            + "\n".join(credit_lines)
            + "\n\nPhotos/videos provided by Pexels.\n\n"
            + " ".join(hashtags)
        )

        tags = [tag.lstrip("#") for tag in hashtags] + [
            topic.replace("_", " "),
            title,
            "satisfying",
            "shorts"
        ]

        video_id = upload(yt_upload, final, title, description, tags)

    print(json.dumps({
        "status": "uploaded",
        "video_id": video_id,
        "topic": topic,
        "title": title,
        "creative_prompt": concept["prompt"],
        "searches": concept["searches"],
        "duration_seconds": duration,
        "region": REGION_CODE,
        "privacy": YOUTUBE_PRIVACY,
        "trend_scores": scores
    }, indent=2))


if __name__ == "__main__":
    main()

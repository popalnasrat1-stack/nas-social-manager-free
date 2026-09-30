import os, json, base64, random, subprocess, tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import requests

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

REGION_CODE = os.getenv("REGION_CODE", "AE").upper()
YOUTUBE_PRIVACY = os.getenv("YOUTUBE_PRIVACY", "private")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY", "")
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
        "duration": (9, 13),
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
        "duration": (9, 13),
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
        "duration": (9, 13),
        "concepts": [
            {
                "title": "Dragon Fruit Cutting ASMR",
                "prompt": "Macro ASMR shot of a chilled dragon fruit being sliced open with a razor-sharp knife, vivid pink skin and white seeded flesh, clean cutting sounds, black background, immediate first cut.",
                "searches": [
                    "knife cutting dragon fruit close up",
                    "dragon fruit sliced with knife",
                    "pitaya cutting close up",
                    "fruit knife cutting macro"
                ],
            },
            {
                "title": "Mango Cutting ASMR",
                "prompt": "Juicy ripe mango cut into perfect cubes in extreme close-up, glossy golden flesh, clean knife work, bright studio lighting, satisfying first cut immediately.",
                "searches": [
                    "knife cutting mango close up",
                    "mango sliced with knife",
                    "mango cubes knife cutting",
                    "fruit knife cutting macro"
                ],
            },
            {
                "title": "Pineapple Cutting ASMR",
                "prompt": "Extreme close-up of a ripe pineapple being peeled and sliced with fast precise knife work, bright yellow texture, crisp satisfying cuts, action starts in the first frame.",
                "searches": [
                    "knife cutting pineapple close up",
                    "pineapple sliced with knife",
                    "pineapple peeling knife close up",
                    "fruit knife cutting macro"
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
        "duration": (12, 16),
        "concepts": [
            {
                "title": "Supercar Night Run",
                "prompt": "Cinematic vertical rolling shot of an exotic supercar moving at night, low camera angle, headlights and glossy reflections, wheel motion, immediate speed in frame one, premium commercial look.",
                "searches": [
                    "supercar driving road night",
                    "exotic sports car driving",
                    "supercar rolling shot",
                    "sports car driving cinematic"
                ],
            },
            {
                "title": "Exotic Car Rolling Shots",
                "prompt": "Fast cinematic vertical montage of an exotic sports car in motion, tracking shot, spinning wheels, road reflections, low angles, immediate movement, no parked-car setup.",
                "searches": [
                    "exotic car driving road",
                    "sports car rolling shot",
                    "luxury car driving cinematic",
                    "supercar moving road"
                ],
            },
            {
                "title": "Luxury Sports Car Cinematic",
                "prompt": "Premium vertical sports-car commercial with a luxury performance car actively driving, dramatic road, close moving angles, reflections across the bodywork and fast clean cuts.",
                "searches": [
                    "luxury sports car driving",
                    "performance car driving cinematic",
                    "supercar highway driving",
                    "sports car road cinematic"
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


def trend_scores(titles):
    joined = " ".join(titles).lower()
    return {
        topic: sum(joined.count(k) for k in data["trend_keywords"])
        for topic, data in CONTENT.items()
    }


def choose_scheduled_concept():
    """
    Aggressive satisfying-only mode.
    Twelve daily slots focus the channel on one audience instead of mixing niches.
    Rotation: 5 color-mixing, 4 fruit-cutting, 3 visual-ASMR Shorts per day.
    Exotic cars stay in the library but are paused from automatic publishing.
    """
    now = datetime.now(timezone.utc)
    slot = now.hour // 2
    day = now.toordinal()

    daily_rotation = [
        "color_mixing",
        "exotic_fruit",
        "asmr",
        "color_mixing",
        "exotic_fruit",
        "color_mixing",
        "asmr",
        "exotic_fruit",
        "color_mixing",
        "exotic_fruit",
        "color_mixing",
        "asmr",
    ]
    topic = daily_rotation[slot % len(daily_rotation)]

    concepts = CONTENT[topic]["concepts"]
    occurrence = day * 12 + slot
    concept = concepts[occurrence % len(concepts)]
    return topic, concept


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pricing_numbers(obj, inside_pricing=False):
    """
    Collect explicit numeric pricing/cost values conservatively.
    A model is treated as free only when the catalog explicitly advertises
    pricing and every advertised numeric price is zero.
    """
    values = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_low = str(key).lower()
            child_pricing = inside_pricing or any(
                word in key_low for word in ("price", "pricing", "cost")
            )
            if isinstance(value, (dict, list)):
                values.extend(_pricing_numbers(value, child_pricing))
                continue

            number = _number(value)
            if number is None:
                continue

            # Include all numbers inside pricing/cost objects, plus common
            # model-registry billing keys such as completionVideoSeconds.
            if child_pricing or any(
                word in key_low
                for word in (
                    "completionvideo", "videoseconds", "video_seconds",
                    "persecond", "per_second", "completionimage"
                )
            ):
                values.append(number)
    elif isinstance(obj, list):
        for item in obj:
            values.extend(_pricing_numbers(item, inside_pricing))
    return values


def free_pollinations_video_models():
    """
    Discover the live Pollinations video catalog and return only models that
    explicitly advertise zero pricing. If none are free, AI generation is
    skipped so the workflow cannot unexpectedly spend paid Pollen.
    """
    if not POLLINATIONS_API_KEY:
        return []

    try:
        response = requests.get(
            "https://gen.pollinations.ai/video/models",
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        print(f"Pollinations model discovery failed: {exc}")
        return []

    if isinstance(payload, dict):
        models = payload.get("data") or payload.get("models") or []
    elif isinstance(payload, list):
        models = payload
    else:
        models = []

    free_models = []
    for model in models:
        if not isinstance(model, dict):
            continue

        model_id = model.get("id") or model.get("model") or model.get("name")
        if not model_id:
            continue

        prices = _pricing_numbers(model)
        if not prices:
            # No explicit price => do not assume free.
            continue
        if any(price > 0 for price in prices):
            continue

        reliability = str(model.get("reliability") or "").lower()
        free_models.append((0 if reliability == "reliable" else 1, str(model_id)))

    free_models.sort()
    return [model_id for _, model_id in free_models]


def _save_pollinations_response(response, output):
    content_type = (response.headers.get("content-type") or "").lower()

    if "video/" in content_type or "application/octet-stream" in content_type:
        output.write_bytes(response.content)
        return output if output.stat().st_size > 10000 else None

    try:
        payload = response.json()
    except Exception:
        return None

    data = payload.get("data") if isinstance(payload, dict) else None
    item = data[0] if isinstance(data, list) and data else payload
    if not isinstance(item, dict):
        return None

    if item.get("b64_json"):
        try:
            output.write_bytes(base64.b64decode(item["b64_json"]))
            return output if output.stat().st_size > 10000 else None
        except Exception:
            return None

    media_url = item.get("url")
    if media_url:
        try:
            with requests.get(media_url, stream=True, timeout=180) as media:
                media.raise_for_status()
                with open(output, "wb") as handle:
                    for chunk in media.iter_content(1024 * 1024):
                        if chunk:
                            handle.write(chunk)
            return output if output.stat().st_size > 10000 else None
        except Exception:
            return None

    return None


def generate_pollinations_clip(prompt, work):
    """
    Try free Pollinations video generation first. The live model catalog decides
    which zero-price model is used. Generation failure never stops the channel;
    the caller falls back to Pexels.
    """
    models = free_pollinations_video_models()
    if not models:
        print("No explicitly free Pollinations video model is available; using Pexels fallback.")
        return None, None

    endpoint = "https://gen.pollinations.ai/video/" + quote(prompt, safe="")
    headers = {"Authorization": f"Bearer {POLLINATIONS_API_KEY}"}

    for index, model_id in enumerate(models[:4], start=1):
        output = work / f"pollinations_{index}.mp4"
        try:
            response = requests.get(
                endpoint,
                headers=headers,
                params={
                    "model": model_id,
                    "duration": 4,
                    "aspectRatio": "9:16",
                },
                timeout=330,
            )
            if response.status_code != 200:
                print(f"Pollinations model {model_id} returned HTTP {response.status_code}.")
                continue

            saved = _save_pollinations_response(response, output)
            if saved and media_duration(saved) > 0:
                print(f"Using free Pollinations AI video model: {model_id}")
                return saved, model_id
        except Exception as exc:
            print(f"Pollinations model {model_id} failed: {exc}")

    print("Free Pollinations generation failed; using Pexels fallback.")
    return None, None


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
    hook = exact[0] if exact else candidates[0]

    remaining = [
        c for c in candidates
        if c["video"].get("id") != hook["video"].get("id")
    ]
    remaining.sort(key=lambda c: (c["query_index"], c["rank_index"]))

    # Keep the rest highly relevant, with a little variety.
    body_pool = remaining[:10]
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


def make_vibe_audio(topic, duration, work):
    """
    Create an original low-volume sound bed with FFmpeg.
    It is synthesized inside this workflow rather than downloaded from a song library.
    Stock-clip audio is kept when it exists, so cutting/engine sounds can still come through.
    """
    profiles = {
        "asmr": {"freq": 174, "noise": "pink", "amp": 0.010, "mix": 0.22},
        "color_mixing": {"freq": 220, "noise": "pink", "amp": 0.011, "mix": 0.20},
        "exotic_fruit": {"freq": 330, "noise": "white", "amp": 0.007, "mix": 0.17},
        "exotic_cars": {"freq": 55, "noise": "brown", "amp": 0.013, "mix": 0.28},
    }
    p = profiles[topic]
    out = work / "vibe.m4a"
    fade_out = max(0.0, duration - 0.45)

    run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i",
        f"sine=frequency={p['freq']}:sample_rate=44100:duration={duration}",
        "-f", "lavfi", "-i",
        f"anoisesrc=color={p['noise']}:amplitude={p['amp']}:sample_rate=44100:duration={duration}",
        "-filter_complex",
        (
            "[0:a]volume=0.035,lowpass=f=1200[tone];"
            "[1:a]highpass=f=80,lowpass=f=6500[noise];"
            "[tone][noise]amix=inputs=2:duration=longest:normalize=0,"
            f"afade=t=in:st=0:d=0.20,afade=t=out:st={fade_out:.2f}:d=0.45,"
            "alimiter=limit=0.80[a]"
        ),
        "-map", "[a]",
        "-c:a", "aac", "-b:a", "128k",
        str(out)
    ])
    return out, p["mix"]


def make_video(clips, topic, work):
    low, high = CONTENT[topic]["duration"]
    target_duration = random.randint(low, high)

    # Aggressive retention structure:
    # 0.7–1.0s hook -> two satisfying shots -> repeat hook at the end.
    # Repeating the opening shot helps the Short loop naturally.
    hook_seconds = random.uniform(0.70, 1.00)
    body_total = max(2.0, target_duration - (hook_seconds * 2))
    body_seconds = body_total / max(1, len(clips) - 1)

    normalized = []
    for index, src in enumerate(clips, start=1):
        seconds = hook_seconds if index == 1 else body_seconds
        dst = work / f"clip_{index}.mp4"
        normalize_clip(src, dst, seconds, hook=(index == 1))
        normalized.append(dst)

    # Finish on the same visual hook used at the start so replay feels continuous.
    sequence = normalized + [normalized[0]]

    concat_file = work / "concat.txt"
    concat_file.write_text(
        "\n".join(f"file '{path.as_posix()}'" for path in sequence),
        encoding="utf-8"
    )

    visual = work / "visual.mp4"
    run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-t", str(target_duration),
        "-c", "copy",
        "-movflags", "+faststart",
        str(visual)
    ])

    vibe, vibe_mix = make_vibe_audio(topic, target_duration, work)
    final = work / "final.mp4"
    run([
        "ffmpeg", "-y",
        "-i", str(visual),
        "-i", str(vibe),
        "-filter_complex",
        (
            "[0:a]volume=1.0[original];"
            f"[1:a]volume={vibe_mix:.2f}[bed];"
            "[original][bed]amix=inputs=2:duration=first:normalize=0,"
            "alimiter=limit=0.95[a]"
        ),
        "-map", "0:v:0",
        "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "160k",
        "-shortest", "-movflags", "+faststart",
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
    scores = trend_scores(current_titles)
    topic, concept = choose_scheduled_concept()

    title = concept["title"]
    hashtags = CONTENT[topic]["hashtags"]

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)

        ai_clip, ai_model = generate_pollinations_clip(concept["prompt"], work)

        if ai_clip:
            # Sample three different moments from the AI clip, then build a replay-friendly loop.
            clips = [ai_clip, ai_clip, ai_clip]
            credits = []
            source_type = "pollinations_ai"
        else:
            clips, credits = download_clips(concept, work, wanted=3)
            source_type = "pexels"

        final, duration = make_video(clips, topic, work)

        if source_type == "pollinations_ai":
            description = (
                f"{title}. Original prompt-directed AI visual generated through Pollinations "
                f"using model {ai_model}. The background sound bed is generated inside this workflow.\n\n"
                + " ".join(hashtags)
            )
        else:
            credit_lines = [
                f"Footage by {credit['name']} on Pexels: {credit['url']}"
                for credit in credits
            ]
            description = (
                f"{title}. Original prompt-directed vertical edit using licensed stock footage. "
                "No trending video is copied. The background sound bed is generated inside the workflow; "
                "original stock-clip audio is kept when available.\n\n"
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
        "source": source_type,
        "pollinations_model": ai_model,
        "searches": concept["searches"],
        "duration_seconds": duration,
        "region": REGION_CODE,
        "privacy": YOUTUBE_PRIVACY,
        "trend_scores": scores
    }, indent=2))


if __name__ == "__main__":
    main()

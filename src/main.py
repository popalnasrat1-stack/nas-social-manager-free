import os, json, base64, random, subprocess, tempfile, time, re
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
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
TOKEN_B64 = os.getenv("YOUTUBE_TOKEN_B64", "")

# Prompt-first creative system.
# Each Short starts with a controlled visual prompt, tries AI video first,
# automatically rejects weak generations, and falls back to licensed stock footage
# so the publishing schedule stays reliable.
CONTENT = {
    "asmr": {
        "trend_keywords": ["asmr", "satisfying", "oddly satisfying", "soap", "sand", "slime", "texture", "macro"],
        "hashtags": ["#Shorts", "#ASMR", "#Satisfying", "#OddlySatisfying"],
        "duration": (8, 11),
        "concepts": [
            {
                "title": "The Cleanest Soap Cut",
                "prompt": "Extreme macro of a bright crisp soap block already being shaved into thin perfect curls in frame one, razor-clean edges, vivid texture, tiny fragments falling, premium studio light, no setup, continuous satisfying motion, seamless replay ending.",
                "searches": [
                    "soap cutting satisfying close up",
                    "soap shaving macro",
                    "soap slicing asmr",
                    "oddly satisfying soap"
                ],
            },
            {
                "title": "Perfect Kinetic Sand Slice",
                "prompt": "Macro kinetic sand already under the blade in frame one, one impossibly clean slice followed by smooth compression, sharp geometric edges, rich texture, high contrast, hypnotic continuous motion, no hands blocking the action.",
                "searches": [
                    "kinetic sand cutting satisfying",
                    "kinetic sand slicing close up",
                    "sand cutting asmr",
                    "oddly satisfying sand"
                ],
            },
            {
                "title": "Glossy Slime Fold ASMR",
                "prompt": "Ultra-close glossy slime fold with a large bubble stretching and collapsing smoothly, action already happening at frame one, reflective texture, clean background, slow elastic movement, satisfying visual payoff before the loop.",
                "searches": [
                    "slime satisfying close up",
                    "slime stretching macro",
                    "glossy slime asmr",
                    "slime bubble satisfying"
                ],
            },
            {
                "title": "Perfect Texture Loop",
                "prompt": "Extreme macro visual ASMR of a glossy soft material being pressed into a perfect repeating pattern, immediate motion, clean symmetry, tactile detail, stable camera, strong first-frame texture, loop ending matches the opening.",
                "searches": [
                    "oddly satisfying texture close up",
                    "satisfying pressing macro",
                    "visual asmr close up",
                    "satisfying texture loop"
                ],
            },
        ],
    },
    "color_mixing": {
        "trend_keywords": ["paint", "painting", "color", "colour", "mixing", "art", "palette", "acrylic", "pour"],
        "hashtags": ["#Shorts", "#ColorMixing", "#ASMR", "#Art", "#Satisfying"],
        "duration": (8, 11),
        "concepts": [
            {
                "title": "Watch These Colors Transform",
                "prompt": "Extreme macro of cobalt blue and pearl white thick paint already folding together under a steel palette knife in frame one, dramatic color contrast, glossy ridges, fast first transformation, then smooth controlled blending into a clean icy blue.",
                "searches": [
                    "paint mixing palette knife close up",
                    "blue white paint mixing satisfying",
                    "palette knife paint macro",
                    "acrylic paint mixing close up"
                ],
            },
            {
                "title": "Neon Paint Scrape",
                "prompt": "Macro neon magenta and electric yellow acrylic paint scraped together in one clean palette-knife pass, immediate high-contrast motion, thick glossy paint, vivid orange gradient reveal, premium studio lighting, no setup.",
                "searches": [
                    "neon paint mixing",
                    "acrylic paint scrape close up",
                    "bright color mixing paint",
                    "palette knife satisfying paint"
                ],
            },
            {
                "title": "Gold and Black Paint Blend",
                "prompt": "Extreme macro metallic gold and deep black paint being folded together from the first frame, reflective metallic streaks, luxurious glossy ridges, strong contrast, slow controlled palette-knife movement, dramatic satisfying reveal.",
                "searches": [
                    "gold black paint mixing",
                    "metallic paint mixing close up",
                    "palette knife gold paint",
                    "paint texture macro"
                ],
            },
            {
                "title": "Rainbow Acrylic Pour",
                "prompt": "Vertical macro acrylic pour with bright cyan, magenta, yellow and white already flowing together in frame one, clean marbling, smooth liquid motion, vivid high-contrast color cells, no empty setup, beautiful loopable finish.",
                "searches": [
                    "acrylic pour close up",
                    "fluid art paint pouring",
                    "rainbow paint pour",
                    "color pour satisfying"
                ],
            },
        ],
    },
    "exotic_fruit": {
        "trend_keywords": ["fruit", "food", "cutting", "mango", "pineapple", "pomegranate", "dragon fruit", "tropical"],
        "hashtags": ["#Shorts", "#FruitCutting", "#ASMR", "#Satisfying", "#Food"],
        "duration": (8, 11),
        "concepts": [
            {
                "title": "Dragon Fruit Reveal",
                "prompt": "Macro chilled dragon fruit with the blade already entering the vivid pink skin in frame one, one clean cut revealing bright white seeded flesh immediately, juicy texture, black background, tight framing, satisfying reveal and loop.",
                "searches": [
                    "dragon fruit cutting close up",
                    "pitaya slicing knife",
                    "dragon fruit sliced macro",
                    "exotic fruit cutting"
                ],
            },
            {
                "title": "Perfect Mango Cubes",
                "prompt": "Extreme close-up ripe mango already being scored into perfect cubes in frame one, glossy golden flesh, crisp knife motion, then the mango cheek flips outward for an instant geometric reveal, bright studio light.",
                "searches": [
                    "mango cutting cubes close up",
                    "mango slicing knife macro",
                    "mango hedgehog cut",
                    "fruit cutting satisfying"
                ],
            },
            {
                "title": "Pineapple Spiral Cut",
                "prompt": "Macro ripe pineapple being peeled and spiral-cut with precise knife work already underway in frame one, bright yellow flesh, crisp texture, fast satisfying transformation, tight close-up, no setup.",
                "searches": [
                    "pineapple cutting close up",
                    "pineapple peeling knife",
                    "pineapple slicing satisfying",
                    "fruit knife cutting macro"
                ],
            },
            {
                "title": "Pomegranate Reveal",
                "prompt": "Extreme macro pomegranate already being opened in frame one, clean knife score then instant reveal of glossy ruby seeds, rich color contrast, juicy texture, controlled hands, premium food-film lighting.",
                "searches": [
                    "pomegranate cutting close up",
                    "pomegranate opening",
                    "pomegranate seeds macro",
                    "fruit cutting close up"
                ],
            },
        ],
    },
    "exotic_cars": {
        "trend_keywords": ["car", "cars", "supercar", "sports car", "luxury car", "automotive", "engine"],
        "hashtags": ["#Shorts", "#Supercars", "#ExoticCars", "#Cars"],
        "duration": (10, 13),
        "concepts": [
            {
                "title": "Supercar Night Run",
                "prompt": "Cinematic vertical rolling shot of an exotic supercar already moving fast in frame one at night, low camera angle, headlights and glossy reflections, strong wheel motion, premium commercial look.",
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



def media_dimensions(path):
    try:
        out = run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json", str(path)
        ])
        streams = json.loads(out).get("streams", [])
        if not streams:
            return 0, 0
        return int(streams[0].get("width") or 0), int(streams[0].get("height") or 0)
    except Exception:
        return 0, 0


def video_quality_check(path, label="video"):
    """
    Fast automatic gate before an AI clip can be uploaded.
    Rejects broken, tiny, extremely short, or mostly frozen generations.
    """
    duration = media_duration(path)
    width, height = media_dimensions(path)
    size = path.stat().st_size if Path(path).exists() else 0
    reasons = []

    if duration < 3.0:
        reasons.append(f"too short ({duration:.1f}s)")
    if max(width, height) < 720 or min(width, height) < 400:
        reasons.append(f"low resolution ({width}x{height})")
    if size < 150_000:
        reasons.append(f"tiny file ({size} bytes)")

    # Detect long frozen sections. This is deliberately forgiving because
    # macro ASMR can have slow motion, but a nearly static AI generation is poor for Shorts.
    try:
        probe = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-i", str(path),
                "-vf", "freezedetect=n=-45dB:d=2.0",
                "-an", "-f", "null", "-"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=90,
        )
        freezes = [
            float(x) for x in re.findall(r"freeze_duration:\s*([0-9.]+)", probe.stderr)
        ]
        if duration > 0 and freezes and max(freezes) > duration * 0.72:
            reasons.append(f"mostly frozen ({max(freezes):.1f}s)")
    except Exception:
        pass

    ok = not reasons
    print(json.dumps({
        "quality_gate": label,
        "passed": ok,
        "duration": round(duration, 2),
        "resolution": f"{width}x{height}",
        "file_bytes": size,
        "reasons": reasons,
    }))
    return ok


def build_ai_prompts(topic, concept):
    """
    Produce two tightly controlled prompt variants. The second is only used
    when the first AI result fails the automatic quality gate.
    """
    topic_direction = {
        "asmr": (
            "ultra-real tactile material physics, crisp texture detail, deliberate satisfying motion, "
            "single clear action already happening in frame one"
        ),
        "color_mixing": (
            "thick glossy pigment with realistic viscosity, clean steel palette-knife movement, "
            "rich micro-texture, smooth continuous folding motion"
        ),
        "exotic_fruit": (
            "photoreal fresh fruit texture, believable knife geometry and hand anatomy, juicy clean slice, "
            "the blade already making contact in frame one"
        ),
        "exotic_cars": (
            "premium automotive commercial realism, moving reflections, stable tracking motion, "
            "clean body geometry and natural wheel movement"
        ),
    }[topic]

    common = (
        "Vertical 9:16 premium cinematic macro video. "
        "Keep the main subject large and centered in the safe area. "
        "Immediate action, no intro, no setup, no dead frames. "
        "Smooth stable camera, shallow depth of field, controlled studio lighting, high detail, "
        + topic_direction + ". "
        "No text, captions, logos, watermark, UI, duplicate objects, warped anatomy, malformed hands, "
        "bent knife, melting geometry, visual flicker, jump cuts, camera shake, heavy motion blur, "
        "overexposure, underexposure, or cluttered background. "
    )

    return [
        common + concept["prompt"] + " One continuous polished shot with realistic physics and a clean ending.",
        common + concept["prompt"] + " Alternate take: tighter macro framing, stronger texture contrast, smoother motion, premium product-film finish.",
    ]


def polished_title(topic, concept):
    now = datetime.now(timezone.utc)
    slot = now.hour // 2
    variants = {
        "asmr": [
            concept["title"],
            "Oddly Satisfying ASMR Close-Up",
            "Perfect Texture ASMR",
            "This Cut Is Too Satisfying",
        ],
        "color_mixing": [
            concept["title"],
            "Perfect Paint Blend",
            "Glossy Color Mixing ASMR",
            "Watch These Colors Melt Together",
        ],
        "exotic_fruit": [
            concept["title"],
            "Perfect Fruit Slice ASMR",
            "The Cleanest Fruit Cut",
            "Satisfying Tropical Fruit Slice",
        ],
        "exotic_cars": [
            concept["title"],
            "Supercar Detail in Motion",
            "Luxury Car Cinematic",
            "Pure Supercar Detail",
        ],
    }[topic]
    return variants[(now.toordinal() * 12 + slot) % len(variants)]


def write_token():
    if not TOKEN_B64:
        raise RuntimeError("YOUTUBE_TOKEN_B64 secret is missing.")

    legacy = base64.b64decode(TOKEN_B64).decode("utf-8")
    encrypted_path = Path("youtube_token_encrypted.txt")

    if encrypted_path.exists():
        try:
            import hashlib
            from cryptography.fernet import Fernet

            legacy_payload = json.loads(legacy)
            client_secret = str(legacy_payload.get("client_secret") or "").strip()
            if not client_secret:
                raise RuntimeError("Existing YouTube OAuth configuration has no client_secret.")

            key = base64.urlsafe_b64encode(
                hashlib.sha256(client_secret.encode("utf-8")).digest()
            )
            encrypted = encrypted_path.read_text(encoding="utf-8").strip()
            token = Fernet(key).decrypt(encrypted.encode("ascii")).decode("utf-8")
            Path("youtube_token.json").write_text(token, encoding="utf-8")
            print("Using refreshed encrypted YouTube authorization.")
            return
        except Exception as exc:
            raise RuntimeError(f"Could not decrypt refreshed YouTube authorization: {exc}")

    Path("youtube_token.json").write_text(legacy, encoding="utf-8")


def youtube_upload_client():
    write_token()
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = Credentials.from_authorized_user_file("youtube_token.json", scopes)
    try:
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
    except Exception as exc:
        if "invalid_grant" in str(exc).lower() or "expired or revoked" in str(exc).lower():
            raise RuntimeError(
                "YouTube authorization expired or was revoked. Run the YouTube Authorization workflow to reconnect the channel."
            ) from exc
        raise
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
        print("No explicitly free Pollinations video model is available; trying next source.")
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

    print("Free Pollinations generation failed; trying next source.")
    return None, None


def _download_url_to_file(url, output, timeout=180):
    try:
        with requests.get(url, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            with open(output, "wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        if output.exists() and output.stat().st_size > 10000 and media_duration(output) > 0:
            return output
    except Exception as exc:
        print(f"Media download failed: {exc}")
    return None


def _replicate_output_url(output):
    if isinstance(output, str) and output.startswith("http"):
        return output
    if isinstance(output, list):
        for item in output:
            url = _replicate_output_url(item)
            if url:
                return url
    if isinstance(output, dict):
        for key in ("url", "video", "output"):
            if key in output:
                url = _replicate_output_url(output[key])
                if url:
                    return url
    return None


def generate_replicate_clip(prompt, work):
    """
    Second AI fallback using Replicate's current Try-for-Free video model.
    Replicate's free trial is limited. If the account has no purchased credit,
    exhausted trial access should fail and the workflow falls back to Pexels.
    """
    if not REPLICATE_API_TOKEN:
        return None, None

    model_id = "minimax/video-01"
    endpoint = "https://api.replicate.com/v1/models/minimax/video-01/predictions"
    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
        "Cancel-After": "7m",
    }

    # MiniMax text-to-video does not expose a native aspect-ratio input here,
    # so the prompt keeps the important action centered for a later 9:16 crop.
    ai_prompt = (
        "Portrait vertical composition, subject centered, extreme close-up, "
        "important action kept in the center safe area for a 9:16 crop. "
        + prompt
    )

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json={
                "input": {
                    "prompt": ai_prompt,
                    "prompt_optimizer": True,
                }
            },
            timeout=45,
        )
    except Exception as exc:
        print(f"Replicate request failed: {exc}")
        return None, None

    if response.status_code not in (200, 201):
        detail = response.text[:500].replace("\n", " ")
        print(
            f"Replicate free-trial request unavailable "
            f"(HTTP {response.status_code}): {detail}"
        )
        return None, None

    try:
        prediction = response.json()
    except Exception:
        print("Replicate returned a non-JSON prediction response.")
        return None, None

    get_url = (prediction.get("urls") or {}).get("get")
    prediction_id = prediction.get("id")
    if not get_url and prediction_id:
        get_url = f"https://api.replicate.com/v1/predictions/{prediction_id}"

    deadline = time.time() + 390
    while prediction.get("status") not in ("succeeded", "failed", "canceled") and time.time() < deadline:
        if not get_url:
            break
        time.sleep(5)
        try:
            poll = requests.get(
                get_url,
                headers={"Authorization": f"Bearer {REPLICATE_API_TOKEN}"},
                timeout=30,
            )
            if poll.status_code != 200:
                print(f"Replicate polling returned HTTP {poll.status_code}.")
                return None, None
            prediction = poll.json()
        except Exception as exc:
            print(f"Replicate polling failed: {exc}")
            return None, None

    if prediction.get("status") != "succeeded":
        err = prediction.get("error") or "prediction did not complete"
        print(f"Replicate generation unavailable: {err}")
        return None, None

    media_url = _replicate_output_url(prediction.get("output"))
    if not media_url:
        print("Replicate succeeded but returned no downloadable video URL.")
        return None, None

    output = work / "replicate_ai.mp4"
    saved = _download_url_to_file(media_url, output, timeout=180)
    if saved:
        print(f"Using Replicate Try-for-Free AI video model: {model_id}")
        return saved, model_id

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
        "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,"
        "crop=1080:1920,"
        "eq=contrast=1.035:saturation=1.06:brightness=0.005,"
        "unsharp=5:5:0.28:5:5:0.0,"
        "fps=30,format=yuv420p"
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
    Generate a subtle original sound bed inside FFmpeg.
    Profiles are tuned to support the visual instead of sounding like a generic tone.
    """
    profiles = {
        "asmr": {"base": 174, "air": 720, "noise": "pink", "amp": 0.008, "mix": 0.18},
        "color_mixing": {"base": 196, "air": 520, "noise": "pink", "amp": 0.009, "mix": 0.17},
        "exotic_fruit": {"base": 246, "air": 980, "noise": "white", "amp": 0.006, "mix": 0.16},
        "exotic_cars": {"base": 55, "air": 165, "noise": "brown", "amp": 0.011, "mix": 0.22},
    }
    p = profiles[topic]
    out = work / "vibe.m4a"
    fade_out = max(0.0, duration - 0.35)

    run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i",
        f"sine=frequency={p['base']}:sample_rate=44100:duration={duration}",
        "-f", "lavfi", "-i",
        f"sine=frequency={p['air']}:sample_rate=44100:duration={duration}",
        "-f", "lavfi", "-i",
        f"anoisesrc=color={p['noise']}:amplitude={p['amp']}:sample_rate=44100:duration={duration}",
        "-filter_complex",
        (
            "[0:a]volume=0.025,lowpass=f=900[base];"
            "[1:a]volume=0.009,highpass=f=180,lowpass=f=2400[air];"
            "[2:a]highpass=f=90,lowpass=f=7000[texture];"
            "[base][air][texture]amix=inputs=3:duration=longest:normalize=0,"
            f"afade=t=in:st=0:d=0.08,afade=t=out:st={fade_out:.2f}:d=0.35,"
            "alimiter=limit=0.82[a]"
        ),
        "-map", "[a]",
        "-c:a", "aac", "-b:a", "160k",
        str(out)
    ])
    return out, p["mix"]


def mix_final_audio(visual, topic, target_duration, work):
    vibe, vibe_mix = make_vibe_audio(topic, target_duration, work)
    final = work / "final.mp4"

    if has_audio(visual):
        run([
            "ffmpeg", "-y",
            "-i", str(visual),
            "-i", str(vibe),
            "-filter_complex",
            (
                "[0:a]highpass=f=45,volume=0.95[original];"
                f"[1:a]volume={vibe_mix:.2f}[bed];"
                "[original][bed]amix=inputs=2:duration=first:normalize=0,"
                "alimiter=limit=0.94[a]"
            ),
            "-map", "0:v:0", "-map", "[a]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart",
            str(final)
        ])
    else:
        run([
            "ffmpeg", "-y",
            "-i", str(visual),
            "-i", str(vibe),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(target_duration),
            "-shortest", "-movflags", "+faststart",
            str(final)
        ])

    return final


def make_ai_video(src, topic, work):
    """
    AI clips are treated as a continuous hero shot instead of three random crops.
    Preserve the strongest motion, polish it, then replay a short section to reach
    a Shorts-friendly length without turning the edit into a choppy montage.
    """
    low, high = CONTENT[topic]["duration"]
    target_duration = min(11, random.randint(low, high))
    src_duration = media_duration(src)
    usable = max(3.0, min(src_duration, 6.0))

    hero = work / "ai_hero.mp4"
    video_filter = (
        "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,"
        "crop=1080:1920,"
        "eq=contrast=1.04:saturation=1.07:brightness=0.004,"
        "unsharp=5:5:0.30:5:5:0.0,"
        "fps=30,format=yuv420p"
    )

    if has_audio(src):
        run([
            "ffmpeg", "-y", "-i", str(src),
            "-t", f"{usable:.2f}",
            "-vf", video_filter,
            "-af", "highpass=f=45,alimiter=limit=0.95",
            "-c:v", "libx264", "-preset", "fast", "-crf", "19",
            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart",
            str(hero)
        ])
    else:
        run([
            "ffmpeg", "-y", "-i", str(src),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", f"{usable:.2f}",
            "-map", "0:v:0", "-map", "1:a:0",
            "-vf", video_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "19",
            "-c:a", "aac", "-b:a", "160k",
            "-shortest", "-movflags", "+faststart",
            str(hero)
        ])

    # Repeat the polished hero shot rather than cutting to unrelated moments.
    # The final trim makes the ending land inside the same action family as frame one.
    looped = work / "visual.mp4"
    run([
        "ffmpeg", "-y",
        "-stream_loop", "2", "-i", str(hero),
        "-t", str(target_duration),
        "-c", "copy",
        "-movflags", "+faststart",
        str(looped)
    ])

    return mix_final_audio(looped, topic, target_duration, work), target_duration


def make_video(clips, topic, work):
    low, high = CONTENT[topic]["duration"]
    target_duration = random.randint(low, high)

    hook_seconds = random.uniform(0.65, 0.95)
    body_total = max(2.0, target_duration - (hook_seconds * 2))
    body_seconds = body_total / max(1, len(clips) - 1)

    normalized = []
    for index, src in enumerate(clips, start=1):
        seconds = hook_seconds if index == 1 else body_seconds
        dst = work / f"clip_{index}.mp4"
        normalize_clip(src, dst, seconds, hook=(index == 1))
        normalized.append(dst)

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

    return mix_final_audio(visual, topic, target_duration, work), target_duration


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

    title = polished_title(topic, concept)
    hashtags = CONTENT[topic]["hashtags"]

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)

        prompt_variants = build_ai_prompts(topic, concept)
        ai_clip = None
        ai_model = None
        source_type = None
        used_prompt = prompt_variants[0]

        # 1) Pollinations: only explicitly zero-price video models.
        for attempt, ai_prompt in enumerate(prompt_variants, start=1):
            candidate, model = generate_pollinations_clip(ai_prompt, work)
            if not candidate:
                break
            if video_quality_check(candidate, f"pollinations_attempt_{attempt}"):
                ai_clip, ai_model = candidate, model
                source_type = "pollinations_ai"
                used_prompt = ai_prompt
                break
            print(f"Pollinations attempt {attempt} failed quality gate.")

        # 2) Replicate Try-for-Free. Retry once only when a generated clip is poor.
        if not ai_clip:
            for attempt, ai_prompt in enumerate(prompt_variants, start=1):
                candidate, model = generate_replicate_clip(ai_prompt, work)
                if not candidate:
                    break
                if video_quality_check(candidate, f"replicate_attempt_{attempt}"):
                    ai_clip, ai_model = candidate, model
                    source_type = "replicate_ai"
                    used_prompt = ai_prompt
                    break
                print(f"Replicate attempt {attempt} failed quality gate.")

        # 3) Reliable licensed-stock fallback keeps the publishing schedule alive.
        if ai_clip:
            credits = []
            final, duration = make_ai_video(ai_clip, topic, work)
        else:
            clips, credits = download_clips(concept, work, wanted=3)
            source_type = "pexels"
            used_prompt = concept["prompt"]
            final, duration = make_video(clips, topic, work)

        if source_type in ("pollinations_ai", "replicate_ai"):
            provider = "Pollinations" if source_type == "pollinations_ai" else "Replicate"
            description = (
                f"{title}. Original prompt-directed AI visual generated through {provider} "
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
        "creative_prompt": used_prompt,
        "source": source_type,
        "ai_model": ai_model,
        "searches": concept["searches"],
        "duration_seconds": duration,
        "region": REGION_CODE,
        "privacy": YOUTUBE_PRIVACY,
        "trend_scores": scores
    }, indent=2))


if __name__ == "__main__":
    main()

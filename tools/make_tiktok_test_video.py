import json
import random
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import main as creator


TREND_URL = "https://ads.tiktok.com/creative/creativeCenter/trends?region=AE&period=7"

TOPIC_META = {
    "asmr": {
        "hooks": [
            "This texture is ridiculously satisfying",
            "Wait for the smoothest part",
            "Visual ASMR you will want to replay",
            "The last second loops perfectly",
        ],
        "description": "A clean visual ASMR moment made for a quick satisfying replay.",
        "hashtags": ["#ASMR", "#Satisfying", "#OddlySatisfying", "#VisualASMR", "#Relaxing"],
        "keywords": ["asmr", "satisfying", "texture", "slime", "soap", "sand"],
    },
    "color_mixing": {
        "hooks": [
            "Watch these colors melt together",
            "The blend at the end is too satisfying",
            "Perfect color mixing in seconds",
            "This paint blend deserves a replay",
        ],
        "description": "Glossy color mixing with a smooth close-up blend and satisfying finish.",
        "hashtags": ["#ColorMixing", "#PaintMixing", "#ArtTok", "#Satisfying", "#ASMR"],
        "keywords": ["color", "colour", "paint", "art", "mixing", "acrylic"],
    },
    "exotic_fruit": {
        "hooks": [
            "The cleanest fruit cut you will see today",
            "Wait until this fruit opens",
            "That first slice is so satisfying",
            "Perfect tropical fruit cutting ASMR",
        ],
        "description": "A crisp close-up fruit cut with bright texture and a satisfying reveal.",
        "hashtags": ["#FruitCutting", "#FoodTok", "#Satisfying", "#ASMR", "#TropicalFruit"],
        "keywords": ["fruit", "food", "mango", "pineapple", "dragonfruit", "tropical"],
    },
    "exotic_cars": {
        "hooks": [
            "This supercar shot is pure cinema",
            "One clean supercar moment",
            "The reflections make this shot",
            "Luxury in motion",
        ],
        "description": "A tight cinematic supercar moment with motion, reflections, and clean detail.",
        "hashtags": ["#Supercar", "#CarTok", "#ExoticCars", "#LuxuryCars", "#Cars"],
        "keywords": ["car", "cars", "supercar", "automotive", "vehicle", "luxury"],
    },
}


def live_relevant_hashtags(topic):
    """Best-effort public TikTok Creative Center trend signal for UAE.

    The public page can change, so failures fall back to niche-specific hashtags.
    Only topic-relevant tags are accepted; unrelated viral tags are never injected.
    """
    meta = TOPIC_META[topic]
    try:
        response = requests.get(
            TREND_URL,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        response.raise_for_status()
        found = []
        seen = set()
        for raw in re.findall(r"#([A-Za-z0-9_]{2,50})", response.text):
            tag = raw.lower()
            if tag in seen:
                continue
            seen.add(tag)
            if any(keyword.replace(" ", "") in tag for keyword in meta["keywords"]):
                found.append("#" + raw)
            if len(found) >= 3:
                break
        return found
    except Exception as exc:
        print(f"TikTok Creative Center trend lookup skipped: {exc}")
        return []


def build_tiktok_metadata(topic, concept, base_title):
    meta = TOPIC_META[topic]
    now = datetime.now(timezone.utc)
    seed = now.toordinal() * 24 + now.hour
    hook = meta["hooks"][seed % len(meta["hooks"])]

    live_tags = live_relevant_hashtags(topic)
    tags = []
    seen = set()
    for tag in live_tags + meta["hashtags"] + ["#ForYou", "#TikTok"]:
        key = tag.lower()
        if key not in seen:
            seen.add(key)
            tags.append(tag)
        if len(tags) >= 7:
            break

    # TikTok Direct Post video uses one caption/title field. Keep separate pieces
    # in metadata for readability, then combine them into a single post caption.
    title = hook
    description = meta["description"]
    caption = f"{title}\n{description}\n\n{' '.join(tags)}"

    return {
        "name": base_title,
        "title": title,
        "description": description,
        "hashtags": tags,
        "caption": caption,
        "trend_source": "TikTok Creative Center UAE 7-day public trends (best effort) + niche fallback",
    }


def main():
    random.seed()
    topic, concept = creator.choose_scheduled_concept()
    base_title = creator.polished_title(topic, concept)
    metadata = build_tiktok_metadata(topic, concept, base_title)

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        clips, credits = creator.download_clips(concept, work, wanted=3)
        final, duration = creator.make_video(clips, topic, work)
        shutil.copy2(final, "tiktok_video.mp4")

    metadata.update(
        {
            "topic": topic,
            "duration_seconds": duration,
            "source": "pexels",
            "audio": "Original synthesized sound bed embedded in the MP4",
        }
    )
    Path("tiktok_video_meta.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps({"status": "video_ready", **metadata}, ensure_ascii=False))


if __name__ == "__main__":
    main()

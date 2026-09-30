import json
import random
import shutil
import tempfile
from pathlib import Path

from src import main as creator


def main():
    random.seed()
    topic, concept = creator.choose_scheduled_concept()
    title = creator.polished_title(topic, concept)

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        clips, credits = creator.download_clips(concept, work, wanted=3)
        final, duration = creator.make_video(clips, topic, work)
        shutil.copy2(final, "tiktok_video.mp4")

    Path("tiktok_video_meta.json").write_text(
        json.dumps(
            {
                "topic": topic,
                "title": title,
                "duration_seconds": duration,
                "source": "pexels",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"status": "video_ready", "topic": topic, "title": title, "duration_seconds": duration}))


if __name__ == "__main__":
    main()

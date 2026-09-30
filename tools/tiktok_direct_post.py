import argparse
import base64
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import requests
from cryptography.fernet import Fernet


CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
DIRECT_POST_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"


def load_token(path):
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
    if not client_secret:
        raise SystemExit("TIKTOK_CLIENT_SECRET is missing.")

    encrypted = Path(path).read_text(encoding="utf-8").strip()
    key = base64.urlsafe_b64encode(hashlib.sha256(client_secret.encode("utf-8")).digest())
    payload = Fernet(key).decrypt(encrypted.encode("ascii"))
    return json.loads(payload.decode("utf-8"))


def api_json(response, label):
    try:
        payload = response.json()
    except Exception:
        raise SystemExit(f"{label} returned HTTP {response.status_code} with a non-JSON response.")

    error = payload.get("error") or {}
    if response.status_code >= 400 or error.get("code") not in (None, "", "ok"):
        safe = {
            "http_status": response.status_code,
            "error_code": error.get("code"),
            "message": error.get("message"),
            "log_id": error.get("log_id"),
        }
        raise SystemExit(label + " failed: " + json.dumps(safe))
    return payload


def media_duration(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path)
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        return 0.0
    try:
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def direct_post(token_path, video_path, title, aigc=False):
    token = load_token(token_path)
    scopes = {x.strip() for x in str(token.get("scope", "")).split(",") if x.strip()}
    if "video.publish" not in scopes:
        raise SystemExit("The TikTok token does not include video.publish. Re-authorize first.")

    access_token = token.get("access_token")
    if not access_token:
        raise SystemExit("TikTok token bundle has no access_token.")

    video = Path(video_path)
    if not video.exists():
        raise SystemExit(f"Video not found: {video}")
    size = video.stat().st_size
    if size <= 0:
        raise SystemExit("Video file is empty.")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    creator_response = requests.post(
        CREATOR_INFO_URL,
        headers=headers,
        json={},
        timeout=30,
    )
    creator_payload = api_json(creator_response, "TikTok creator info")
    creator = creator_payload.get("data") or {}

    privacy_options = creator.get("privacy_level_options") or []
    if "PUBLIC_TO_EVERYONE" not in privacy_options:
        raise SystemExit(
            "TikTok does not currently offer PUBLIC_TO_EVERYONE for this creator/app. "
            "No post was sent."
        )

    duration = media_duration(video)
    max_duration = float(creator.get("max_video_post_duration_sec") or 0)
    if max_duration > 0 and duration > max_duration:
        raise SystemExit(
            f"Video is {duration:.1f}s but this creator can post at most {max_duration:.1f}s."
        )

    post_info = {
        "title": title[:2200],
        "privacy_level": "PUBLIC_TO_EVERYONE",
        "disable_comment": bool(creator.get("comment_disabled", False)),
        "disable_duet": bool(creator.get("duet_disabled", False)),
        "disable_stitch": bool(creator.get("stitch_disabled", False)),
        "video_cover_timestamp_ms": 500,
        "brand_content_toggle": False,
        "brand_organic_toggle": False,
        "is_aigc": bool(aigc),
    }

    init_response = requests.post(
        DIRECT_POST_URL,
        headers=headers,
        json={
            "post_info": post_info,
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": size,
                "total_chunk_count": 1,
            },
        },
        timeout=45,
    )
    init_payload = api_json(init_response, "TikTok direct post initialization")
    data = init_payload.get("data") or {}
    upload_url = data.get("upload_url")
    publish_id = data.get("publish_id")
    if not upload_url or not publish_id:
        raise SystemExit("TikTok direct post initialization returned no upload URL or publish ID.")

    with video.open("rb") as handle:
        put = requests.put(
            upload_url,
            headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(size),
                "Content-Range": f"bytes 0-{size - 1}/{size}",
            },
            data=handle,
            timeout=180,
        )
    if put.status_code not in (200, 201, 202, 204):
        raise SystemExit(f"TikTok media upload failed with HTTP {put.status_code}.")

    final_status = "PROCESSING_UPLOAD"
    fail_reason = None
    public_post_ids = []
    for _ in range(36):
        time.sleep(5)
        status_resp = requests.post(
            STATUS_URL,
            headers=headers,
            json={"publish_id": publish_id},
            timeout=30,
        )
        status_payload = api_json(status_resp, "TikTok status check")
        status_data = status_payload.get("data") or {}
        final_status = status_data.get("status") or final_status
        fail_reason = status_data.get("fail_reason")
        public_post_ids = status_data.get("publicaly_available_post_id") or []
        print(json.dumps({
            "publish_id": publish_id,
            "status": final_status,
            "fail_reason": fail_reason,
            "public_post_ids": public_post_ids,
        }))
        if final_status in ("PUBLISH_COMPLETE", "FAILED"):
            break

    if final_status == "FAILED":
        raise SystemExit("TikTok direct post failed: " + str(fail_reason or "unknown reason"))

    print(json.dumps({
        "status": "direct_post_submitted",
        "publish_id": publish_id,
        "tiktok_status": final_status,
        "public_post_ids": public_post_ids,
        "privacy_requested": "PUBLIC_TO_EVERYONE",
    }))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    parser.add_argument("--video", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--aigc", action="store_true")
    args = parser.parse_args()
    direct_post(args.token, args.video, args.title, args.aigc)


if __name__ == "__main__":
    main()

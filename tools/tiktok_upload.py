import argparse
import base64
import hashlib
import json
import os
import time
from pathlib import Path

import requests
from cryptography.fernet import Fernet


INIT_URL = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
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


def upload_video(token_path, video_path):
    token = load_token(token_path)
    scope = token.get("scope", "")
    if "video.upload" not in {x.strip() for x in scope.split(",") if x.strip()}:
        raise SystemExit("The TikTok token does not include video.upload.")

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
    init = requests.post(
        INIT_URL,
        headers=headers,
        json={
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": size,
                "total_chunk_count": 1,
            }
        },
        timeout=45,
    )
    init_payload = api_json(init, "TikTok upload initialization")
    data = init_payload.get("data") or {}
    upload_url = data.get("upload_url")
    publish_id = data.get("publish_id")
    if not upload_url or not publish_id:
        raise SystemExit("TikTok upload initialization returned no upload URL or publish ID.")

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
    for _ in range(12):
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
        print(json.dumps({"publish_id": publish_id, "status": final_status, "fail_reason": fail_reason}))
        if final_status in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE", "FAILED"):
            break

    if final_status == "FAILED":
        raise SystemExit("TikTok processing failed: " + str(fail_reason or "unknown reason"))

    print(json.dumps({
        "status": "uploaded_to_tiktok",
        "publish_id": publish_id,
        "tiktok_status": final_status,
        "next_step": "Open TikTok inbox and complete the draft post.",
    }))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    parser.add_argument("--video", required=True)
    args = parser.parse_args()
    upload_video(args.token, args.video)


if __name__ == "__main__":
    main()

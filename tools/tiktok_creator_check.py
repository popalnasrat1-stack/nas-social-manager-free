import argparse
import base64
import hashlib
import json
import os
from pathlib import Path

import requests
from cryptography.fernet import Fernet

CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"


def load_token(path):
    secret = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
    encrypted = Path(path).read_text(encoding="utf-8").strip()
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return json.loads(Fernet(key).decrypt(encrypted.encode("ascii")).decode("utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    args = parser.parse_args()

    token = load_token(args.token)
    scopes = {x.strip() for x in str(token.get("scope", "")).split(",") if x.strip()}
    print("video_publish_scope:", "video.publish" in scopes)

    resp = requests.post(
        CREATOR_INFO_URL,
        headers={
            "Authorization": f"Bearer {token['access_token']}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json={},
        timeout=30,
    )
    try:
        payload = resp.json()
    except Exception:
        raise SystemExit(f"Creator info returned non-JSON HTTP {resp.status_code}")

    error = payload.get("error") or {}
    if resp.status_code >= 400 or error.get("code") not in (None, "", "ok"):
        print(json.dumps({
            "http_status": resp.status_code,
            "error_code": error.get("code"),
            "message": error.get("message"),
            "log_id": error.get("log_id"),
        }))
        raise SystemExit(1)

    data = payload.get("data") or {}
    print(json.dumps({
        "privacy_level_options": data.get("privacy_level_options") or [],
        "comment_disabled": data.get("comment_disabled"),
        "duet_disabled": data.get("duet_disabled"),
        "stitch_disabled": data.get("stitch_disabled"),
        "max_video_post_duration_sec": data.get("max_video_post_duration_sec"),
        "public_direct_post_available": "PUBLIC_TO_EVERYONE" in (data.get("privacy_level_options") or []),
    }, indent=2))


if __name__ == "__main__":
    main()

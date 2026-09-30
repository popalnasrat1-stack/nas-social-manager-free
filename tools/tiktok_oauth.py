import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import requests

REDIRECT_URI = "http://127.0.0.1:3455/callback/"
SCOPES = "user.info.basic,video.upload"


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def code_verifier(client_secret: str, state: str) -> str:
    digest = hmac.new(
        client_secret.encode("utf-8"),
        ("tiktok-pkce:" + state).encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return b64url(digest)


def start():
    client_key = os.environ.get("TIKTOK_CLIENT_KEY", "")
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "")
    if not client_key or not client_secret:
        raise SystemExit("TikTok client secrets are missing in GitHub Actions.")

    state = secrets.token_urlsafe(24)
    verifier = code_verifier(client_secret, state)
    challenge = hashlib.sha256(verifier.encode("ascii")).hexdigest()

    params = {
        "client_key": client_key,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = "https://www.tiktok.com/v2/auth/authorize/?" + urlencode(params)

    print("OPEN THIS URL IN YOUR BROWSER:")
    print(url)
    print()
    print("After authorizing TikTok, the localhost page may fail to load. That is expected.")
    print("Copy the FULL URL from your browser address bar and use it in the Finish step.")
    print("Do not paste the callback URL into chat.")


def finish(callback_url: str):
    client_key = os.environ.get("TIKTOK_CLIENT_KEY", "")
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "")
    if not client_key or not client_secret:
        raise SystemExit("TikTok client secrets are missing in GitHub Actions.")

    parsed = urlparse(callback_url.strip())
    query = parse_qs(parsed.query)

    if query.get("error"):
        raise SystemExit(
            "TikTok authorization returned an error: "
            + query.get("error_description", query["error"])[0]
        )

    code = (query.get("code") or [""])[0]
    state = (query.get("state") or [""])[0]
    if not code or not state:
        raise SystemExit("Callback URL is missing code or state.")

    verifier = code_verifier(client_secret, state)

    response = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        },
        timeout=30,
    )

    try:
        payload = response.json()
    except Exception:
        raise SystemExit(f"TikTok token exchange returned HTTP {response.status_code}.")

    if response.status_code != 200 or not payload.get("access_token"):
        safe_error = {
            "status": response.status_code,
            "error": payload.get("error"),
            "error_description": payload.get("error_description"),
            "log_id": payload.get("log_id"),
        }
        raise SystemExit("TikTok token exchange failed: " + json.dumps(safe_error))

    # Encrypt the token bundle before it leaves the workflow. The encrypted blob
    # can safely be moved into a GitHub secret; the client secret is required to decrypt it.
    from cryptography.fernet import Fernet

    key = base64.urlsafe_b64encode(hashlib.sha256(client_secret.encode("utf-8")).digest())
    fernet = Fernet(key)
    token_blob = fernet.encrypt(json.dumps(payload).encode("utf-8")).decode("ascii")

    Path("tiktok_token_encrypted.txt").write_text(token_blob, encoding="utf-8")

    print("TikTok authorization succeeded.")
    print("Granted scopes:", payload.get("scope", ""))
    print("Encrypted token bundle created as workflow artifact.")
    print("No access token or refresh token was printed to the log.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["start", "finish"])
    parser.add_argument("--callback-url", default="")
    args = parser.parse_args()

    if args.step == "start":
        start()
    else:
        if not args.callback_url:
            raise SystemExit("Finish requires --callback-url.")
        finish(args.callback_url)


if __name__ == "__main__":
    main()

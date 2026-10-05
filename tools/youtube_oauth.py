import argparse
import base64
import hashlib
import hmac
import html
import json
import os
import secrets
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from cryptography.fernet import Fernet


AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIRECT_URI = "http://localhost:8080/"
SCOPES = "https://www.googleapis.com/auth/youtube.upload"


def current_client():
    raw = os.environ.get("YOUTUBE_TOKEN_B64", "").strip()
    if not raw:
        raise SystemExit("YOUTUBE_TOKEN_B64 is missing.")
    try:
        payload = json.loads(base64.b64decode(raw).decode("utf-8"))
    except Exception as exc:
        raise SystemExit(f"Could not read existing YouTube OAuth configuration: {exc}")
    client_id = str(payload.get("client_id") or "").strip()
    client_secret = str(payload.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        raise SystemExit("Existing YouTube token does not contain client_id/client_secret.")
    return client_id, client_secret


def sign_state(client_secret):
    nonce = secrets.token_urlsafe(24)
    sig = hmac.new(client_secret.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    return f"{nonce}.{sig}"


def valid_state(value, client_secret):
    try:
        nonce, supplied = value.rsplit(".", 1)
    except ValueError:
        return False
    expected = hmac.new(client_secret.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied, expected)


def start():
    client_id, client_secret = current_client()
    state = sign_state(client_secret)
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    url = AUTH_URL + "?" + urlencode(params)
    page = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>YouTube Authorization</title>
<meta http-equiv="refresh" content="1;url={html.escape(url, quote=True)}"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:760px;margin:60px auto;padding:0 20px">
<h1>Authorize YouTube uploads</h1>
<p>Google should open automatically. If it does not, click the button below.</p>
<p><a href="{html.escape(url, quote=True)}" style="display:inline-block;padding:12px 18px;background:#111;color:#fff;text-decoration:none;border-radius:10px">Continue to Google</a></p>
<p>After approving access, your browser will try to open <code>localhost</code> and may show that the page cannot be reached. That is expected. Copy the <strong>entire URL from the address bar</strong> and save it as the GitHub Actions secret <code>YOUTUBE_CALLBACK_URL</code>.</p>
</body></html>"""
    Path("youtube_authorize.html").write_text(page, encoding="utf-8")
    print("YouTube authorization launcher created.")
    print("Redirect target:", REDIRECT_URI)


def finish():
    client_id, client_secret = current_client()
    callback = os.environ.get("YOUTUBE_CALLBACK_URL", "").strip()
    if not callback:
        raise SystemExit("YOUTUBE_CALLBACK_URL is missing.")

    parsed = urlparse(callback)
    params = parse_qs(parsed.query)
    if params.get("error"):
        raise SystemExit("Google authorization returned an error: " + params["error"][0])

    code = (params.get("code") or [""])[0]
    state = (params.get("state") or [""])[0]
    if not code:
        raise SystemExit("No authorization code was found in YOUTUBE_CALLBACK_URL.")
    if not state or not valid_state(state, client_secret):
        raise SystemExit("YouTube authorization state validation failed.")

    response = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=45,
    )
    try:
        token = response.json()
    except Exception:
        raise SystemExit(f"Google token exchange returned HTTP {response.status_code} with a non-JSON response.")
    if response.status_code >= 400 or not token.get("refresh_token"):
        safe = {
            "http_status": response.status_code,
            "error": token.get("error"),
            "error_description": token.get("error_description"),
            "refresh_token_present": bool(token.get("refresh_token")),
        }
        raise SystemExit("YouTube token exchange failed: " + json.dumps(safe))

    authorized = {
        "token": token.get("access_token"),
        "refresh_token": token.get("refresh_token"),
        "token_uri": TOKEN_URL,
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": [SCOPES],
    }
    key = base64.urlsafe_b64encode(hashlib.sha256(client_secret.encode("utf-8")).digest())
    encrypted = Fernet(key).encrypt(json.dumps(authorized).encode("utf-8")).decode("ascii")
    Path("youtube_token_encrypted.txt").write_text(encrypted, encoding="utf-8")
    print("YouTube authorization succeeded.")
    print("youtube.upload scope granted.")
    print("Encrypted YouTube token bundle created.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["start", "finish"])
    args = parser.parse_args()
    start() if args.step == "start" else finish()


if __name__ == "__main__":
    main()

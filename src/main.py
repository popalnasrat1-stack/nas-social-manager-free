
import os, re, json, base64, random, shutil, subprocess, tempfile
from pathlib import Path
import requests

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

REGION_CODE = os.getenv("REGION_CODE", "AE").upper()
YOUTUBE_PRIVACY = os.getenv("YOUTUBE_PRIVACY", "private")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
TOKEN_B64 = os.getenv("YOUTUBE_TOKEN_B64", "")

SAFE_TOPICS = {
    "animals": {
        "keywords": ["cat","cats","dog","dogs","pet","pets","puppy","kitten","animal","wildlife","bird","birds"],
        "pexels": ["funny pets", "cute animals", "playful dog", "curious cat"],
        "hashtags": ["#Shorts","#Animals","#Pets","#Funny"],
    },
    "food": {
        "keywords": ["food","cook","cooking","recipe","chef","cake","pizza","burger","dessert","snack"],
        "pexels": ["street food", "cooking close up", "dessert making", "food preparation"],
        "hashtags": ["#Shorts","#Food","#Cooking","#Satisfying"],
    },
    "satisfying": {
        "keywords": ["satisfying","cleaning","restore","restoration","makeover","transform","transformation","craft","paint","art"],
        "pexels": ["satisfying process", "craft close up", "cleaning transformation", "painting detail"],
        "hashtags": ["#Shorts","#Satisfying","#OddlySatisfying","#Relaxing"],
    },
    "funny": {
        "keywords": ["funny","comedy","prank","meme","laugh","lol","joke"],
        "pexels": ["funny people", "friends laughing", "playful moment", "comedy reaction"],
        "hashtags": ["#Shorts","#Funny","#Comedy","#Entertainment"],
    },
    "travel": {
        "keywords": ["travel","beach","mountain","city","nature","trip","vacation","island"],
        "pexels": ["travel adventure", "beautiful city", "nature travel", "beach sunset"],
        "hashtags": ["#Shorts","#Travel","#Explore","#Amazing"],
    },
    "challenge": {
        "keywords": ["challenge","game","guess","test","try","win","competition"],
        "pexels": ["friends game", "fun challenge", "people playing", "reaction challenge"],
        "hashtags": ["#Shorts","#Challenge","#Fun","#Entertainment"],
    },
}

BLOCKED = [
    "election","president","prime minister","minister","war","attack","killed","death","dead",
    "shooting","bomb","earthquake","flood","tragedy","murder","crime","suicide","sex","porn",
    "drug","overdose","hospital","disease","investment","crypto","stock market"
]

def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-5000:])
    return p.stdout

def write_token():
    if not TOKEN_B64:
        raise RuntimeError("YOUTUBE_TOKEN_B64 secret is missing.")
    token = base64.b64decode(TOKEN_B64).decode("utf-8")
    Path("youtube_token.json").write_text(token, encoding="utf-8")

def youtube():
    write_token()
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = Credentials.from_authorized_user_file("youtube_token.json", scopes)
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
    if not creds.valid:
        raise RuntimeError("YouTube token is invalid.")
    return build("youtube", "v3", credentials=creds)

def trending_titles(yt):
    resp = yt.videos().list(
        part="snippet",
        chart="mostPopular",
        regionCode=REGION_CODE,
        videoCategoryId="24",
        maxResults=30
    ).execute()
    titles = []
    for item in resp.get("items", []):
        t = item.get("snippet", {}).get("title", "").strip()
        low = t.lower()
        if t and not any(x in low for x in BLOCKED):
            titles.append(t)
    return titles

def score_topics(titles):
    joined = " ".join(titles).lower()
    scores = {}
    for topic, data in SAFE_TOPICS.items():
        scores[topic] = sum(joined.count(k) for k in data["keywords"])
    ranked = sorted(scores, key=lambda k: scores[k], reverse=True)
    top = ranked[:3] if ranked else list(SAFE_TOPICS)
    # add variety but bias toward current signals
    weights = [3,2,1][:len(top)]
    return random.choices(top, weights=weights, k=1)[0], scores

def build_script(topic):
    templates = {
        "animals": [
            "Quick scroll break: animal clips are still winning attention for one simple reason — you never know what happens next. Here’s a tiny dose of playful chaos, curious faces, and perfect timing. No complicated story, just a few moments that are almost impossible not to watch twice. Which one would you replay?",
            "Need a fast mood reset? Cute and unpredictable animal moments keep showing up in popular entertainment because the reaction is instant. Here’s an original little montage built around that same energy: curious, chaotic, and strangely calming at the same time."
        ],
        "food": [
            "There’s something about close-up food preparation that makes people stop scrolling. The movement is simple, the payoff is visual, and every step gets more satisfying. Here’s a quick food mood break inspired by that format — clean cuts, texture, color, and a final result worth waiting for.",
            "Fast food visuals are perfect short-form entertainment: movement, color, texture, then a payoff. Here’s a quick original montage with the same satisfying rhythm. Nothing complicated — just a few seconds of preparation that are way too easy to keep watching."
        ],
        "satisfying": [
            "Oddly satisfying videos work because your brain wants to see the process finish. A messy start, steady progress, and a clean result creates a tiny story without needing much explanation. Here’s a short original sequence built around that exact feeling. Stay for the payoff.",
            "Sometimes the best scroll break is simply watching a process come together. Smooth movement, small details, and a clean finish can be more relaxing than a long video. Here’s a quick original satisfying sequence inspired by what people are enjoying right now."
        ],
        "funny": [
            "Short-form comedy works best when the setup is quick and the reaction is even quicker. Here’s a light, original entertainment break built around expressions, timing, and playful moments. No long intro — just the kind of energy that makes you smile before you even realize it.",
            "The funniest short clips usually have one thing in common: they get to the moment fast. Here’s a quick original montage with playful reactions, awkward timing, and harmless chaos — exactly the kind of scroll break that doesn’t need a long explanation."
        ],
        "travel": [
            "Travel clips keep people watching because every few seconds can reveal a completely different view. Here’s a fast original travel mood break — movement, scenery, and that little feeling of wanting to be somewhere else for a minute. Which view would you pick?",
            "Sometimes entertainment is just seeing a place that makes you stop scrolling. A beautiful view, a little motion, and a quick change of scene can do the job. Here’s an original travel-style short inspired by what people are watching right now."
        ],
        "challenge": [
            "Challenges are easy to watch because you instantly understand the question: will it work or not? That tiny bit of suspense keeps people around for the payoff. Here’s a light original challenge-style montage with quick reactions and playful energy.",
            "A simple game becomes good short-form entertainment when the rules are obvious and the payoff comes fast. Here’s a quick original challenge-style break built around that same rhythm: setup, reaction, payoff."
        ]
    }
    return random.choice(templates[topic])

def title_for(topic):
    options = {
        "animals": ["A Tiny Animal Mood Boost 🐾", "The Kind of Animal Clip You Replay Twice 👀"],
        "food": ["This Food Prep Is Way Too Satisfying 😮", "A 30-Second Food Mood Break"],
        "satisfying": ["Your Brain Wanted to See the Ending 😌", "A Quick Oddly Satisfying Reset"],
        "funny": ["A Quick Dose of Harmless Chaos 😂", "30 Seconds of Pure Entertainment"],
        "travel": ["A Tiny Escape for Your Feed 🌍", "Views That Make You Stop Scrolling"],
        "challenge": ["Would You Pass This? 👀", "A Quick Challenge-Style Scroll Break"],
    }
    return random.choice(options[topic])

def search_pexels(query, per_page=12):
    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY secret is missing.")
    r = requests.get(
        "https://api.pexels.com/v1/videos/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": query, "per_page": per_page, "orientation": "portrait"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("videos", [])

def choose_file(video):
    files = video.get("video_files", [])
    if not files:
        return None
    # Prefer portrait / reasonably small HD-ish files for fast GitHub Actions runs.
    def rank(f):
        w, h = f.get("width") or 0, f.get("height") or 0
        portrait_penalty = 0 if h >= w else 10
        width_penalty = abs((w or 720) - 720) / 1000
        return portrait_penalty + width_penalty
    return sorted(files, key=rank)[0]

def download_clips(topic, work):
    queries = SAFE_TOPICS[topic]["pexels"][:]
    random.shuffle(queries)
    selected = []
    credits = []

    for q in queries:
        for v in search_pexels(q):
            f = choose_file(v)
            if not f or not f.get("link"):
                continue
            if any(x["id"] == v.get("id") for x in selected):
                continue
            selected.append({"id": v.get("id"), "file": f, "video": v})
            user = v.get("user") or {}
            credits.append({
                "name": user.get("name", "Pexels contributor"),
                "url": v.get("url") or user.get("url") or "https://www.pexels.com/"
            })
            if len(selected) >= 3:
                break
        if len(selected) >= 3:
            break

    if not selected:
        raise RuntimeError("No suitable Pexels videos found.")

    paths = []
    for i, item in enumerate(selected, start=1):
        url = item["file"]["link"]
        out = work / f"clip_src_{i}.mp4"
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(out, "wb") as fh:
                for chunk in r.iter_content(1024 * 1024):
                    if chunk:
                        fh.write(chunk)
        paths.append(out)
    return paths, credits

def make_voice(script, work):
    wav = work / "voice.wav"
    # Free/offline text to speech.
    run(["espeak-ng", "-s", "170", "-v", "en-us", "-w", str(wav), script])
    return wav

def audio_duration(path):
    out = run([
        "ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1",str(path)
    ])
    return max(5.0, float(out.strip()))

def make_video(clips, voice, title, work):
    duration = audio_duration(voice)
    per = max(4.0, duration / len(clips) + 0.5)
    normalized = []

    for i, src in enumerate(clips, start=1):
        dst = work / f"clip_{i}.mp4"
        vf = (
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            "fps=30,format=yuv420p"
        )
        run([
            "ffmpeg","-y","-stream_loop","-1","-i",str(src),
            "-t",f"{per:.2f}","-vf",vf,
            "-an","-c:v","libx264","-preset","veryfast","-crf","24",
            str(dst)
        ])
        normalized.append(dst)

    concat = work / "concat.txt"
    concat.write_text("\n".join(f"file '{p.as_posix()}'" for p in normalized), encoding="utf-8")
    silent = work / "silent.mp4"
    run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),"-c","copy",str(silent)])

    final = work / "final.mp4"
    run([
        "ffmpeg","-y","-i",str(silent),"-i",str(voice),
        "-map","0:v:0","-map","1:a:0",
        "-c:v","copy","-c:a","aac","-b:a","160k",
        "-shortest","-movflags","+faststart",str(final)
    ])
    return final

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
    return result.get("id","")

def main():
    random.seed()
    yt = youtube()

    titles = trending_titles(yt)
    topic, scores = score_topics(titles)

    script = build_script(topic)
    title = title_for(topic)
    hashtags = SAFE_TOPICS[topic]["hashtags"]

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        clips, credits = download_clips(topic, work)
        voice = make_voice(script, work)
        final = make_video(clips, voice, title, work)

        credit_lines = []
        for c in credits:
            credit_lines.append(f"Footage by {c['name']} on Pexels: {c['url']}")

        description = (
            "Original edit inspired by broad patterns in YouTube's current popular Entertainment chart "
            f"for region {REGION_CODE}. No clips were copied from the trending videos themselves.\n\n"
            + "\n".join(credit_lines)
            + "\n\nPhotos/videos provided by Pexels.\n\n"
            + " ".join(hashtags)
        )

        tags = [x.lstrip("#") for x in hashtags] + [topic, "entertainment", "shorts"]
        video_id = upload(yt, final, title, description, tags)

    print(json.dumps({
        "status": "uploaded",
        "video_id": video_id,
        "topic": topic,
        "title": title,
        "region": REGION_CODE,
        "privacy": YOUTUBE_PRIVACY,
        "trend_scores": scores
    }, indent=2))

if __name__ == "__main__":
    main()

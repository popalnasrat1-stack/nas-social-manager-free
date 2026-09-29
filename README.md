# Nas Social Manager V4 FREE

This version is designed to run while your Mac is asleep **without paying for OpenAI or a 24/7 cloud server**.

It uses:

- **GitHub Actions** for the hourly cloud runner.
- **YouTube Data API** for current popular entertainment signals and uploads.
- **Pexels API** for free stock video footage.
- **espeak-ng** for free offline narration.
- **FFmpeg** for video editing.

There is no paid AI API in V4.

## What happens every hour

1. GitHub starts a temporary cloud computer.
2. V4 checks YouTube's current `mostPopular` Entertainment chart for your region.
3. It looks for broad safe trend categories such as animals, food, satisfying videos, comedy, travel, or challenges.
4. It does **not** download or copy the trending YouTube videos.
5. It gets unrelated free stock footage from Pexels.
6. It creates a new narration from safe built-in templates.
7. It edits a vertical video.
8. It creates a title, description, hashtags/tags, and Pexels credits.
9. It uploads the result to your YouTube channel.
10. It repeats the next hour.

## Important trade-off

Because V4 uses **no paid AI**, its scripts/titles are template-based and the narration voice is basic.

V3.1 will generally create more varied and polished content, but V4 can be operated with no OpenAI bill.

No system can guarantee "perfect" titles, hashtags, views, or monetization.

---

# WHAT YOU NEED — ALL FREE

## 1. GitHub account

Create a GitHub account.

For the simplest no-cost hourly setup, use a **public repository**. GitHub's standard hosted runners are free for public repositories.

Your code will be public, but the YouTube token and Pexels API key will be stored as private GitHub Secrets and must NEVER be committed into the repository.

A private repository receives a monthly free-minute allowance, so hourly video rendering might eventually use that allowance.

## 2. Pexels API key

Create a free Pexels account and request a free API key.

V4 automatically adds Pexels/contributor credits into each video description.

## 3. Your existing YouTube token

You already have this from V1/V2:

`youtube_token.json`

DO NOT upload that file into the repository.

Instead, convert it to Base64 on your Mac:

```bash
base64 -i youtube_token.json | pbcopy
```

That copies the encoded token to your clipboard.

---

# GITHUB SETUP

Create a new repository, for example:

`nas-social-manager-free`

Upload all files from this V4 folder.

Then go to:

**Settings → Secrets and variables → Actions**

## Add these Repository Secrets

### `YOUTUBE_TOKEN_B64`
Paste the Base64 text copied from your Mac.

### `PEXELS_API_KEY`
Paste your Pexels API key.

## Add these Repository Variables

### `REGION_CODE`
Example:

`AE`

Other examples: `US`, `GB`, `CA`, `AU`.

### `YOUTUBE_PRIVACY`
Start with:

`private`

Do not change this to `public` until several tests look correct.

---

# TEST IT

Open your GitHub repository.

Go to:

**Actions → Free Hourly YouTube Short → Run workflow**

Watch the run.

When it finishes successfully, open YouTube Studio.

You should see the new video as **Private**.

After several good tests, change the repository variable:

`YOUTUBE_PRIVACY = public`

---

# HOURLY SCHEDULE

The workflow is set to:

`17 minutes past every hour`

This avoids GitHub's busiest time at the exact start of the hour.

GitHub scheduled workflows are not guaranteed to run at the exact second/minute and can occasionally be delayed.

---

# KEEPING IT FREE

Public GitHub repositories can use standard GitHub-hosted Actions runners without billed minutes.

Pexels has a free API. V4 normally makes only a small number of requests per hour.

YouTube's API has free quotas. The current default `videos.insert` quota bucket supports far more than the 24 uploads/day used by an hourly schedule.

There is no OpenAI API key in V4.

---

# COPYRIGHT / QUALITY

V4 never downloads the popular/trending YouTube videos.

The popular chart is only used to choose broad entertainment categories.

The actual footage comes from Pexels, and attribution is added automatically.

Do not remove the Pexels attribution logic unless you have separately reviewed Pexels' API/content terms.

High-frequency repetitive uploads can still be a problem for viewer experience and YouTube monetization. Review the output before leaving public hourly uploads enabled long-term.

---

# STOP AUTOMATION

Go to:

**GitHub → Actions → Free Hourly YouTube Short**

Disable the workflow.

No Mac needs to stay on.

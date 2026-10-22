# Khabar

**Your news, summarized and in your inbox.**

https://github.com/user-attachments/assets/677b5a81-b5b6-48bb-b03a-5951912b7717


Khabar reads trusted news outlets, groups the stories by topic, and emails you a short AI summary three times a day, with a link to every source. You stay informed in a few minutes, without scrolling.

## Features

- **Three briefs a day:** morning, afternoon and evening
- **By topic:** geopolitics, Morocco, economy, tech/AI, software engineering, science
- **Trusted sources only**, with a link on every story
- **No repeats:** stories already emailed in the last 48 hours are dropped unless something new happened, in which case they're marked as an **Update**
- **Free to run:** uses Gemini's free tier. If the AI step fails, that topic is sent as plain headlines

## How it works

RSS feeds → rank by source trust and recency → LLM summary per topic → email

## Quick start

```bash
git clone https://github.com/Mainich-Mohamed/Khabar.git
cd Khabar
cp .env.example .env        # add your Gmail App Password and a free Gemini key
docker compose up -d db
docker compose run --rm app preview     # try it without sending
docker compose up -d --build scheduler  # run it automatically
```

## Run it without your own machine

GitHub Actions runs the digest, [Neon](https://neon.com) holds the database, and a small Cloudflare Worker starts each run on time (GitHub's own cron ran hours late). See `.github/workflows/` and `deploy/cloudflare/`.

## Stack

Python · PostgreSQL (Neon) · Docker · GitHub Actions · Cloudflare Workers · Gmail SMTP · Gemini AI

## Roadmap

- [x] Email briefs with deduplication
- [ ] Sunday weekly brief
- [x] Always-on hosting
- [ ] Mobile app

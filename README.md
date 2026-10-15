# Khabar

**Your news, summarized and in your inbox.**

https://github.com/user-attachments/assets/677b5a81-b5b6-48bb-b03a-5951912b7717


Khabar reads trusted news outlets, groups the stories by topic, and emails you a short AI summary three times a day, with a link to every source. You stay informed in a few minutes, without scrolling.

## Features

- **Three briefs a day:** morning, afternoon and evening
- **By topic:** geopolitics, Morocco, economy, tech/AI, science
- **Trusted sources only**, with a link on every story
- **No repeats:** stories already emailed in the last 48 hours are dropped unless something new happened, in which case they're marked as an **Update**
- **Free to run:** uses free LLM tiers, with automatic fallbacks

## How it works

RSS feeds → rank by source trust and recency → LLM summary per topic → email

## Quick start

```bash
git clone https://github.com/Mainich-Mohamed/Khabar.git
cd Khabar
cp .env.example .env        # add your Gmail App Password and free LLM keys
docker compose up -d db
docker compose run --rm app preview     # try it without sending
docker compose up -d --build scheduler  # run it automatically
```

## Stack

Python · PostgreSQL · Docker · Gmail SMTP · Groq / OpenRouter / Gemini

## Roadmap

- [x] Email briefs with deduplication
- [ ] Sunday weekly brief
- [ ] Always-on hosting
- [ ] Mobile app

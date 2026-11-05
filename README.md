<div align="center">

# Khabar

**The news, read for you. Three short briefs a day, and one expert analysis every Sunday.**

https://github.com/user-attachments/assets/677b5a81-b5b6-48bb-b03a-5951912b7717

</div>

---

Khabar (خبر, "news") reads 33 trusted outlets in English, French and Arabic, merges the stories that cover the same event, and emails you a short brief with a link to every source.

On Sundays, the **Khabar Artificial Expert** goes further: it rereads everything Khabar sent you that week and explains what it means.

No app, no feed, no scrolling. Just your inbox.

## What lands in your inbox

| When (UTC) | Email | What's inside |
|---|---|---|
| 07:00 | **Morning brief** | The top story, then every topic summarized, with sources |
| 16:00 | **Afternoon update** | Only what's new since the morning, skipped on quiet days |
| 20:00 | **Evening brief** | The full brief again, without repeating the morning's stories |
| Sunday 20:30 | **🧠 Khabar Artificial Expert** | The week analysed, topic by topic |

### The daily briefs
- **Six topics:** Geopolitics · Morocco · Economy · Tech & AI · Software Engineering · Science & Engineering
- **One event, one story.** When five outlets cover the same thing, you read it once, with all five links.
- **Facts only from the articles.** Stories backed by a single outlet are marked *single source*.
- **No repeats.** A story sent in the last 48 hours comes back only if something changed, and then it's tagged **Update**.
- **Did you know?** One curious find to end on.

### The Khabar Artificial Expert



https://github.com/user-attachments/assets/0b1848c3-52bc-47de-9f69-884f73b15fb0


Once a week, an AI analyst takes each topic and writes 300 to 400 words on:
- **what is happening:** the events of the week, read together;
- **why:** the forces and patterns behind them;
- **what could come next:** possible scenarios and what to watch.

It opens with **the week in one paragraph**, which ties the topics together. Every analysis ends with **"Based on this week's stories"**, linking the briefs it relied on.

The analysis is free to reason, but **it can't invent events**: every fact comes from stories Khabar already sent you.

## How it works

```
Daily    33 RSS feeds ─► rank by source trust and recency ─► read the article leads
                     ─► Gemini groups and summarizes each topic ─► email ─► remember what was sent

Sunday   the week's sent stories ─► one expert analysis per topic (Groq, gpt-oss-120b)
                                 ─► the week in one paragraph ─► email
```

The model returns story numbers, never links. Khabar maps the numbers back to the real articles, so a link in your inbox can't be made up. If a topic's AI call fails, that topic falls back to plain headlines, and the email still goes out.

## Run it locally

You need Docker, a Gmail account with an [App Password](https://myaccount.google.com/apppasswords), and two free API keys: [Gemini](https://aistudio.google.com) for the daily briefs and [Groq](https://console.groq.com) for the Sunday analysis.

```bash
git clone https://github.com/Mainich-Mohamed/Khabar.git
cd Khabar
cp .env.example .env                          # fill in Gmail, GEMINI_API_KEY, WEEKLY_API_KEY
docker compose up -d db

docker compose run --rm app check-feeds       # are all the feeds reachable?
docker compose run --rm app preview           # build a brief into preview.html, send nothing
docker compose run --rm app preview-weekly    # build the Sunday analysis, send nothing
docker compose run --rm app run               # send a real brief
```

`docker compose up -d --build scheduler` keeps sending the full briefs at `DIGEST_HOURS`. The afternoon update and the Sunday analysis are started by the hosted setup below, or by hand with `update` and `weekly`.

## Run it without a server

This is how Khabar runs in production, for free:

- **[Neon](https://neon.com)** hosts the PostgreSQL database.
- **GitHub Actions** runs each job (`.github/workflows/digest.yml`).
- **A Cloudflare Worker** (`deploy/cloudflare/trigger.js`) starts every run on time, because GitHub's own cron ran hours late.
- **Healthchecks** emails you if a run is missed.

Add these repository secrets: `DATABASE_URL`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_TO`, `GEMINI_API_KEY`, `WEEKLY_API_KEY`, `HEALTHCHECK_URL`.

## Make it yours

- **Sources and topics:** `config/sources.yaml`. Each feed has a topic, a language and a trust weight.
- **Language and style:** `DIGEST_LANGUAGE`, `DIGEST_VOICE` (`lively` or `plain`), `TIMEZONE`.
- **Models:** `GEMINI_MODEL` for the briefs; `WEEKLY_MODEL` and `WEEKLY_BASE_URL` for the analysis, which works with any OpenAI-compatible API.

Every setting is documented in `.env.example`.

## Stack

Python · PostgreSQL · Docker · GitHub Actions · Cloudflare Workers · Gemini · Groq · Gmail SMTP

## Roadmap

- [x] Daily briefs with deduplication and updates
- [x] Always-on hosting
- [x] Khabar Artificial Expert, the Sunday analysis
- [ ] Mobile app

## License

[MIT](LICENSE) © 2026 Mohamed Mainich

# Landing page plan

Status: planning. this document records the decisions so far.

## Goal
A single-page site where someone enters their email and starts receiving Khabar's briefs.
The email form is the only call to action.

## Decisions
- **Hosting:** the page is static, on GitHub Pages. A small FastAPI service on Render's free tier
  handles signup, confirmation and unsubscribe. Subscribers are stored in the existing Neon database.
  Hosting must stay free.
- **Frontend:** Vite, React 19, TypeScript, Tailwind v4, shadcn CLI and `motion`, built to static files
  in a `site/` folder. Components come from the free tiers of Magic UI and Aceternity UI, used sparingly:
  most visitors are on phones.
- **Brand:** Nuqta (green `#0b5d4f`, saffron `#cf7f00`, Readex Pro). Tokens are in
  `brand/email-mockup/HANDOFF.md`.
- **Languages:** English and Arabic (right-to-left). The language toggle changes the page itself and is
  always visible. (French version in future, maybe 😜😶‍🌫️)
- **Brief language:** chosen by the subscriber at signup. The Arabic brief does not exist yet, so Arabic
  is shown as "coming soon" and those subscribers join a waitlist.
- **Signup:** double opt-in, then one email per subscriber with its own unsubscribe link.
- **Layout:** one responsive page, designed for phones first (Android is the main audience), with a
  desktop layout from about 1024px. Not two separate versions.

## Page structure
1. **Top bar:** logo and language toggle.
2. **Hero:** tagline, headline, subheadline, email form with brief-language choice, reassurance line,
   phone mockup of a brief.
3. **Outlets strip:** 33 outlets, 6 topics, 3 source languages, outlet names as text.
4. **How it works:** we read, we merge, you read.
5. **What you get:** morning brief, afternoon update, evening brief, Sunday analysis.
6. **Why trust it:** facts only from the articles, sources linked, single-source labels, no repeats.
7. **FAQ:** free, unsubscribing, language, topics, who writes it, privacy, why confirm.
8. **Final signup:** the same form again.
9. **Footer:** logo, language toggle, privacy, GitHub link, contact.

Left out on purpose: testimonials and subscriber counts (none exist, none will be invented),
pricing, a navigation menu, and a "Built in the open" section (a footer GitHub link for now).

## Implementation order
1. Copy files in English and Arabic.
2. `site/` setup: Vite, Tailwind, brand tokens, language switch with right-to-left.
3. Hero, with a stub in place of the backend.
4. The remaining sections, one at a time.
5. Polish: phone and desktop widths, Arabic layout details, performance.
6. Backend (subscribers table, per-subscriber sending, signup/confirm/unsubscribe) and deploy.
# Landing page plan

Status: the desktop page is built in `site/` (12 Nov 2026). Left: the mobile layout, the backend and
the deploy. This document records the decisions and what was built; the day-to-day state is in the
"Landing page" section of `HANDOFF.md`.

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
- **Layout:** one responsive page, with a desktop layout from about 1024px. Not two separate versions.
  Changed: the desktop page was built first, and the mobile layout comes next.
- **Theme:** dark only, for every browser. The light version was dropped.
- **Extra libraries:** `cobe` (the globe in the hero) and inline Phosphor icons (MIT, thin weight).

## Page structure (as built)
1. **Top bar:** logo and language toggle.
2. **Hero:** tagline, headline, subheadline and the email form with the brief-language choice, over an
   aurora background, beside a slowly spinning globe. (Dropped: the phone mockup, the stack of email
   cards, the beams, and the reassurance line.)
3. **Outlets strip:** 17 outlet logos in their own colours, scrolling sideways, each sized to the same area.
4. **What you get:** a timeline of the four emails: 07:00, 16:00, 20:00, and Sunday 20:30 (the Khabar
   Artificial Expert).
5. **Why trust it:** a full-width tinted band with four promises (one event one story, facts only from the
   articles, links that can't be made up, an expert that can't invent events) beside an example of two
   stories laid out like the email. The example stories are invented and labelled as an example.
6. **FAQ:** seven questions that open and close: free, topics, language, who writes it, why confirm,
   unsubscribe, what happens to the email.
7. **Final signup:** a full-width green band with the same form in a glass card.
8. **Footer:** logo, tagline, GitHub link, copyright. (Still missing: a contact email.)

Tried and removed: "How it works" (we read, we merge, you read), after three different layouts.

Left out on purpose: testimonials and subscriber counts (none exist, none will be invented),
pricing, a navigation menu, a custom cursor, and a "Built in the open" section (a footer GitHub link
for now).

## Implementation order
1. Copy files in English and Arabic. (Done, in `site/src/i18n/strings.ts`.)
2. `site/` setup: Vite, Tailwind, brand tokens, language switch with right-to-left. (Done.)
3. Hero, with a stub in place of the backend. (Done: `site/src/lib/signup.ts` waits, then succeeds; in
   development an email starting with "fail" simulates a network error.)
4. The remaining sections, one at a time. (Done, for desktop.)
5. Polish: **mobile layout (next)**, Arabic layout details, accessibility checks, performance (the globe
   and the aurora are heavy).
6. Backend (subscribers table, per-subscriber sending, signup/confirm/unsubscribe) and deploy. The FAQ
   already promises an unsubscribe link in every email, which does not exist yet.
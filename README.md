markdown# Trendjack Hunter

Built for Kuzana — a Django SaaS that detects trending startup/entrepreneurship
topics across RSS, Reddit, and YouTube, scores them for relevance to Kenyan
entrepreneurs, and generates AI-powered content briefs — before the trend has
already passed.

## What it does
RSS + Reddit + YouTube → Article collection → Trend detection
(keyword extraction + scoring) → Entrepreneur relevance scoring (0-100)
→ AI content brief generation → Dashboard + Trend detail page

- Collects articles from startup/tech/entrepreneurship RSS feeds, Reddit
  (`r/Entrepreneur`, `r/smallbusiness`, `r/startups`, `r/kenya`, `r/SideProject`),
  and YouTube search queries.
- Detects rising topics by extracting noun-phrase keywords (spaCy) and scoring
  them by frequency + recency, with filtering to strip publisher-name leakage,
  sentence fragments, and generic single-word noise.
- Scores relevance (0–100) for founders specifically — funding news scores
  high, celebrity gossip scores near zero — using a transparent, rule-based
  weighted system.
- Generates content briefs via AI for trends that clear the relevance
  threshold: why it's trending, why founders care, a content angle, a
  LinkedIn post idea, an Instagram Reel idea, a 30–60s video script, a hook,
  a title, a remix template, and an urgency score. Briefs can be generated
  from the terminal (`generate_briefs`) or on-demand from a button on the
  Trend Detail page (subscribers only).
- Full account system: two-step signup (email verification code required
  before an account is even created), login, password reset via email
  (Resend), and a self-service "My Account" page (profile, live subscription
  status, full billing history).
- Subscriptions and payments via IntaSend — both card checkout and M-Pesa
  STK push, with webhook-driven activation.
- Displays everything in a themed dashboard (sortable/filterable trend
  cards) and a detail page per trend (full brief, gated behind an active
  subscription, + source articles).

## Setup

```bash
# 1. Clone the project, then from the project root:
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Download the spaCy English model (used for keyword extraction)
python -m spacy download en_core_web_sm

# 4. Set up Postgres (see "Database setup" below if starting fresh)

# 5. Set up your environment file
cp .env.example .env
# then edit .env and fill in real values — see .env.example for what's
# required (DATABASE_URL, an AI key, Resend, YouTube, Reddit, IntaSend)

# 6. Run migrations
python manage.py migrate

# 7. Create an admin user (to view /admin/)
python manage.py createsuperuser

# 8. Run the server
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` for the app, `http://127.0.0.1:8000/admin/`
for the Django admin panel.

### Database setup (Postgres)

This project runs on PostgreSQL, not SQLite. If you don't already have a
`trendjack` database set up:

```bash
sudo -u postgres psql
```
```sql
CREATE DATABASE trendjack;
CREATE USER trendjack_user WITH PASSWORD 'your_strong_password';
GRANT ALL PRIVILEGES ON DATABASE trendjack TO trendjack_user;
```

On Postgres 15+, you'll also need to grant schema permissions (connect to
the `trendjack` database specifically for this, not `postgres`):

```sql
GRANT ALL ON SCHEMA public TO trendjack_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO trendjack_user;
ALTER SCHEMA public OWNER TO trendjack_user;
```

Then build your `DATABASE_URL` in `.env` as:
postgres://trendjack_user:PASSWORD@localhost:5432/trendjack
**Special characters in your password must be URL-encoded** (`@` → `%40`,
`#` → `%23`, `$` → `%24`, etc.) or the connection string won't parse correctly.

## Running the pipeline

```bash
# Collects fresh articles (RSS + Reddit + YouTube), then detects trends —
# one command does both by default.
python manage.py detect_trends
#    optional: --lookback-days 30
#    optional: --skip-collect     (re-analyze existing articles only, skip re-collecting)

# Generate AI content briefs for trends above the relevance threshold
python manage.py generate_briefs
#    optional: --force          (regenerate briefs that already exist)
#    optional: --limit 5        (cap how many briefs to generate, controls API cost)
```

Subscribed users can also generate a brief for a single trend on-demand from
a button on that trend's detail page, without touching the terminal at all.

**Tip:** `MIN_RELEVANCE_SCORE_FOR_BRIEF` in `.env` controls how selective
brief generation is (default 40/100).

## Project structure
trendjack_hunter/
├── config/             # Django settings, root URLs
├── core/               # Shared base template, landing page, theme CSS
├── accounts/           # Signup/login/password-reset, Profile, Subscription,
│                       #   IntaSend integration, My Account page
├── articles/           # Collection: Article model, RSS/Reddit/YouTube
│                       #   collectors, management commands
├── trends/             # Detection: Trend model, keyword extraction,
│                       #   scoring, dashboard, detail page
├── briefs/             # AI generation: ContentBrief model, AI client,
│                       #   generate_briefs command
└── templates/base.html # Shared themed layout used by every page

## Database models

| Model | Key fields | Purpose |
|---|---|---|
| `Article` | `title`, `source`, `source_type`, `url` (unique), `summary`, `published_at` | Raw evidence layer — one row per ingested article (RSS/Reddit/YouTube) |
| `Trend` | `name` (unique), `trend_score`, `relevance_score`, `source_count`, `articles` (M2M), `status` | A detected topic, with frequency/recency score and 0–100 founder-relevance score |
| `ContentBrief` | `trend` (1:1), `why_trending`, `why_entrepreneurs_care`, `content_angle`, `linkedin_post_idea`, `instagram_reel_idea`, `video_script`, `suggested_hook`, `suggested_title`, `remix_template`, `urgency_score`, `estimated_lifespan` | AI-generated, ready-to-use content brief for one trend |
| `Profile` | `user` (1:1), `phone_number`, `email_verified` | Extends Django's User with M-Pesa phone and verification state |
| `Subscription` | `user`, `plan`, `payment_method`, `status`, `amount_kes`, `current_period_end` | One row per payment attempt/period — full billing history lives here |

## Design decisions worth knowing for Q&A

- **Relevance scoring is rule-based, not an LLM call.** Instant and free to
  score every trend candidate; the AI call is reserved for the higher-value
  job of writing the actual brief, only for trends that clear the threshold.
  Every score is fully explainable (which keyword categories matched, and why).
- **Keyword extraction is deliberately hardened against noise.** Filters
  reject publisher-name leakage (e.g. aggregated Google News titles), sentence
  fragments from informal/unpunctuated titles, single generic words, and
  platform boilerplate (`#Shorts`, etc.) — tuned iteratively against real
  pipeline output, not just in theory.
- **Signup verifies email *before* account creation, not after.** A 6-digit
  code is emailed on signup; the `User` row is only created once that code is
  confirmed — an unverified signup attempt never persists in the database at all.
- **Collection and detection are one command.** `detect_trends` runs all
  three collectors automatically before analyzing, so there's no multi-step
  manual pipeline to remember — `--skip-collect` is available if you just
  want to re-analyze existing articles.
- **Briefs use strict JSON-output prompting**, parsed defensively (handles
  markdown code-fence wrapping, validates all required keys are present)
  rather than parsing free-form prose — this is what makes many structured
  DB fields reliable.
- **Trend matching is deduped and recency-weighted.** "AI Agents" and
  "ai agents" collapse into one trend; simple plurals merge too; an article
  published today contributes more to the trend score than one from a week ago.
- **Idempotent by design.** Re-running collection skips duplicate URLs;
  re-running `generate_briefs` skips trends that already have a brief unless
  you pass `--force`.

## Known limitations / in-progress items

- **No background task queue (Celery) yet** — commands run manually or via
  cron/Task Scheduler. This is the natural next upgrade once deployed, and
  would enable true "runs automatically every day" scheduling.
- **AI billing** — the international-card requirement for OpenAI/Anthropic
  billing is a known live blocker for actual brief generation right now.
- **Reddit as a live source** is implemented but currently blocked by an
  unresolved developer-app signup issue on one dev machine.
- **IntaSend is wired for sandbox testing only** — going live requires
  IntaSend's business verification (KYC) process, not yet started.
- **No trend history graphs or email alert digests yet** — listed as
  possible future features, not part of current scope.
- Relevance scoring keyword lists are a reasonable starting set, not
  exhaustive — easy to extend in `trends/services/relevance_scorer.py`.

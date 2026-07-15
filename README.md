# Trendjack Hunter

**Built for Kuzana** — a Django MVP that detects trending startup/entrepreneurship topics
and generates AI-powered content briefs, before the trend has already passed.

---

## What it does

```
RSS feeds → Article collection → Trend detection (keyword extraction + scoring)
          → Entrepreneur relevance scoring (0-100) → OpenAI content brief generation
          → Dashboard + Trend detail page
```

1. **Collects** articles from startup/tech/entrepreneurship RSS feeds.
2. **Detects** rising topics by extracting noun-phrase keywords (spaCy) and scoring
   them by frequency + recency.
3. **Scores relevance** (0–100) for founders specifically — funding news scores high,
   celebrity gossip scores near zero — using a transparent, rule-based weighted system.
4. **Generates content briefs** via OpenAI (gpt-4o-mini) for trends that clear the
   relevance threshold: why it's trending, why founders care, a content angle, a
   LinkedIn post idea, an Instagram Reel idea, a hook, a title, and an urgency score.
5. **Displays everything** in a dashboard (sortable/filterable trend cards) and a
   detail page per trend (full brief + source articles).

---

## Setup

```bash
# 1. Clone / unzip the project, then from the project root:
pip install -r requirements.txt

# 2. Download the spaCy English model (used for keyword extraction)
python -m spacy download en_core_web_sm

# 3. Set up your environment file
cp .env.example .env
# then edit .env and add your real OPENAI_API_KEY

# 4. Run migrations
python manage.py migrate

# 5. Create an admin user (to view /admin/)
python manage.py createsuperuser

# 6. Run the server
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` for the app, `http://127.0.0.1:8000/admin/` for the
admin panel.

---

## Running the pipeline

These three management commands form the core pipeline. Run them in order:

```bash
# 1. Pull in fresh articles from all configured RSS sources
python manage.py collect_articles

# 2. Detect trending topics from articles collected in the last 14 days
python manage.py detect_trends
#    optional: --lookback-days 30

# 3. Generate AI content briefs for trends above the relevance threshold
python manage.py generate_briefs
#    optional: --force          (regenerate briefs that already exist)
#    optional: --limit 5        (cap how many briefs to generate, controls API cost)
```

For a hackathon demo, running these three in sequence against real RSS feeds will
populate the dashboard with real, current trends end-to-end.

**Tip:** `MIN_RELEVANCE_SCORE_FOR_BRIEF` in `.env` controls how selective brief
generation is (default 40/100). Lower it if you want briefs on more borderline trends;
raise it to save API calls and only brief the strongest signals.

---

## Project structure

```
trendjack_hunter/
├── config/             # Django settings, root URLs
├── core/               # Shared base template, landing page, theme CSS
├── articles/           # RSS collection: Article model, collector service, collect_articles command
├── trends/             # Detection: Trend model, keyword extraction, scoring, dashboard, detail page
├── briefs/             # AI generation: ContentBrief model, OpenAI client, generate_briefs command
└── templates/base.html # Shared Bootstrap layout used by every page
```

Each app has a single responsibility, which keeps the OpenAI integration, the
scoring logic, and the RSS parsing fully decoupled from each other — useful both
for the demo narrative and for swapping any one piece out later (e.g. adding a
second AI provider, or a new data source) without touching the rest.

---

## Database models

| Model | Key fields | Purpose |
|---|---|---|
| `Article` | title, source, url (unique), summary, published_at | Raw evidence layer — one row per ingested article |
| `Trend` | name (unique), trend_score, relevance_score, source_count, articles (M2M), status | A detected topic, with frequency/recency score and 0-100 founder-relevance score |
| `ContentBrief` | trend (1:1), why_trending, why_entrepreneurs_care, content_angle, linkedin_post_idea, instagram_reel_idea, suggested_hook, suggested_title, urgency_score | AI-generated, ready-to-use content brief for one trend |

---

## Design decisions worth knowing for Q&A

- **Relevance scoring is rule-based, not an LLM call.** This makes it instant and
  free to score every trend candidate; OpenAI is reserved for the higher-value job
  of writing the actual brief, only for trends that clear the threshold. Every score
  is fully explainable (which keyword categories matched, and why).
- **Keyword extraction has a graceful fallback.** It tries spaCy noun-chunk extraction
  first; if the model isn't installed, it falls back to a regex-based extractor so the
  pipeline never hard-crashes on a missing dependency.
- **Briefs use strict JSON-output prompting**, parsed defensively (handles markdown
  code-fence wrapping, validates all required keys are present) rather than parsing
  free-form prose — this is what makes 8 structured DB fields reliable.
- **Trend matching is deduped and recency-weighted.** "AI Agents" and "ai agents"
  collapse into one trend; an article published today contributes more to the trend
  score than one from a week ago.
- **Idempotent by design.** Re-running `collect_articles` skips duplicate URLs;
  re-running `generate_briefs` skips trends that already have a brief unless you
  pass `--force`. Safe to run on a cron schedule without runaway API costs or
  duplicate data.

---

## Known limitations (MVP scope, intentional)

- No background task queue (Celery) — commands are run manually or via cron/Task
  Scheduler. Fine for a hackathon; would be the first upgrade for production.
- No trend history graphs, image extraction, or email alerts yet — these were
  listed as bonus features and are not part of the core MVP.
- Relevance scoring keyword lists are a reasonable starting set, not exhaustive —
  easy to extend in `trends/services/relevance_scorer.py`.

"""
Trend scoring service.

Takes raw extracted phrases (which are noisy and inconsistently cased
across different articles) and turns them into clean trend candidates:

1. Normalize phrases so "AI Agents" and "ai agents" are the same trend.
2. Count how many distinct articles mention each normalized phrase.
3. Compute a trend_score that rewards both volume (source_count) and
   recency (articles published more recently count for more) — this is
   what lets us call something a "rising" trend rather than just an
   old topic that happens to appear often.

Scoring formula (kept intentionally simple/explainable for the demo):

    trend_score = sum(recency_weight(article) for each distinct article)

Where recency_weight decays linearly over a 7-day window:
    - published today        -> weight 1.0
    - published 7 days ago   -> weight ~0.0
    - older than 7 days      -> weight 0.1 (still counts a little, but
                                 won't dominate the ranking)

This means a phrase mentioned by 3 articles all published today scores
higher than a phrase mentioned by 5 articles spread over the last month.
"""

from collections import defaultdict
from datetime import datetime, timezone

from trends.services.keyword_extractor import extract_keywords as extract_phrases

RECENCY_WINDOW_DAYS = 7
MIN_SOURCE_COUNT = 2  # a phrase needs to appear in at least this many articles to count as a "trend"


def _recency_weight(published_at):
    """
    Linear decay from 1.0 (published now) to 0.0 (published RECENCY_WINDOW_DAYS
    ago), floored at 0.1 for anything older so old-but-recurring topics don't
    drop to zero entirely.
    """
    if published_at is None:
        return 0.3  # unknown date — treat as mildly recent, not zero

    now = datetime.now(timezone.utc)
    age_days = max((now - published_at).total_seconds() / 86400.0, 0)

    if age_days >= RECENCY_WINDOW_DAYS:
        return 0.1

    return 1.0 - (age_days / RECENCY_WINDOW_DAYS) * 0.9


def build_trend_candidates(articles):
    """
    Given a queryset/list of Article objects, extract and aggregate phrases
    into trend candidates.

    Returns a dict keyed by normalized (lowercase) phrase, with values:
        {
            "display_name": "AI Agents",      # best-cased version seen
            "trend_score": 4.2,
            "source_count": 3,
            "article_ids": [1, 5, 9],
        }
    """
    # normalized_key -> accumulator
    candidates = defaultdict(lambda: {
        "display_names": defaultdict(int),  # casing variant -> count, to pick the most common
        "score_sum": 0.0,
        "article_ids": set(),
    })

    for article in articles:
        text = f"{article.title}. {article.summary}"
        phrases = extract_phrases(text)
        weight = _recency_weight(article.published_at)

        # Use a set so one article mentioning "AI" three times in its text
        # only contributes once to that article's evidence for the phrase.
        seen_in_this_article = set()

        for phrase in phrases:
            # Normalize simple plurals so "founder"/"founders",
            # "agent"/"agents" merge into one trend instead of splitting
            # into near-duplicate cards. Naive (strips trailing "s"), but
            # covers the common case cheaply without a full lemmatizer.
            normalized = phrase.lower()
            key = normalized[:-1] if normalized.endswith("s") and len(normalized) > 4 else normalized

            if key in seen_in_this_article:
                continue
            seen_in_this_article.add(key)

            bucket = candidates[key]
            bucket["display_names"][phrase] += 1
            bucket["score_sum"] += weight
            bucket["article_ids"].add(article.id)
    results = {}
    for key, bucket in candidates.items():
        source_count = len(bucket["article_ids"])
        if source_count < MIN_SOURCE_COUNT:
            continue  # too rare to call it a "trend" yet

        best_display_name = max(bucket["display_names"].items(), key=lambda kv: kv[1])[0]

        results[key] = {
            "display_name": best_display_name,
            "trend_score": round(bucket["score_sum"], 2),
            "source_count": source_count,
            "article_ids": list(bucket["article_ids"]),
        }

    return results

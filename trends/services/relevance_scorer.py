"""
Entrepreneur relevance scoring service.

Deliberately rule-based (not an LLM call) so that scoring every trend
candidate is instant and free. OpenAI is reserved for the more valuable
job of writing the actual content brief (see briefs app), only for trends
that clear a relevance threshold here.

Approach: weighted keyword categories. A trend's display name + the
combined text of its evidence articles is scanned for terms in each
category. Categories carry different weights because, e.g., a funding
mention is a much stronger founder-relevance signal than a vague
"technology" mention.

Score is capped at 100 and floored at 0. This is intentionally simple
and tunable — for a hackathon demo, explainability matters more than
ML sophistication, and you can defend every point of the score.
"""

import re

# category -> (weight, keywords)
# Weight = points added per category match (matched once per category, not
# per keyword occurrence, so a category can't be gamed by repeating a word).
RELEVANCE_CATEGORIES = {
    "funding": (35, [
        "funding", "raised", "raises", "seed round", "series a", "series b",
        "venture capital", "vc", "investment", "investor", "valuation",
        "ipo", "acquisition", "acquired", "grant", "grants",
    ]),
    "startup_core": (30, [
        "startup", "founder", "co-founder", "entrepreneur", "entrepreneurship",
        "bootstrap", "incubator", "accelerator", "pitch deck", "mvp",
        "product-market fit", "saas",
    ]),
    "business_ops": (20, [
        "revenue", "business model", "monetization", "growth", "market",
        "customers", "b2b", "b2c", "pricing", "scaling", "hiring",
        "remote work", "productivity",
    ]),
    "technology": (15, [
        "ai", "artificial intelligence", "machine learning", "api",
        "platform", "app", "software", "fintech", "blockchain", "automation",
        "agent", "agents", "llm", "developer tools",
    ]),
}

# Topics that actively signal LOW relevance, even if a tech/business word
# happens to appear nearby (e.g. "celebrity launches AI app" should not
# score as high as a genuine startup story).
LOW_RELEVANCE_SIGNALS = [
    "celebrity", "gossip", "royal family", "kardashian", "box office",
    "movie review", "tv show", "sports score", "football match",
    "horoscope", "recipe",
]

LOW_RELEVANCE_PENALTY = 25


def score_relevance(trend_name, evidence_text=""):
    """
    Compute a 0-100 entrepreneur relevance score.

    Args:
        trend_name: the trend's display name, e.g. "AI Agents"
        evidence_text: combined text (titles + summaries) of articles
                       backing this trend, for broader context matching.

    Returns: int 0-100
    """
    combined = f"{trend_name} {evidence_text}".lower()
    score = 0
    matched_categories = []

    for category, (weight, keywords) in RELEVANCE_CATEGORIES.items():
        if any(_contains_phrase(combined, kw) for kw in keywords):
            score += weight
            matched_categories.append(category)

    if any(_contains_phrase(combined, signal) for signal in LOW_RELEVANCE_SIGNALS):
        score -= LOW_RELEVANCE_PENALTY

    # Small bonus if a trend hits 3+ categories — genuinely cross-cutting
    # founder topics (e.g. "AI startup raises Series A") are the gold
    # standard for content, so reward that combination explicitly.
    if len(matched_categories) >= 3:
        score += 10

    return max(0, min(100, score))


def _contains_phrase(text, phrase):
    """Word-boundary-safe substring check so 'ai' doesn't match inside 'said'."""
    pattern = r"\b" + re.escape(phrase) + r"\b"
    return re.search(pattern, text) is not None

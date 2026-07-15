"""
OpenAI client service for content brief generation.

Design notes:
- We ask the model for STRICT JSON output and parse it ourselves, rather
  than parsing free-form prose. This is far more reliable for populating
  structured DB fields (ContentBrief has 8 distinct fields).
- All required keys are validated after parsing. If the model returns
  malformed/incomplete JSON, we raise BriefGenerationError with a clear
  message rather than silently saving partial/garbage data.
- The API key and model name come from Django settings (which load from
  .env) — this file never hardcodes credentials.
"""

import json
import logging

from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

REQUIRED_KEYS = [
    "why_trending",
    "why_entrepreneurs_care",
    "content_angle",
    "linkedin_post_idea",
    "instagram_reel_idea",
    "suggested_hook",
    "suggested_title",
    "estimated_lifespan",
    "video_script",
    "remix_template",
    "urgency_score",
]

SYSTEM_PROMPT = """You are a senior content strategist for Kuzana, a media brand that creates \
entrepreneurship content for founders and startups. Given a trending topic and supporting \
evidence from recent news articles, you produce a concise, actionable content brief.

You MUST respond with ONLY a valid JSON object — no markdown formatting, no code fences, \
no preamble or explanation outside the JSON. The JSON object must have exactly these keys:

- "why_trending": string, 1-2 sentences on why this topic is trending right now
- "why_entrepreneurs_care": string, 1-2 sentences on why founders/entrepreneurs should care
- "content_angle": string, 1-2 sentences describing a unique angle Kuzana could take
- "linkedin_post_idea": string, a ready-to-adapt LinkedIn post (3-5 sentences)
- "instagram_reel_idea": string, a short Reel concept/script outline (hook, body, CTA)
- "suggested_hook": string, a short punchy opening line (under 20 words)
- "suggested_title": string, a compelling content title (under 15 words)
- "estimated_lifespan": string, your best estimate of how much longer this specific \
trend will stay culturally relevant/worth posting about, expressed as a short range \
with a unit, e.g. "6-12 hours", "2-3 days", "1-2 weeks". Base this on how fast-moving \
the topic type is (a viral meme/news reaction fades in hours-days; a structural \
industry shift can stay relevant for weeks) and the evidence provided.
- "video_script": string, a ready-to-shoot 30-60 second video script for a single \
founder-facing creator to perform to camera. Structure it in labeled beats separated \
by newlines, e.g. "HOOK (0-3s): ...", "SETUP (3-15s): ...", "PAYOFF (15-45s): ...", \
"CTA (45-60s): ...". Write actual lines to say, not a description of what to say.
- "remix_template": string, 2-4 sentences explaining the *underlying format/structure* \
this trend uses (independent of its specific content) and how to remix that same \
structure into a business/founder story. This should be reusable as a template even \
after this specific trend fades — describe the shape, not just this instance of it.
- "urgency_score": integer 0-100, how time-sensitive this content opportunity is

Keep tone practical and founder-focused, not hype-y. Be specific to the evidence given, \
not generic."""


def _build_user_prompt(trend_name, relevance_score, trend_score, evidence_summaries):
    evidence_block = "\n".join(f"- {s}" for s in evidence_summaries[:6]) or "(no article summaries available)"
    return f"""Trending topic: {trend_name}
Entrepreneur relevance score: {relevance_score}/100
Trend score (frequency/recency weighted): {trend_score}

Evidence from recent articles:
{evidence_block}

Generate the content brief JSON now."""


class BriefGenerationError(Exception):
    """Raised when OpenAI call fails or returns unusable output."""
    pass


def _get_client():
    if not settings.OPENAI_API_KEY:
        raise BriefGenerationError(
            "OPENAI_API_KEY is not set. Add it to your .env file."
        )
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def _strip_code_fences(text):
    """
    Defensive cleanup: even with explicit instructions, some models wrap
    JSON in ```json ... ``` fences. Strip them if present.
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text


def generate_brief_data(trend_name, relevance_score, trend_score, evidence_summaries):
    """
    Call OpenAI to generate brief content for a trend.

    Args:
        trend_name: str, e.g. "AI Agents"
        relevance_score: int 0-100
        trend_score: float
        evidence_summaries: list of strings (article title + summary snippets)

    Returns: dict with all REQUIRED_KEYS populated, plus "_raw" containing
             the original raw text response (for audit storage).

    Raises: BriefGenerationError on any failure (missing key, API error,
            invalid JSON, missing required fields).
    """
    client = _get_client()
    user_prompt = _build_user_prompt(trend_name, relevance_score, trend_score, evidence_summaries)

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=1600,
        )
    except Exception as exc:  # noqa: BLE001
        raise BriefGenerationError(f"OpenAI API call failed: {exc}") from exc

    raw_text = response.choices[0].message.content or ""
    cleaned = _strip_code_fences(raw_text)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise BriefGenerationError(
            f"OpenAI returned invalid JSON: {exc}. Raw response: {raw_text[:300]}"
        ) from exc

    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        raise BriefGenerationError(
            f"OpenAI response missing required keys: {missing}. Raw response: {raw_text[:300]}"
        )

    # Defensive type coercion for urgency_score in case the model returns a string
    try:
        data["urgency_score"] = max(0, min(100, int(data["urgency_score"])))
    except (TypeError, ValueError):
        data["urgency_score"] = 50  # safe neutral default rather than failing the whole brief

    data["_raw"] = raw_text
    return data

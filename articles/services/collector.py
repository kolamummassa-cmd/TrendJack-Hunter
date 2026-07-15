"""
Collector service: fetches RSS feeds and saves new Article rows.

Design notes:
- Dedup is done via Article.url having a unique constraint — we check
  existence before inserting rather than relying on try/except for every
  row, since checking is cheap and gives us a clean count of "new" vs
  "skipped" articles for reporting.
- We deliberately do NOT raise on a single feed failure. One broken/slow
  RSS source should not stop the whole collection run. Failures are
  collected and reported back to the caller (the management command).
- published_at parsing is defensive: feeds vary wildly in date formats.
  feedparser normalizes most of this into `published_parsed`, but we
  fall back to None if it's missing rather than guessing.
"""

import logging
from datetime import datetime, timezone

import feedparser

from articles.models import Article
from articles.services.rss_sources import RSS_SOURCES

logger = logging.getLogger(__name__)


def _parse_published_date(entry):
    """
    Convert feedparser's published_parsed (a time.struct_time, UTC-ish)
    into a timezone-aware datetime. Returns None if unavailable/unparseable.
    """
    time_struct = getattr(entry, "published_parsed", None) or getattr(
        entry, "updated_parsed", None
    )
    if not time_struct:
        return None
    try:
        return datetime(*time_struct[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _extract_summary(entry):
    """
    Pull the best available short description from a feed entry.
    Falls back through summary -> description -> empty string.
    """
    return getattr(entry, "summary", "") or getattr(entry, "description", "") or ""


def collect_from_feed(source_name, feed_url):
    """
    Fetch a single RSS feed and save any new articles.

    Returns a dict: {"new": int, "skipped": int, "error": str|None}
    """
    result = {"new": 0, "skipped": 0, "error": None}

    try:
        parsed_feed = feedparser.parse(feed_url)
    except Exception as exc:  # noqa: BLE001 - we want to catch and report, not crash
        result["error"] = str(exc)
        logger.warning("Failed to fetch feed %s (%s): %s", source_name, feed_url, exc)
        return result

    def _clean_title(title):
        """
        Google News RSS aggregates from many publishers and appends
        " - PublisherName" to every title (e.g. "Startup Raises $5M - Yahoo Finance").
        Since this suffix recurs across many articles, it gets misidentified as
        a 'trend' by the keyword extractor. Stripping it here fixes the problem
        at the source, before it ever reaches trend detection.
        """
        if " - " in title:
            title = title.rsplit(" - ", 1)[0].strip()
        return title

    # feedparser sets bozo=1 on malformed feeds but often still parses
    # partial entries, so we don't bail out — just log it.
    if getattr(parsed_feed, "bozo", 0):
        logger.info("Feed %s flagged as malformed (bozo), continuing anyway", source_name)

    for entry in parsed_feed.entries:
        url = getattr(entry, "link", "").strip()
        title = _clean_title(getattr(entry, "title", "").strip())
        if not url or not title:
            result["skipped"] += 1
            continue

        if Article.objects.filter(url=url).exists():
            result["skipped"] += 1
            continue

        Article.objects.create(
            title=title[:500],
            source=source_name,
            url=url[:1000],
            summary=_extract_summary(entry)[:5000],
            published_at=_parse_published_date(entry),
        )
        result["new"] += 1

    return result


def collect_all():
    """
    Run collection across every source in RSS_SOURCES.

    Returns a list of per-source result dicts, e.g.:
    [{"source": "TechCrunch", "new": 5, "skipped": 2, "error": None}, ...]
    Used by the collect_articles management command to print a summary.
    """
    summary = []
    for source in RSS_SOURCES:
        result = collect_from_feed(source["name"], source["url"])
        summary.append({"source": source["name"], **result})
    return summary

"""
Collector service: searches YouTube for short-form videos matching our
tracked queries and saves new Article rows (source_type=youtube).

Uses the official YouTube Data API v3 `search.list` endpoint, which is
free for this volume of use (10,000 quota units/day; each search call
costs 100 units, so this comfortably supports dozens of queries/day).

Docs: https://developers.google.com/youtube/v3/docs/search/list
Get an API key: https://console.cloud.google.com/apis/credentials
(enable "YouTube Data API v3" on the project first).
"""

import logging
from datetime import datetime, timezone

from datetime import timedelta

import requests
from django.conf import settings

from articles.models import Article
from articles.services.youtube_sources import YOUTUBE_SEARCH_QUERIES

logger = logging.getLogger(__name__)

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def _parse_published_date(published_raw):
    if not published_raw:
        return None
    try:
        return datetime.strptime(published_raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def collect_from_query(query):
    """
    Search YouTube for one query and save any new short-form videos found.

    Returns a dict: {"new": int, "skipped": int, "error": str|None}
    """
    result = {"new": 0, "skipped": 0, "error": None}

    if not settings.YOUTUBE_API_KEY:
        result["error"] = "YOUTUBE_API_KEY is not set in settings/.env"
        return result

    params = {
        "key": settings.YOUTUBE_API_KEY,
        "part": "snippet",
        "q": query,
        "type": "video",
        "videoDuration": "short",  # YouTube's own "under 4 minutes" filter — covers Shorts
        "order": "date",
        "publishedAfter": (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "maxResults": 25,
        "relevanceLanguage": "en",
    }

    try:
        response = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # noqa: BLE001 - one bad query shouldn't stop the whole run
        result["error"] = str(exc)
        logger.warning("YouTube search failed for query '%s': %s", query, exc)
        return result

    for item in data.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        title = snippet.get("title", "").strip()

        if not video_id or not title:
            result["skipped"] += 1
            continue

        url = f"https://www.youtube.com/watch?v={video_id}"

        if Article.objects.filter(url=url).exists():
            result["skipped"] += 1
            continue

        Article.objects.create(
            title=title[:500],
            source=f"YouTube - {snippet.get('channelTitle', 'Unknown channel')}",
            url=url,
            summary=snippet.get("description", "")[:5000],
            published_at=_parse_published_date(snippet.get("publishedAt")),
            source_type=Article.SOURCE_YOUTUBE,
        )
        result["new"] += 1

    return result


def collect_all():
    """
    Run collection across every query in YOUTUBE_SEARCH_QUERIES.

    Returns a list of per-query result dicts, matching the shape used by
    articles/services/collector.py's collect_all(), so both can be reported
    on the same way.
    """
    summary = []
    for query in YOUTUBE_SEARCH_QUERIES:
        result = collect_from_query(query)
        summary.append({"source": f"YouTube: '{query}'", **result})
    return summary

"""
Collector service: fetches "top of the day" posts from tracked subreddits
and saves new Article rows (source_type=reddit).

Uses Reddit's OAuth2 "script app" flow (client_credentials grant), which
is the correct, ToS-compliant way to access Reddit's API for commercial
use — the plain reddit.com/*.json endpoints without auth are rate-limited
and not meant for production/commercial apps.

Setup:
1. Go to https://www.reddit.com/prefs/apps
2. Click "create another app...", choose type "script"
3. Note the client id (under the app name) and client secret
4. Put them in .env as REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET

Docs: https://www.reddit.com/dev/api/
"""

import logging
from datetime import datetime, timezone

import requests
from django.conf import settings

from articles.models import Article
from articles.services.reddit_sources import REDDIT_SUBREDDITS

logger = logging.getLogger(__name__)

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"


def _get_access_token():
    auth = requests.auth.HTTPBasicAuth(settings.REDDIT_CLIENT_ID, settings.REDDIT_CLIENT_SECRET)
    data = {"grant_type": "client_credentials"}
    headers = {"User-Agent": settings.REDDIT_USER_AGENT}
    response = requests.post(TOKEN_URL, auth=auth, data=data, headers=headers, timeout=15)
    response.raise_for_status()
    return response.json()["access_token"]


def collect_from_subreddit(subreddit, access_token):
    """
    Fetch today's top posts from one subreddit and save any new ones.

    Returns a dict: {"new": int, "skipped": int, "error": str|None}
    """
    result = {"new": 0, "skipped": 0, "error": None}

    url = f"https://oauth.reddit.com/r/{subreddit}/top"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": settings.REDDIT_USER_AGENT,
    }
    params = {"t": "day", "limit": 25}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # noqa: BLE001 - one bad subreddit shouldn't stop the whole run
        result["error"] = str(exc)
        logger.warning("Reddit fetch failed for r/%s: %s", subreddit, exc)
        return result

    for child in data.get("data", {}).get("children", []):
        post = child.get("data", {})
        title = post.get("title", "").strip()
        permalink = post.get("permalink", "")

        if not title or not permalink:
            result["skipped"] += 1
            continue

        post_url = f"https://www.reddit.com{permalink}"

        if Article.objects.filter(url=post_url).exists():
            result["skipped"] += 1
            continue

        created_utc = post.get("created_utc")
        published_at = (
            datetime.fromtimestamp(created_utc, tz=timezone.utc) if created_utc else None
        )

        Article.objects.create(
            title=title[:500],
            source=f"Reddit - r/{subreddit}",
            url=post_url[:1000],
            summary=(post.get("selftext", "") or "")[:5000],
            published_at=published_at,
            source_type=Article.SOURCE_REDDIT,
        )
        result["new"] += 1

    return result


def collect_all():
    """
    Run collection across every subreddit in REDDIT_SUBREDDITS.

    Returns a list of per-subreddit result dicts, matching the shape used
    by the RSS and YouTube collectors.
    """
    try:
        access_token = _get_access_token()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not authenticate with Reddit: %s", exc)
        return [{"source": "Reddit", "new": 0, "skipped": 0, "error": str(exc)}]

    summary = []
    for subreddit in REDDIT_SUBREDDITS:
        result = collect_from_subreddit(subreddit, access_token)
        summary.append({"source": f"Reddit: r/{subreddit}", **result})
    return summary

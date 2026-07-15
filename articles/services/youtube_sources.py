"""
YOUTUBE_SEARCH_QUERIES is the single source of truth for which search terms
collect_youtube runs against YouTube's search endpoint. Each query pulls
back a batch of Shorts-length videos matching that term, ranked by views.

To add a new topic area for monitoring, just add a string here — no other
code needs to change.
"""

YOUTUBE_SEARCH_QUERIES = [
    "startup funding",
    "entrepreneur tips",
    "small business Kenya",
    "side hustle ideas",
    "founder story",
    "business trends 2026",
]

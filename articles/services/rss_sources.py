"""
RSS_SOURCES is the single source of truth for which feeds collect_articles
pulls from. Each entry has:

- "name": human-readable source label, stored on Article.source
- "url": the RSS/Atom feed URL

To add a new source for the hackathon demo, just add an entry here —
no other code needs to change.
"""

RSS_SOURCES = [
    {
        "name": "Google News - Startups",
        "url": "https://news.google.com/rss/search?q=startup+funding&hl=en-US&gl=US&ceid=US:en",
    },
    {
        "name": "Google News - AI Business",
        "url": "https://news.google.com/rss/search?q=AI+business+entrepreneurs&hl=en-US&gl=US&ceid=US:en",
    },
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
    },
    {
        "name": "TechCrunch - Startups",
        "url": "https://techcrunch.com/category/startups/feed/",
    },
    {
        "name": "VentureBeat",
        "url": "https://venturebeat.com/feed/",
    },
    {
        "name": "Entrepreneur.com",
        "url": "https://www.entrepreneur.com/latest.rss",
    },
    {
        "name": "Google News - Kenya Startups",
        "url": "https://news.google.com/rss/search?q=Kenya+startup+fintech&hl=en-US&gl=US&ceid=US:en",
    },
]

# trends/services/keyword_extractor.py

import re
from collections import Counter

# Words that should never be trends
STOPWORDS = {
    "which", "where", "when", "what", "who", "how", "why", "that", "this",
    "these", "those", "they", "them", "their", "there", "here", "then",
    "than", "the", "a", "an", "all", "some", "any", "each", "every",
    "other", "others", "another", "such", "more", "most", "much", "many",
    "few", "own", "same", "just", "also", "even", "still", "already",
    "something", "someone", "anyone", "everyone", "nothing", "everything",
    "work", "end", "mid", "way", "time", "day", "week", "year", "month",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    "users", "teams", "costs", "files", "scale", "favor", "planning",
    "improvements", "software", "companies", "defense", "cars", "prompts",
    "register", "pass", "reason", "system", "model", "release", "platform",
    "agents", "agent", "researchers", "enterprises",
    "crunchbase news", "yahoo finance", "business insider",
    "techcrunch", "venturebeat", "tech funding news",
    "entrepreneur.com", "google news",
    "funding round", "seed funding", "startup daily funding report",
    "funding news", "daily funding report",
}

# Patterns to reject
JUNK_PATTERNS = [
    r"^\d+$",                    # pure numbers
    r"^\$[\d,.]+[MBK]?$",       # money like $50M — keep as part of phrase, not alone
    r"^\d{1,2}:\d{2}",          # times like 11:59
    r"<[^>]+>",                  # HTML tags
    r"&[a-z#0-9]+;",            # HTML entities like &amp; &#x27;
    r"target=",                  # HTML attributes
    r"font:",                    # CSS
    r"^\W+$",                    # only punctuation/symbols
    r"^#\w+$",                   # standalone hashtags like #Shorts, #ad
]


def is_junk(phrase: str) -> bool:
    phrase_lower = phrase.lower().strip()

    # Too short
    if len(phrase_lower) < 4:
        return True
    if len(phrase_lower.split()) < 2:
        return True

    # In stopwords — reject if the whole phrase matches, OR if any
    # individual word in the phrase is a stopword. Fragments like
    # "that actually work" aren't themselves in STOPWORDS, but "that"
    # and "work" are — this catches junk built from filler words that
    # spaCy sometimes glues onto a real topic (common with informal,
    # unpunctuated YouTube titles).
    words = phrase_lower.split()
    if phrase_lower in STOPWORDS or any(w in STOPWORDS for w in words):
        return True

    first_word = phrase_lower.split()[0] if phrase_lower.split() else ""
    if first_word in {
        "the", "a", "an", "your", "our", "their", "its", "my",
        "that", "which", "who", "whom", "whose", "what",
        "this", "these", "those",
    }:
        return True

    # Matches junk patterns
    for pattern in JUNK_PATTERNS:
        if re.search(pattern, phrase, re.IGNORECASE):
            return True
    if len(words) > 8:
        return True
    return False


def extract_keywords(text: str) -> list[str]:
    """
    Extract candidate trend phrases from text.
    Tries spaCy first, falls back to regex if model not available.
    """
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
        return _extract_spacy(text, nlp)
    except Exception:
        return _extract_regex(text)


def _extract_spacy(text: str, nlp) -> list[str]:
    doc = nlp(text[:100000])  # cap to avoid memory issues
    phrases = []
    for chunk in doc.noun_chunks:
        # Only keep chunks where the root is a proper noun or noun (not pronoun/determiner)
        if chunk.root.pos_ in ("NOUN", "PROPN") and chunk.root.dep_ not in ("det",):
            phrase = chunk.text.strip()
            if not is_junk(phrase):
                phrases.append(phrase)
    return phrases


def _extract_regex(text: str) -> list[str]:
    # Match capitalized phrases (2-4 words) as candidate proper nouns
    pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b'
    matches = re.findall(pattern, text)
    return [m for m in matches if not is_junk(m)]
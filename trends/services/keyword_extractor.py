# trends/services/keyword_extractor.py

import logging
import re
from collections import Counter

logger = logging.getLogger(__name__)

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

# Short "words" that are legitimate on their own (acronyms/abbreviations) and
# shouldn't trip the gibberish guard below, even though they're <= 2 letters.
ALLOWED_SHORT_WORDS = {
    "ai", "vc", "vr", "ar", "ml", "io", "us", "uk", "eu", "3d", "ux", "ui",
}


def _has_gibberish_short_word(words: list[str]) -> bool:
    """
    Catches fragments like "Cr In" or "Must Know" made of near-meaningless
    short tokens — real multi-word trend phrases almost always have at least
    one word longer than 2 letters that isn't a stopword.
    """
    for w in words:
        stripped = re.sub(r"[^a-z0-9]", "", w)
        if stripped and len(stripped) <= 2 and stripped not in ALLOWED_SHORT_WORDS:
            return True
    return False


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

    # Gibberish/fragment guard — e.g. "Cr In", "Must Know"
    if _has_gibberish_short_word(words):
        return True

    return False


# --- spaCy model loading -----------------------------------------------
# Loaded once and cached at module level. Previously this was reloaded from
# disk on every single call, which was slow and meant any transient failure
# (e.g. the model not being installed at all) silently degraded every future
# call too, with no way to notice it had happened.
_NLP = None
_NLP_LOAD_ATTEMPTED = False


def _get_nlp():
    global _NLP, _NLP_LOAD_ATTEMPTED
    if _NLP is not None or _NLP_LOAD_ATTEMPTED:
        return _NLP

    _NLP_LOAD_ATTEMPTED = True
    try:
        import spacy
        _NLP = spacy.load("en_core_web_sm")
    except Exception:
        logger.exception(
            "Failed to load spaCy model 'en_core_web_sm' — falling back to the "
            "regex keyword extractor for the rest of this process's lifetime. "
            "Trend name quality will be significantly degraded (no "
            "part-of-speech tagging or named-entity filtering, so person names "
            "and sentence fragments will leak through as 'trends'). Make sure "
            "en_core_web_sm is actually installed in this environment."
        )
        _NLP = None
    return _NLP


def extract_keywords(text: str) -> list[str]:
    """
    Extract candidate trend phrases from text.
    Uses spaCy (POS + named-entity aware) when the model is available,
    falling back to a much cruder regex extractor if it isn't.
    """
    nlp = _get_nlp()
    if nlp is not None:
        return _extract_spacy(text, nlp)
    return _extract_regex(text)


def _chunk_overlaps_person(chunk, person_spans) -> bool:
    for ent in person_spans:
        if chunk.start < ent.end and chunk.end > ent.start:
            return True
    return False


def _extract_spacy(text: str, nlp) -> list[str]:
    doc = nlp(text[:100000])  # cap to avoid memory issues

    # A bare person's name ("Elon Musk", "Pete Davidson") isn't itself a
    # postable "trend" the way a topic/event/company is — reject any noun
    # chunk that overlaps a PERSON entity.
    person_spans = [ent for ent in doc.ents if ent.label_ == "PERSON"]

    phrases = []
    for chunk in doc.noun_chunks:
        # Only keep chunks where the root is a proper noun or noun (not pronoun/determiner)
        if chunk.root.pos_ in ("NOUN", "PROPN") and chunk.root.dep_ not in ("det",):
            phrase = chunk.text.strip()
            if is_junk(phrase):
                continue
            if _chunk_overlaps_person(chunk, person_spans):
                continue
            phrases.append(phrase)
    return phrases


def _extract_regex(text: str) -> list[str]:
    # Match capitalized phrases (2-4 words) as candidate proper nouns
    pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b'
    matches = re.findall(pattern, text)
    return [m for m in matches if not is_junk(m)]

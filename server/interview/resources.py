"""Free learning material for a topic or skill, from a curated, link-checked list (no web search, no model).

Each entry pairs exact terms with links to official docs or well-known free courses. A topic gets the
links of the entries that match the most of its terms, so a passing word ("pipelines" in a RAG topic)
does not pull in an unrelated entry.
"""
import json
import re
from pathlib import Path

PATH = Path(__file__).resolve().parent / 'data' / 'learning_resources.json'
MAX_LINKS = 3
_entries = None


def entries():
    global _entries
    if _entries is None:
        _entries = json.loads(PATH.read_text(encoding='utf-8'))['entries']
    return _entries


def for_text(*texts):
    """Up to MAX_LINKS links for the given topic texts (topic label, question, tags, requirement)."""
    text = ' '.join(t for t in texts if t).lower()
    scored = []
    for order, entry in enumerate(entries()):
        hits = sum(bool(re.search(r'(?<![a-z0-9])' + re.escape(term) + r'(?![a-z0-9])', text)) for term in entry['terms'])
        if hits:
            scored.append((-hits, order, entry))
    if not scored:
        return []
    top = min(s[0] for s in scored)
    links, seen = [], set()
    for _, _, entry in sorted((s for s in scored if s[0] == top), key=lambda s: s[:2]):
        for link in entry['links']:
            if link['url'] not in seen and len(links) < MAX_LINKS:
                seen.add(link['url'])
                links.append(link)
    return links

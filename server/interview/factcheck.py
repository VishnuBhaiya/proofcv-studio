"""Fact check: compare what the candidate says about themselves with their confirmed profile.

Runs locally. Every first-person sentence ("I", "my", "we") is a claim. Each
claim is matched to its closest confirmed fact with MiniLM, and three rules
flag details the profile cannot back up: numbers, named tools, and leadership.
A flag means "not in your confirmed profile", not "false".
"""
import re
from difflib import SequenceMatcher

import numpy as np

from .fit import evidence_units, keyword_pattern
from .star import split_sentences

# Calibrated on true and invented claims about the labelled sample profile.
SUPPORTED_SIMILARITY = 0.45
WEAK_SIMILARITY = 0.35
FIRST_PERSON = re.compile(r"\b(i|i'm|i've|i'd|my|me|we|our|us)\b", re.I)
# "I would report precision" describes what the speaker would do, not something they did.
# "I'd" is hypothetical in "I'd use YOLO" but past ("I had") in "I'd deployed it on AWS".
HYPOTHETICAL = re.compile(r"\b(i|we) (would|could|should|might|will)\b|\b(i|we)'ll\b|\b(i|we)'d (?!\w+ed\b|(been|built|done|made|led|run|won|got|had|taken|written|seen|worked)\b)", re.I)
# Greetings and thanks ("Hi, I'm Avery.", "Thank you.") are not claims about experience.
COURTESY = re.compile(r"^\W*(hi|hello|hey|good (morning|afternoon|evening)|thanks|thank you)\b", re.I)
# "My name is Avery", "I'm Avery Morgan": the name a candidate introduces themselves with.
STATED_NAME = re.compile(r"\b(?i:my name is|my name's|i am|i'm|this is)\s+([A-Z][a-z'-]+(?:\s+[A-Z]\.)?(?:\s+[A-Z][a-z'-]+)?)")
NOT_NAMES = {'From', 'Here', 'Currently', 'Really', 'An', 'A', 'The', 'Studying', 'Working', 'Applying', 'Interested', 'Passionate', 'Based', 'Looking'}
NAME_SIMILARITY = 0.75  # Allows small recognition slips ("Averi", "Every"), not a different name.
SHORT_NAME_SIMILARITY = 0.6  # One wrong letter in a short name ("Sem" for "Sam"), if the first letter matches.
LEADERSHIP_CLAIM = re.compile(r"\b(i (led|managed|supervised|ran the team)|i was the (lead|leader|manager|captain)|team lead|in charge of (a|the) team)\b", re.I)
LEADERSHIP_EVIDENCE = re.compile(r"\b(led|leader|leading|team lead|managed a|supervised|captain\w*|mentor\w*|head of|in charge of)\b", re.I)
TOOLS = ('python', 'java', 'c++', 'sql', 'pytorch', 'tensorflow', 'keras', 'scikit-learn', 'numpy', 'pandas', 'opencv', 'yolo',
         'docker', 'kubernetes', 'terraform', 'aws', 'azure', 'gcp', 'spark', 'hadoop', 'kafka', 'airflow', 'langchain', 'langgraph',
         'llamaindex', 'langflow', 'faiss', 'chroma', 'pinecone', 'neo4j', 'postgresql', 'mongodb', 'fastapi', 'flask', 'django',
         'mlflow', 'dvc', 'optuna', 'hugging face', 'bert', 'gpt', 'openai', 'gemini', 'react', 'git', 'github actions', 'jenkins',
         'linux', 'tableau', 'power bi', 'matplotlib', 'seaborn', 'jetson', 'cuda', 'onnx', 'tensorrt', 'pytest')
NUMBER_WORDS = {w: i for i, w in enumerate('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split())}
NUMBER_WORDS.update({'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90})


def word_numbers(text):
    """Numbers written in words: 'two hundred' -> 200, 'seventy-eight' -> 78, 'three thousand' -> 3000."""
    found, total, current, active = set(), 0, 0, False
    for token in re.findall(r'[a-z]+', text.lower().replace('-', ' ')) + ['']:
        if token in NUMBER_WORDS:
            current, active = current + NUMBER_WORDS[token], True
        elif token == 'hundred':
            current, active = (current or 1) * 100, True
        elif token == 'thousand':
            total, current, active = total + (current or 1) * 1000, 0, True
        elif token == 'and' and active:
            continue
        elif active:
            found.add(str(total + current))
            total, current, active = 0, 0, False
    return found


def numbers(text):
    """Digits in the text, plus numbers written in words (as in many profiles)."""
    return set(re.findall(r'\d+(?:\.\d+)?', text.replace(',', ''))) | word_numbers(text)


def same_name(heard, name):
    ratio = SequenceMatcher(None, heard, name).ratio()
    return ratio >= NAME_SIMILARITY or (heard[:1] == name[:1] and ratio >= SHORT_NAME_SIMILARITY)


def name_claim(transcript, profile):
    """The name said in the first few sentences, checked against the profile name; None if no name was said."""
    profile_names = [n.lower() for n in re.findall(r"[A-Za-z'-]+", profile.get('name') or '')]
    if not profile_names:
        return None
    for sentence in split_sentences(transcript)[:3]:
        match = STATED_NAME.search(sentence)
        if not match or match.group(1).split()[0] in NOT_NAMES:
            continue
        said = re.findall(r"[A-Za-z'-]+", match.group(1))
        known = all(any(same_name(word.lower(), name) for name in profile_names) for word in said if len(word) > 1)
        flags = [] if known else [{'type': 'name', 'value': match.group(1),
                 'message': f'You introduced yourself as "{match.group(1)}", but the name in your confirmed profile is {profile["name"]}.'}]
        return {'text': sentence, 'status': 'supported' if known else 'unmatched', 'similarity': 1.0 if known else 0.0,
                'support': {'label': 'Name', 'text': profile['name']} if known else None, 'flags': flags}
    return None


def honesty(result):
    """0-100: how much of what was claimed the profile backs. Supported claims count fully, loosely
    matched ones partly and unmatched ones not at all; each flagged detail costs a further 25."""
    claims = result['claims']
    if not claims:
        return None
    backed = sum(CLAIM_CREDIT[c['status']] for c in claims) / len(claims)
    return max(0, round(backed * 100) - 25 * sum(len(c['flags']) for c in claims))


CLAIM_CREDIT = {'supported': 1.0, 'weak': 0.6, 'unmatched': 0.0}


def claim_numbers(text):
    """Numbers worth checking in a claim: digits, and number words from ten up ("ninety percent"),
    but not "one" or "two", which are usually ordinary words ("one of my projects")."""
    return set(re.findall(r'\d+(?:\.\d+)?', text.replace(',', ''))) | {n for n in word_numbers(text) if int(n) >= 10}


def check(transcript, profile, backend, personal_story=True):
    """Claims with their closest supporting fact and any unsupported details.

    In a personal story, sentences with numbers count as claims even without "I"
    ("recall improved to 78%"). In a technical explanation they do not, so that
    "a threshold like 0.5" is not flagged.
    """
    named = name_claim(transcript, profile)
    claims = [s for s in split_sentences(transcript)
              if (FIRST_PERSON.search(s) or (personal_story and claim_numbers(s))) and not HYPOTHETICAL.search(s) and not COURTESY.search(s)
              and s != (named or {}).get('text')]
    units = evidence_units(profile)
    if not claims:
        found = [named] if named else []
        result = {'claims': found, 'notes': [c['flags'][0]['message'] for c in found if c['flags']] or ['No first-person claims to check.']}
        return {**result, 'score': honesty(result)}
    profile_text = ' '.join(u['text'] for u in units).lower()
    profile_numbers = numbers(profile_text)
    profile_tools = {t for t in TOOLS + tuple(s.lower() for s in profile.get('skills') or []) if keyword_pattern(t).search(profile_text)}
    shows_leadership = bool(LEADERSHIP_EVIDENCE.search(profile_text))
    similarities = np.asarray(backend.encode(claims)) @ np.asarray(backend.encode([u['text'] for u in units])).T if units else np.zeros((len(claims), 0))
    results = []
    for i, claim in enumerate(claims):
        lowered = claim.lower()
        flags = []
        for value in sorted(claim_numbers(claim) - profile_numbers):
            shown = value + ('%' if re.search(re.escape(value) + r'\s*(%|percent)', lowered) else '')
            flags.append({'type': 'number', 'value': shown, 'message': f'"{shown}" is not in your confirmed profile. Be ready to back it up, or add it to your profile.'})
        for tool in TOOLS:
            said = re.search(keyword_pattern(tool).pattern, claim, re.I) if tool not in profile_tools else None
            if said:
                flags.append({'type': 'tool', 'value': tool, 'said': said.group(0), 'message': f'You mentioned {said.group(0)}, which is not in your confirmed profile.'})
        if LEADERSHIP_CLAIM.search(claim) and not shows_leadership:
            flags.append({'type': 'leadership', 'value': LEADERSHIP_CLAIM.search(claim).group(0), 'message': 'This is a leadership claim, but nothing in your confirmed profile shows leading others.'})
        best = int(similarities[i].argmax()) if units else None
        similarity = float(similarities[i, best]) if units else 0.0
        status = 'supported' if similarity >= SUPPORTED_SIMILARITY else 'weak' if similarity >= WEAK_SIMILARITY else 'unmatched'
        results.append({'text': claim, 'status': status, 'similarity': round(similarity, 3),
                        'support': {k: units[best][k] for k in ('label', 'text')} if units and status != 'unmatched' else None, 'flags': flags})
    if named:
        results.insert(0, named)
    flagged = sum(bool(r['flags']) for r in results)
    unmatched = sum(r['status'] == 'unmatched' for r in results)
    notes = []
    if flagged:
        notes.append(f'{flagged} of your {len(results)} claims include details that are not in your confirmed profile. Only say what you can back up, or add it to your profile first.')
    if unmatched:
        notes.append(f'{unmatched} claim{"s" if unmatched > 1 else ""} could not be matched to anything in your profile. Interviewers often ask follow-up questions, so make sure you can expand on {"them" if unmatched > 1 else "it"}.')
    if not notes:
        notes.append('Everything you said about yourself matches your confirmed profile.')
    result = {'claims': results, 'notes': notes}
    return {**result, 'score': honesty(result)}

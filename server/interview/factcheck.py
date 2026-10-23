"""Fact check: compare what the candidate says about themselves with their confirmed profile.

Runs locally. Every first-person sentence ("I", "my", "we") is a claim. Each
claim is matched to its closest confirmed fact with MiniLM, and three rules
flag details the profile cannot back up: numbers, named tools, and leadership.
A flag means "not in your confirmed profile", not "false".
"""
import re

import numpy as np

from .fit import evidence_units, keyword_pattern
from .star import split_sentences

# Calibrated on true and invented claims about the labelled sample profile.
SUPPORTED_SIMILARITY = 0.45
WEAK_SIMILARITY = 0.35
FIRST_PERSON = re.compile(r"\b(i|i'm|i've|i'd|my|me|we|our|us)\b", re.I)
# "I would report precision" describes what the speaker would do, not something they did.
HYPOTHETICAL = re.compile(r"\b(i|we) (would|could|should|might|will)\b|\b(i|we)'(d|ll)\b", re.I)
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


def check(transcript, profile, backend, personal_story=True):
    """Claims with their closest supporting fact and any unsupported details.

    In a personal story, sentences with numbers count as claims even without "I"
    ("recall improved to 78%"). In a technical explanation they do not, so that
    "a threshold like 0.5" is not flagged.
    """
    claims = [s for s in split_sentences(transcript)
              if (FIRST_PERSON.search(s) or (personal_story and re.search(r'\d', s))) and not HYPOTHETICAL.search(s)]
    units = evidence_units(profile)
    if not claims:
        return {'claims': [], 'notes': ['No first-person claims to check.']}
    profile_text = ' '.join(u['text'] for u in units).lower()
    profile_numbers = numbers(profile_text)
    profile_tools = {t for t in TOOLS + tuple(s.lower() for s in profile.get('skills') or []) if keyword_pattern(t).search(profile_text)}
    shows_leadership = bool(LEADERSHIP_EVIDENCE.search(profile_text))
    similarities = np.asarray(backend.encode(claims)) @ np.asarray(backend.encode([u['text'] for u in units])).T if units else np.zeros((len(claims), 0))
    results = []
    for i, claim in enumerate(claims):
        lowered = claim.lower()
        flags = []
        for value in sorted(set(re.findall(r'\d+(?:\.\d+)?', claim.replace(',', ''))) - profile_numbers):
            shown = value + ('%' if re.search(re.escape(value) + r'\s*(%|percent)', lowered) else '')
            flags.append({'type': 'number', 'value': shown, 'message': f'"{shown}" is not in your confirmed profile. Be ready to back it up, or add it to your profile.'})
        for tool in TOOLS:
            said = re.search(keyword_pattern(tool).pattern, claim, re.I) if tool not in profile_tools else None
            if said:
                flags.append({'type': 'tool', 'value': tool, 'message': f'You mentioned {said.group(0)}, which is not in your confirmed profile.'})
        if LEADERSHIP_CLAIM.search(claim) and not shows_leadership:
            flags.append({'type': 'leadership', 'value': LEADERSHIP_CLAIM.search(claim).group(0), 'message': 'This is a leadership claim, but nothing in your confirmed profile shows leading others.'})
        best = int(similarities[i].argmax()) if units else None
        similarity = float(similarities[i, best]) if units else 0.0
        status = 'supported' if similarity >= SUPPORTED_SIMILARITY else 'weak' if similarity >= WEAK_SIMILARITY else 'unmatched'
        results.append({'text': claim, 'status': status, 'similarity': round(similarity, 3),
                        'support': {k: units[best][k] for k in ('label', 'text')} if units and status != 'unmatched' else None, 'flags': flags})
    flagged = sum(bool(r['flags']) for r in results)
    unmatched = sum(r['status'] == 'unmatched' for r in results)
    notes = []
    if flagged:
        notes.append(f'{flagged} of your {len(results)} claims include details that are not in your confirmed profile. Only say what you can back up, or add it to your profile first.')
    if unmatched:
        notes.append(f'{unmatched} claim{"s" if unmatched > 1 else ""} could not be matched to anything in your profile. Interviewers often ask follow-up questions, so make sure you can expand on {"them" if unmatched > 1 else "it"}.')
    if not notes:
        notes.append('Everything you said about yourself matches your confirmed profile.')
    return {'claims': results, 'notes': notes}

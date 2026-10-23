"""Technical answers: which of the question's key points did the answer cover?

Runs locally. The transcript is cut into short overlapping word windows so a
key point can match part of a long spoken sentence. Each key point is then
compared with every window by MiniLM similarity, and its important terms are
looked for exactly. This measures coverage of expected ideas, not whether every
statement is correct.
"""
import re

import numpy as np

WINDOW_WORDS, WINDOW_STEP = 14, 5
# Calibrated on written good, partial and off-topic answers (see test_content.py).
COVERED_SIMILARITY = 0.55
PARTIAL_SIMILARITY = 0.40
TERM_SHARE_FOR_COVERED = 0.5
# Spoken answers often say the words where key points use the acronym, or the reverse.
ACRONYMS = {'iou': 'intersection over union', 'map': 'mean average precision', 'rag': 'retrieval augmented generation',
            'llm': 'large language model', 'nlp': 'natural language processing', 'cnn': 'convolutional neural network',
            'ci/cd': 'continuous integration', 'lora': 'low rank adaptation', 'hnsw': 'hierarchical navigable small world'}
STOPWORDS = set('a an and are as at be by can each for from has have how in into is it its of on or such that the their them then there these this those to use used using was what when where which while with without you your one more less than so not only also both any every same other'.split())


def normalise(text):
    """Add the missing form of each acronym: 'IoU' gains 'intersection over union' and vice versa."""
    lowered = text.lower().replace('-', ' ')
    extra = []
    for short, long in ACRONYMS.items():
        has_short = re.search(r'(?<![a-z0-9])' + re.escape(short) + r'(?![a-z0-9])', lowered)
        if has_short and long not in lowered:
            extra.append(long)
        elif long in lowered and not has_short:
            extra.append(short)
    return f"{text} ({', '.join(extra)})" if extra else text


def windows(text):
    """Overlapping chunks of about WINDOW_WORDS words, plus every full sentence."""
    words = text.split()
    chunks = [' '.join(words[i:i + WINDOW_WORDS]) for i in range(0, max(len(words) - WINDOW_WORDS, 0) + 1, WINDOW_STEP)]
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.split()) >= 3]
    return list(dict.fromkeys(c for c in chunks + sentences if c))


def terms(text):
    """Content words of a key point, e.g. 'IoU threshold decides...' -> iou, threshold, decides."""
    return list(dict.fromkeys(t for t in re.findall(r"[a-z0-9][a-z0-9+#/.-]*", text.lower().replace('-', ' ')) if t not in STOPWORDS and len(t) > 2))


def term_present(term, text):
    stem = term[:-1] if term.endswith('s') and len(term) > 4 else term
    return re.search(r'(?<![a-z0-9])' + re.escape(stem), text) is not None


def score(transcript, key_points, backend):
    """Covered / partly covered / missed for each key point, with the best matching quote."""
    chunks = windows(transcript)
    if not chunks:
        return {'key_points': [{'text': k, 'status': 'missed', 'similarity': 0.0, 'quote': None, 'terms_found': []} for k in key_points],
                'score': 0.0, 'notes': ['Not enough speech to check the content.']}
    similarities = np.asarray(backend.encode([normalise(k) for k in key_points])) @ np.asarray(backend.encode([normalise(c) for c in chunks])).T
    lowered = normalise(transcript).lower()
    results = []
    for i, point in enumerate(key_points):
        best = int(similarities[i].argmax())
        point_terms = terms(point)
        found = [t for t in point_terms if term_present(t, lowered)]
        share = len(found) / len(point_terms) if point_terms else 0.0
        similarity = float(similarities[i, best])
        if similarity >= COVERED_SIMILARITY or (similarity >= PARTIAL_SIMILARITY and share >= TERM_SHARE_FOR_COVERED):
            status = 'covered'
        elif similarity >= PARTIAL_SIMILARITY or share >= TERM_SHARE_FOR_COVERED:
            status = 'partial'
        else:
            status = 'missed'
        results.append({'text': point, 'status': status, 'similarity': round(similarity, 3),
                        'quote': chunks[best] if status != 'missed' else None, 'terms_found': found})
    value = sum({'covered': 1, 'partial': 0.5, 'missed': 0}[r['status']] for r in results) / len(results)
    missed = [r['text'] for r in results if r['status'] == 'missed']
    notes = []
    if value >= 0.8:
        notes.append('You covered the main points a strong answer needs.')
    if missed:
        notes.append('Not mentioned: ' + '; '.join(missed) + '.')
    partial = [r['text'] for r in results if r['status'] == 'partial']
    if partial:
        notes.append('Touched on but could be clearer: ' + '; '.join(partial) + '.')
    return {'key_points': results, 'score': round(value, 2), 'notes': notes}

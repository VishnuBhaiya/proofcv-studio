"""STAR check for behavioural answers, using our own trained sentence classifier.

Each sentence of the transcript is labelled situation, task, action, result or
other by a logistic-regression model trained on labelled example answers
(see train_star.py). The weights are stored as plain JSON and applied here with
numpy. Feedback notes come from simple rules over those labels.
"""
import json
import re
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).resolve().parent / 'data'
EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'
STAR = ('situation', 'task', 'action', 'result')
UNCERTAIN_BELOW = 0.5
MIN_ACTION_SHARE = 0.3
MAX_OTHER_SHARE = 0.3


def load_dataset(path=DATA_DIR / 'star_sentences.json'):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    for story in data['stories']:
        for label, _ in story['sentences']:
            if label not in data['labels']:
                raise ValueError(f"Unknown label {label} in {story['id']}.")
    return data


def position(index, count):
    """Where a sentence sits in its answer, from 0 (first) to 1 (last)."""
    return index / (count - 1) if count > 1 else 0.5


def split_sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if len(re.findall(r'\w+', s)) >= 2]


class StarClassifier:
    def __init__(self, path=DATA_DIR / 'star_model.json'):
        model = json.loads(Path(path).read_text(encoding='utf-8'))
        self.labels = model['labels']
        self.use_position = model['use_position']
        self.coef = np.asarray(model['coef'])
        self.intercept = np.asarray(model['intercept'])
        self.info = {k: model[k] for k in ('embedding_model', 'use_position', 'C', 'trained_on')}

    def predict(self, sentences, backend):
        """Label and probability for each sentence, in answer order."""
        if not sentences:
            return []
        x = np.asarray(backend.encode(sentences))
        if self.use_position:
            x = np.hstack([x, np.array([[position(i, len(sentences))] for i in range(len(sentences))])])
        logits = x @ self.coef.T + self.intercept
        probabilities = np.exp(logits - logits.max(axis=1, keepdims=True))
        probabilities /= probabilities.sum(axis=1, keepdims=True)
        return [{'label': self.labels[int(row.argmax())], 'confidence': round(float(row.max()), 3)} for row in probabilities]


_classifier = None


def classifier():
    global _classifier
    if _classifier is None:
        _classifier = StarClassifier()
    return _classifier


def analyse(transcript, backend, model=None):
    """Per-sentence STAR labels for a behavioural answer, which parts are present, and coaching notes."""
    model = model or classifier()
    sentences = split_sentences(transcript)
    labelled = [{'text': s, **p, 'uncertain': p['confidence'] < UNCERTAIN_BELOW} for s, p in zip(sentences, model.predict(sentences, backend))]
    by_label = {label: [s['text'] for s in labelled if s['label'] == label] for label in (*STAR, 'other')}
    present = {label: bool(by_label[label]) for label in STAR}
    notes = []
    if not labelled:
        return {'sentences': [], 'present': present, 'notes': ['Not enough speech to check the STAR structure.'], 'model': model.info}
    if not present['situation']:
        notes.append('Start with a sentence or two of context: where you were and what was going on.')
    if not present['task']:
        notes.append('Say what your goal or responsibility was before describing what you did.')
    if not present['action']:
        notes.append('Describe the specific steps you took. This should be the longest part of the answer.')
    elif len(by_label['action']) / len(labelled) < MIN_ACTION_SHARE:
        notes.append('Most of the answer was set-up. Spend more of it on what you actually did.')
    if not present['result']:
        notes.append('Finish with the outcome: what changed because of what you did.')
    elif not any(re.search(r'\d|percent|half|double|twice|third', s.lower()) for s in by_label['result']):
        notes.append('Your result has no number. If you can, quantify it: time saved, percentage improvement, a grade.')
    action_text = ' '.join(by_label['action']).lower()
    if len(re.findall(r'\bwe\b', action_text)) > len(re.findall(r'\bi\b', action_text)):
        notes.append('Your actions mostly say "we". Use "I" for your own part so the interviewer knows what you did.')
    if len(by_label['other']) / len(labelled) > MAX_OTHER_SHARE:
        notes.append('A lot of the answer was filler or not part of the story. Get to the example sooner.')
    if all(present.values()) and not notes:
        notes.append('All four STAR parts are there, in a clear order.')
    return {'sentences': labelled, 'present': present, 'notes': notes, 'model': model.info}

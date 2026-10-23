"""Train and evaluate the STAR sentence classifier.

    python -m server.interview.train_star

Features: the MiniLM sentence embedding (384 values), optionally plus the
sentence's relative position in its answer. Model: multinomial logistic
regression with balanced class weights.

Evaluation is split by story, so no answer appears in both training and
testing. 20% of stories are held out as a test set that is used once.
Settings (C and whether to use position) are chosen by 5-fold grouped
cross-validation on the remaining 80%. Two baselines are scored on the same
test set: always predicting the most common label, and hand-written keyword
rules. The shipped model is then refit on all stories.

Writes data/star_model.json (plain weights, no pickle) and
data/star_evaluation.json.
"""
import json
import re
from datetime import date
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit

from ..retrieval import SentenceTransformerBackend
from .star import DATA_DIR, EMBEDDING_MODEL, load_dataset, position

C_VALUES = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0)
SEED = 42

KEYWORD_RULES = [
    ('other', r"\b(good question|let me (think|explain|give)|does that make sense|that'?s (it|all|the story|probably)|repeat the question|is that the kind|i hope that|uh+|um+)\b"),
    ('result', r"\b(\d+|percent|improved|increased|dropped|fell|reduced|won|award|passed|finished|praised|thanked|learned|since then|now i|still use)\b"),
    ('task', r"\b(my (job|goal|aim|task|role)|i (was asked|had to|needed to|wanted to|was responsible|was in charge)|we (had|needed) to|the (aim|goal) was|responsible for)\b"),
    ('action', r"\bi (\w+ed|built|wrote|made|set|ran|took|found|sent|put|led|gave|told|split|kept|went|did|chose)\b"),
]


def keyword_baseline(text):
    lowered = text.lower()
    for label, pattern in KEYWORD_RULES:
        if re.search(pattern, lowered):
            return label
    return 'situation'


def features(vectors, positions, use_position):
    return np.hstack([vectors, positions[:, None]]) if use_position else vectors


def fit(x, y, c):
    return LogisticRegression(C=c, class_weight='balanced', max_iter=5000, random_state=SEED).fit(x, y)


def scores(y_true, y_pred, labels):
    report = classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0)
    return {'accuracy': round(accuracy_score(y_true, y_pred), 3), 'macro_f1': round(f1_score(y_true, y_pred, labels=labels, average='macro', zero_division=0), 3),
            'per_label': {l: {k: round(report[l][k], 3) for k in ('precision', 'recall', 'f1-score', 'support')} for l in labels}}


def main():
    data = load_dataset()
    labels = data['labels']
    rows = [(s['id'], label, text, position(i, len(s['sentences']))) for s in data['stories'] for i, (label, text) in enumerate(s['sentences'])]
    groups = np.array([r[0] for r in rows])
    y = np.array([r[1] for r in rows])
    texts = [r[2] for r in rows]
    positions = np.array([r[3] for r in rows])
    print(f'Embedding {len(rows)} sentences from {len(set(groups))} stories with {EMBEDDING_MODEL}...')
    vectors = SentenceTransformerBackend(EMBEDDING_MODEL).encode(texts)

    train, test = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED).split(vectors, y, groups))
    folds = list(GroupKFold(n_splits=5).split(train, y[train], groups[train]))
    search = []
    for use_position in (False, True):
        x = features(vectors, positions, use_position)[train]
        for c in C_VALUES:
            fold_f1 = [f1_score(y[train][va], fit(x[tr], y[train][tr], c).predict(x[va]), labels=labels, average='macro') for tr, va in folds]
            search.append({'position': use_position, 'C': c, 'cv_macro_f1': round(float(np.mean(fold_f1)), 3), 'cv_std': round(float(np.std(fold_f1)), 3)})
    best = max(search, key=lambda s: (s['cv_macro_f1'], -s['C']))
    print('Best cross-validation setting:', best)

    def test_scores(use_position, c):
        x = features(vectors, positions, use_position)
        return fit(x[train], y[train], c).predict(x[test])

    majority = max(set(y[train]), key=list(y[train]).count)
    predictions = test_scores(best['position'], best['C'])
    other_variant = test_scores(not best['position'], max((s for s in search if s['position'] != best['position']), key=lambda s: s['cv_macro_f1'])['C'])
    evaluation = {
        'date': date.today().isoformat(),
        'data': {'review_status': data['review_status'], 'stories': len(set(groups)), 'sentences': len(rows),
                 'label_counts': {l: int((y == l).sum()) for l in labels},
                 'test_stories': sorted(set(groups[test])), 'test_sentences': len(test)},
        'method': 'MiniLM embeddings (+ optional relative position) -> multinomial logistic regression, balanced class weights. Split by story; settings chosen by 5-fold grouped CV on the training stories; test stories used once.',
        'model_selection': {'chosen': best, 'all': search},
        'test': {
            'classifier': scores(y[test], predictions, labels),
            'classifier_other_feature_set': {'position': not best['position'], **scores(y[test], other_variant, labels)},
            'baseline_majority': {'predicts': majority, **scores(y[test], [majority] * len(test), labels)},
            'baseline_keyword_rules': scores(y[test], [keyword_baseline(texts[i]) for i in test], labels),
        },
        'confusion_matrix': {'labels': labels, 'rows_are_true': confusion_matrix(y[test], predictions, labels=labels).tolist()},
        'test_errors': [{'text': texts[i], 'true': y[i], 'predicted': p} for i, p in zip(test, predictions) if p != y[i]],
    }

    model = fit(features(vectors, positions, best['position']), y, best['C'])
    assert list(model.classes_) == sorted(labels)
    shipped = {'labels': list(model.classes_), 'embedding_model': EMBEDDING_MODEL, 'use_position': best['position'], 'C': best['C'],
               'trained_on': {'stories': len(set(groups)), 'sentences': len(rows), 'date': evaluation['date'], 'data_review_status': data['review_status']},
               'coef': np.round(model.coef_, 5).tolist(), 'intercept': np.round(model.intercept_, 5).tolist()}
    (DATA_DIR / 'star_model.json').write_text(json.dumps(shipped) + '\n', encoding='utf-8')
    (DATA_DIR / 'star_evaluation.json').write_text(json.dumps(evaluation, indent=2) + '\n', encoding='utf-8')
    for name, result in evaluation['test'].items():
        print(f"{name:32} accuracy {result['accuracy']:.3f}  macro-F1 {result['macro_f1']:.3f}")
    print('Wrote star_model.json and star_evaluation.json')


if __name__ == '__main__':
    main()

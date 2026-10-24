"""Evaluate Interview Coach on real recordings of scripted answers.

    python -m server.interview.evaluate

Read-aloud scripts (data/evaluation_scripts.json) are recorded in the app's
evaluation recorder and saved to runtime/interview-evaluation/<script id>.webm.
Because every script is known word for word and labelled, this measures:

- transcription word error rate (WER) with and without the profile hints,
- whether the user's name was recognised,
- STAR classifier accuracy on the script text and on what Whisper heard,
- key-point scoring agreement on the technical scripts,
- transcription time.

Writes a summary (no audio) to data/real_evaluation.json for the report.
Read speech is easier than spontaneous answers, so these are best-case numbers.
"""
import json
import re
import time
from datetime import date
from pathlib import Path
from statistics import mean

from .factcheck import NUMBER_WORDS
from .star import split_sentences

DATA_DIR = Path(__file__).resolve().parent / 'data'
SCRIPTS_PATH = DATA_DIR / 'evaluation_scripts.json'
REPORT_PATH = DATA_DIR / 'real_evaluation.json'
ROOT = Path(__file__).resolve().parents[2]


def load_scripts(path=SCRIPTS_PATH):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def samples_dir(store_path):
    """Recordings live next to the app's other local data, never in git."""
    return Path(store_path).parent / 'interview-evaluation'


def save_sample(directory, script_id, audio, scripts):
    if script_id not in {s['id'] for s in scripts['scripts']}:
        raise ValueError('Unknown evaluation script.')
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f'{script_id}.webm').write_bytes(audio)


MIN_SECONDS = 3.0  # Every script takes well over this to read aloud.


def recorded(directory):
    return sorted(p.stem for p in Path(directory).glob('*.webm')) if Path(directory).is_dir() else []


def lengths(directory):
    """Seconds of audio in each saved recording, so a failed or cut-off recording is visible."""
    from .speech import SAMPLE_RATE, decode_audio
    result = {}
    for script_id in recorded(directory):
        try:
            result[script_id] = round(len(decode_audio((Path(directory) / f'{script_id}.webm').read_bytes())) / SAMPLE_RATE, 1)
        except Exception:
            result[script_id] = 0.0
    return result


def problems(scripts, seconds):
    """Scripts that are missing or too short to evaluate."""
    missing = [s['id'] for s in scripts['scripts'] if s['id'] not in seconds]
    short = [i for i, length in seconds.items() if length < MIN_SECONDS]
    return missing, short


def normalise(text):
    """Lower-case words for WER: punctuation removed, '%' read as 'percent', number words as digits."""
    text = text.lower().replace('%', ' percent').replace('-', ' ')
    tokens = re.findall(r"[a-z0-9']+", text)
    out, number = [], None
    for token in tokens + ['']:
        if token in NUMBER_WORDS:
            number = (number or 0) + NUMBER_WORDS[token]
            continue
        if token in ('hundred', 'thousand') and number is not None:
            number *= 100 if token == 'hundred' else 1000
            continue
        if number is not None:
            out.append(str(number))
            number = None
        if token:
            out.append(token.strip("'"))
    return [t for t in out if t]


def word_errors(reference, hypothesis):
    """Substitutions + deletions + insertions between two token lists (Levenshtein)."""
    previous = list(range(len(hypothesis) + 1))
    for i, ref in enumerate(reference, 1):
        current = [i]
        for j, hyp in enumerate(hypothesis, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ref != hyp)))
        previous = current
    return previous[-1]


def wer(reference, hypothesis):
    ref, hyp = normalise(reference), normalise(hypothesis)
    return word_errors(ref, hyp), len(ref)


def overlap(a, b):
    a, b = set(normalise(a)), set(normalise(b))
    return len(a & b) / len(a | b) if a | b else 0.0


def star_accuracy(script, transcript, classifier, backend):
    """STAR labels on the script text, and on Whisper's sentences aligned to the closest script sentence."""
    gold = [label for label, _ in script['sentences']]
    texts = [text for _, text in script['sentences']]
    on_text = [p['label'] for p in classifier.predict(texts, backend)]
    heard = split_sentences(transcript)
    on_heard = [p['label'] for p in classifier.predict(heard, backend)] if heard else []
    aligned = [gold[max(range(len(texts)), key=lambda i: overlap(texts[i], sentence))] for sentence in heard]
    return {'text_correct': sum(p == g for p, g in zip(on_text, gold)), 'text_total': len(gold),
            'heard_correct': sum(p == g for p, g in zip(on_heard, aligned)), 'heard_total': len(heard),
            'all_four_found': {'situation', 'task', 'action', 'result'} <= set(on_heard)}


def run(sample_directory=None, store_path=ROOT / 'runtime' / 'proofcv.sqlite3', report_path=REPORT_PATH):
    from ..retrieval import SentenceTransformerBackend
    from . import content, speech
    from .questions import load_bank
    from .star import EMBEDDING_MODEL, classifier
    scripts = load_scripts()
    directory = Path(sample_directory) if sample_directory else samples_dir(store_path)
    available = {s['id']: s for s in scripts['scripts'] if (directory / f"{s['id']}.webm").is_file()}
    if not available:
        raise SystemExit(f'No recordings found in {directory}. Record the scripts in Interview Coach first.')
    vocabulary = scripts['vocabulary']
    profile = {'name': vocabulary['name'], 'skills': vocabulary['terms'], 'projects': []}
    conditions = {'filler prompt only': speech.FILLER_PROMPT, 'with profile hints': speech.expected_words(profile, vocabulary['role'])}
    transcriber = speech.transcriber()
    backend = SentenceTransformerBackend(EMBEDDING_MODEL)
    bank = {q['id']: q for q in load_bank()['questions']}
    star_model = classifier()
    per_sample, totals, seconds = [], {name: [0, 0] for name in conditions}, []
    star_rows, content_rows = [], []
    first_name = vocabulary['name'].split()[0].lower()
    for script_id, script in available.items():
        audio = (directory / f'{script_id}.webm').read_bytes()
        reference = ' '.join(text for _, text in script['sentences'])
        row = {'id': script_id, 'question_id': script['question_id'], 'reference_words': len(normalise(reference))}
        for name, prompt in conditions.items():
            started = time.perf_counter()
            heard = transcriber.transcribe(audio, prompt)
            seconds.append((time.perf_counter() - started, heard['duration']))
            errors, words = wer(reference, heard['text'])
            totals[name][0] += errors
            totals[name][1] += words
            row[name] = {'wer': round(errors / words, 3), 'transcript': heard['text']}
            if first_name in reference.lower():
                row[name]['name_recognised'] = first_name in heard['text'].lower()
        final = row['with profile hints']['transcript']
        if script['question_id'].startswith('bh-'):
            star_rows.append({'id': script_id, **star_accuracy(script, final, star_model, backend)})
        if 'covers' in script:
            key_points = bank[script['question_id']]['key_points']
            scored = content.score(final, key_points, backend)['key_points']
            gold = [i in script['covers'] for i in range(len(key_points))]
            content_rows.append({'id': script_id, 'strict_agree': sum((k['status'] == 'covered') == g for k, g in zip(scored, gold)),
                                 'lenient_agree': sum((k['status'] != 'missed') == g for k, g in zip(scored, gold)), 'total': len(gold),
                                 'statuses': [k['status'] for k in scored], 'gold': script['covers']})
        per_sample.append(row)
    summary = {
        'date': date.today().isoformat(), 'samples': len(per_sample), 'scripts_total': len(scripts['scripts']),
        'note': 'Read-aloud scripts on one speaker and microphone: a best case, not spontaneous speech.',
        'wer': {name: round(e / w, 3) for name, (e, w) in totals.items()},
        'name_recognised': {name: f"{sum(r[name].get('name_recognised', False) for r in per_sample)}/{sum('name_recognised' in r[name] for r in per_sample)}" for name in conditions},
        'star': {'scripts': len(star_rows),
                 'accuracy_on_script_text': round(sum(r['text_correct'] for r in star_rows) / max(1, sum(r['text_total'] for r in star_rows)), 3),
                 'accuracy_on_whisper_text': round(sum(r['heard_correct'] for r in star_rows) / max(1, sum(r['heard_total'] for r in star_rows)), 3),
                 'all_four_parts_found': f"{sum(r['all_four_found'] for r in star_rows)}/{len(star_rows)}", 'per_script': star_rows},
        'key_points': {'scripts': len(content_rows),
                       'strict_agreement': round(sum(r['strict_agree'] for r in content_rows) / max(1, sum(r['total'] for r in content_rows)), 3),
                       'lenient_agreement': round(sum(r['lenient_agree'] for r in content_rows) / max(1, sum(r['total'] for r in content_rows)), 3),
                       'per_script': content_rows},
        'transcription_seconds': {'mean': round(mean(s for s, _ in seconds), 2), 'per_audio_second': round(sum(s for s, _ in seconds) / max(1e-9, sum(d for _, d in seconds)), 2)},
        'per_sample': per_sample,
    }
    Path(report_path).write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Evaluate Interview Coach on recorded scripts.')
    parser.add_argument('--partial', action='store_true', help='write a report even if some scripts are missing or too short')
    args = parser.parse_args()
    directory = samples_dir(ROOT / 'runtime' / 'proofcv.sqlite3')
    missing, short = problems(load_scripts(), lengths(directory))
    if (missing or short) and not args.partial:
        if missing:
            print(f"Not recorded yet: {', '.join(missing)}")
        if short:
            print(f"Too short (under {MIN_SECONDS:g} s, probably cut off or silent): {', '.join(short)}")
        raise SystemExit('Record these scripts again in Interview Coach, or run with --partial to evaluate what is there. No report was written.')
    summary = run(directory)
    print(f"Samples: {summary['samples']} of {summary['scripts_total']} scripts recorded")
    for name, value in summary['wer'].items():
        print(f"WER {name:20} {value:.1%}   name recognised {summary['name_recognised'][name]}")
    s, k = summary['star'], summary['key_points']
    print(f"STAR accuracy: script text {s['accuracy_on_script_text']:.1%}, Whisper text {s['accuracy_on_whisper_text']:.1%}, all four parts found {s['all_four_parts_found']}")
    print(f"Key points agreement: strict {k['strict_agreement']:.1%}, lenient {k['lenient_agreement']:.1%}")
    print(f"Transcription: {summary['transcription_seconds']['mean']} s per answer ({summary['transcription_seconds']['per_audio_second']} s per second of audio)")
    print(f'Wrote {REPORT_PATH}')


if __name__ == '__main__':
    main()

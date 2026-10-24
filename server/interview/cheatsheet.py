"""Interview-day cheat sheet: one page to read just before the interview.

Built locally from the user's own practice where it exists (best introduction,
best STAR stories, delivery habits) and from the confirmed profile and job fit
otherwise. Nothing is invented: suggestions built from the profile say so, and
missing details stay as [bracketed prompts].
"""
import re
from datetime import date
from io import BytesIO
from statistics import mean
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import model_answer, star
from .attempts import needs_work
from .mock import components, overall

GOOD_WPM = (120, 160)


def score_of(summary):
    return overall(components(summary))


def best_attempts(attempts, prefix):
    """Highest-scoring attempt per question whose id starts with prefix (follow-ups excluded)."""
    best = {}
    for a in attempts:
        if a['question_id'].startswith(prefix) and ':' not in a['question_id'] and a['transcript'].strip():
            scored = {**a, 'score': score_of(a['summary'])}
            if a['question_id'] not in best or scored['score'] > best[a['question_id']]['score']:
                best[a['question_id']] = scored
    return sorted(best.values(), key=lambda a: -a['score'])


def introduction(attempts, profile, fit_items, job, backend):
    mine = [a for a in best_attempts(attempts, 'si-30') if not needs_work(a['summary'])]
    if mine:
        return {'source': f"Your own best 30-second answer (scored {mine[0]['score']}/100)", 'text': mine[0]['transcript']}
    built = model_answer.introduction({'id': 'si-30', 'round': 'self_introduction', 'seconds': 30}, profile, fit_items, job, backend)
    return {'source': 'Built from your confirmed profile: practise saying it in your own words', 'text': built['text']}


def strengths(fit_items):
    strong = sorted((r for r in fit_items if r['status'] == 'strong'), key=lambda r: (r['level'] != 'required', -r.get('similarity', 0)))[:3]
    out = []
    for r in strong:
        facts = [e for e in r['evidence'] if e['label'] != 'Skill'] or r['evidence']
        out.append({'requirement': r['text'], 'evidence': f"{facts[0]['label']}: {facts[0]['text']}" if facts else 'Listed in your skills'})
    return out


def stories(attempts, questions_by_id, profile, fit_items, job, backend):
    """The two best behavioural answers, re-labelled S/T/A/R; a profile-based suggestion if there are none."""
    picked = []
    for a in best_attempts(attempts, 'bh-')[:2]:
        sentences = star.split_sentences(a['transcript'])
        firsts = {}
        for text, label in zip(sentences, star.classifier().predict(sentences, backend)):
            if label['label'] != 'other':
                firsts.setdefault(label['label'], text)
        picked.append({'question': questions_by_id.get(a['question_id'], {}).get('text', a['question_id']), 'score': a['score'], 'source': 'Your practice answer',
                       'parts': [[label.capitalize(), firsts[label]] for label in ('situation', 'task', 'action', 'result') if label in firsts]})
    if not picked:
        # Without practice, suggest the profile story closest to what this job values most.
        strong = [r['text'] for r in fit_items if r['status'] == 'strong']
        built = model_answer.behavioural(' '.join([job['title'], *strong[:3]]), profile, backend)
        picked.append({'question': 'Suggested story from your profile', 'score': None, 'source': 'Not practised yet: record it in Practice',
                       'parts': [[p['label'], p['text']] for p in built['parts']][:5]})
    return picked


def gap_answers(fit_items, profile, job, backend):
    gaps = sorted((r for r in fit_items if r['status'] == 'gap' and r['level'] != 'responsibility'), key=lambda r: r['level'] != 'required')[:2]
    return [{'requirement': r['text'],
             'answer': model_answer.motivation({'id': 'mf-gap', 'round': 'motivation_fit'}, r['id'], profile, fit_items, job, backend)['parts']}
            for r in gaps]


def questions_to_ask(fit_items, job):
    duties = [r for r in fit_items if r['level'] == 'responsibility'][:2]
    duty = lambda text: re.sub(r'^[A-Z][a-z]+\b', lambda m: m.group(0).lower(), text.rstrip('.'))
    asked = [f"What does “{duty(r['text'])}” look like day to day in this team?" for r in duties]
    asked += [f"What would success look like in the first six months for the {job['title']}?",
              'How does the team measure whether a model is working well once it is in use?']
    return asked[:4]


def reminders(attempts):
    """Habits from the user's own delivery feedback, or general tips before any practice."""
    spoken = [a['summary'] for a in attempts if a['summary'].get('words_per_minute')]
    if not spoken:
        return ['Practise a few answers first: your personal delivery reminders will appear here.',
                'Aim for 120-160 words per minute and pause instead of saying "um".',
                'Finish every story with a result, ideally with a number.']
    wpm = round(mean(s['words_per_minute'] for s in spoken))
    fillers = round(mean(s['fillers_per_minute'] for s in spoken), 1)
    tips = []
    if wpm > GOOD_WPM[1]:
        tips.append(f'Slow down: you average {wpm} words per minute (aim for 120-160).')
    elif wpm < GOOD_WPM[0]:
        tips.append(f'Pick up the pace a little: you average {wpm} words per minute (aim for 120-160).')
    else:
        tips.append(f'Your pace is good: {wpm} words per minute on average.')
    tips.append(f'Cut filler words: {fillers} per minute on average.' if fillers > 2 else f'Few filler words ({fillers} per minute). Keep it up.')
    ratios = [s['length_ratio'] for s in spoken if s.get('length_ratio') is not None]
    if ratios and mean(ratios) < 0.7:
        tips.append(f'Your answers run short: about {round(mean(ratios) * 100)}% of the target length. Add detail and a result.')
    elif ratios and mean(ratios) > 1.3:
        tips.append(f'Your answers run long: about {round(mean(ratios) * 100)}% of the target length. Get to the point sooner.')
    pauses = sum(s['long_pauses'] for s in spoken)
    if pauses:
        tips.append(f'{pauses} long pauses across your practice: plan the structure before you start talking.')
    flags = sum(s.get('flags', 0) for s in spoken)
    if flags:
        tips.append(f"{flags} detail{'s you said were' if flags > 1 else ' you said was'} not in your confirmed profile. Only claim what you can back up.")
    return tips


def mock_line(readiness):
    if readiness['band'] == 'Incomplete':
        return f"latest mock interview unfinished ({readiness['answered']} of {readiness['total']} answered)"
    return f"latest mock interview {readiness['overall']}/100 ({readiness['band']})"


def build(profile, fit_items, job, attempts, questions_by_id, backend, readiness=None):
    return {
        'name': profile.get('name') or 'Candidate', 'job': job, 'date': date.today().isoformat(),
        'readiness': {k: readiness[k] for k in ('overall', 'band', 'answered', 'total')} if readiness else None,
        'practised': len({a['question_id'] for a in attempts if ':' not in a['question_id']}),
        'introduction': introduction(attempts, profile, fit_items, job, backend),
        'strengths': strengths(fit_items),
        'stories': stories(attempts, questions_by_id, profile, fit_items, job, backend),
        'gaps': gap_answers(fit_items, profile, job, backend),
        'questions_to_ask': questions_to_ask(fit_items, job),
        'reminders': reminders(attempts),
        'note': 'Built on this computer from your practice and confirmed profile. [Brackets] mark details only you can fill in.',
    }


def render_pdf(sheet):
    """The cheat sheet on one A4 page, in two columns."""
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=30, rightMargin=30, topMargin=28, bottomMargin=24,
                                 title=f"Interview cheat sheet - {sheet['job']['title']}")
    ink, green, muted = colors.HexColor('#1f2a24'), colors.HexColor('#2c6554'), colors.HexColor('#6f776f')
    clean = lambda value: escape(str(value).encode('cp1252', 'replace').decode('cp1252'))
    styles = {
        'title': ParagraphStyle('t', fontName='Helvetica-Bold', fontSize=16, leading=19, textColor=ink),
        'sub': ParagraphStyle('s', fontName='Helvetica', fontSize=8.5, leading=11, textColor=muted),
        'head': ParagraphStyle('h', fontName='Helvetica-Bold', fontSize=9.5, leading=12, textColor=green, spaceBefore=7, spaceAfter=3),
        'body': ParagraphStyle('b', fontName='Helvetica', fontSize=8.2, leading=10.4, textColor=ink),
        'small': ParagraphStyle('m', fontName='Helvetica', fontSize=7.2, leading=9, textColor=muted),
        'bullet': ParagraphStyle('u', fontName='Helvetica', fontSize=8.2, leading=10.4, textColor=ink, leftIndent=8, bulletIndent=0),
    }
    p = lambda text, style='body', **kw: Paragraph(clean(text) if style != 'raw' else text, styles[style if style != 'raw' else 'body'], **kw)
    bullet = lambda text: Paragraph(clean(text), styles['bullet'], bulletText='•')
    left = [p('Your 30-second introduction', 'head'), p(sheet['introduction']['text']), p(sheet['introduction']['source'], 'small'),
            p('Top strengths for this role', 'head')]
    for s in sheet['strengths']:
        left += [Paragraph(f"<b>{clean(s['requirement'])}</b>", styles['body']), p(s['evidence'], 'small'), Spacer(1, 3)]
    left += [p('Questions to ask them', 'head')] + [bullet(q) for q in sheet['questions_to_ask']]
    left += [p('Delivery reminders', 'head')] + [bullet(t) for t in sheet['reminders']]
    right = [p('Your best STAR stories', 'head')]
    for story in sheet['stories']:
        right.append(Paragraph(f"<b>{clean(story['question'])}</b>" + (f" &nbsp;({story['score']}/100)" if story['score'] is not None else ''), styles['body']))
        right += [Paragraph(f"<b>{clean(label)}:</b> {clean(text)}", styles['bullet'], bulletText='•') for label, text in story['parts']]
        right += [p(story['source'], 'small'), Spacer(1, 4)]
    right.append(p('Honest answers for your gaps', 'head'))
    for gap in sheet['gaps']:
        right.append(Paragraph(f"<b>{clean(gap['requirement'])}</b>", styles['body']))
        right += [Paragraph(f"<b>{clean(part['label'])}:</b> {clean(part['text'])}", styles['bullet'], bulletText='•') for part in gap['answer']]
        right.append(Spacer(1, 4))
    readiness = f" · {mock_line(sheet['readiness'])}" if sheet.get('readiness') else ''
    story = [p('INTERVIEW-DAY CHEAT SHEET', 'small'), p(f"{sheet['name']} · {sheet['job']['title']}", 'title'),
             p(f"{date.fromisoformat(sheet['date']).strftime('%d %B %Y')} · {sheet['practised']} questions practised{readiness}", 'sub'), Spacer(1, 4)]
    columns = Table([[left, right]], colWidths=[262, 273])
    columns.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (0, 0), 14),
                                 ('LINEAFTER', (0, 0), (0, 0), 0.4, colors.HexColor('#d9d6cf'))]))
    story += [columns, Spacer(1, 6), p(sheet['note'], 'small')]
    document.build(story)
    return buffer.getvalue()

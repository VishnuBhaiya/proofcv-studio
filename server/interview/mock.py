"""Full mock interview: five questions in a row, then a readiness report.

The readiness score is a transparent average of things already measured for
each answer: delivery (pace, fillers, long pauses, length), STAR structure,
key-point coverage and claims backed by the profile. No model decides it, and
the report prints the formula.
"""
from datetime import datetime
from io import BytesIO
from statistics import mean
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .attempts import needs_work

BANDS = ((80, 'Ready'), (60, 'Nearly ready'), (0, 'Needs practice'))
BAND_COLOURS = {'Ready': colors.HexColor('#2f6b45'), 'Nearly ready': colors.HexColor('#8a6418'), 'Needs practice': colors.HexColor('#a2422f')}
COMPONENT_LABELS = {'delivery': 'Delivery', 'length': 'Answer length', 'structure': 'STAR structure', 'content': 'Key points', 'honesty': 'Claims backed by your profile'}
METHOD = ('Each answer scores 0-100 as the average of the parts that apply to it. Delivery: the average of pace (100 inside 120-160 '
          'words/min, minus 2 per word/min outside), filler words (minus 10 per filler/min above 2) and long pauses (minus 20 each). '
          'Answer length: minus 1 per % away from the target length. STAR structure: parts present out of 4 (behavioural only). '
          'Key points: share covered (technical answers, and self-introductions against points from your confirmed profile). '
          'Claims: share of what you said about yourself that your confirmed profile backs (a loose match counts 60%), minus 25 '
          'per flagged detail such as an unbacked number, tool, leadership claim or a different name. An answer scoring under 40 on '
          'key points or claims is capped at 40 overall. The overall score is the average of answered questions. 80+ is Ready, 60-79 Nearly ready, below 60 Needs practice; '
          'until every question is answered the result is shown as Incomplete.')


def pick(rounds):
    """Five questions from the picked set: a 90-second intro, two behavioural, one technical, one motivation."""
    chosen = []
    intro = [q for q in rounds.get('self_introduction', []) if q.get('seconds') == 90] or rounds.get('self_introduction', [])[:1]
    chosen += intro[:1]
    behavioural = rounds.get('behavioural', [])
    chosen += behavioural[:1] + behavioural[2:3]
    chosen += rounds.get('technical', [])[:1]
    motivation = rounds.get('motivation_fit', [])
    chosen += ([q for q in motivation if q['id'] == 'mf-gap'] or [q for q in motivation if q['id'] == 'mf-why-role'] or motivation)[:1]
    return chosen


def components(summary):
    """0-100 scores for each part that applies to one answer."""
    if not summary.get('words_per_minute'):
        return {'delivery': 0}
    delivery = [max(0, 100 - 2 * (summary.get('pace_gap') or 0)),
                max(0, 100 - 10 * max(0, summary['fillers_per_minute'] - 2)),
                max(0, 100 - 20 * summary['long_pauses'])]
    parts = {'delivery': round(mean(delivery))}
    if summary.get('length_gap') is not None:
        parts['length'] = max(0, 100 - summary['length_gap'])
    if 'star_parts' in summary:
        parts['structure'] = round(summary['star_parts'] / 4 * 100)
    if 'key_points' in summary:
        parts['content'] = round(summary['key_points'] * 100)
    if 'honesty' in summary:
        if summary['honesty'] is not None:  # Nothing claimed: nothing to back up, so no score.
            parts['honesty'] = summary['honesty']
    elif 'flags' in summary:  # Attempts saved before claims were scored one by one.
        parts['honesty'] = max(0, 100 - 25 * summary['flags'])
    return parts


# An answer that misses what was asked, or that the profile does not back, cannot score well on
# delivery alone: the overall score is capped when key points or profile backing are this low.
CAP_BELOW = 40
CAPPED_SCORE = 40


def overall(parts):
    """One 0-100 score for an answer: the average of its parts, capped when the substance is missing."""
    score = round(mean(parts.values()))
    if min(parts.get('content', 100), parts.get('honesty', 100)) < CAP_BELOW:
        score = min(score, CAPPED_SCORE)
    return score


def band(score):
    return next(label for limit, label in BANDS if score >= limit)


def report(session, attempts):
    """Readiness report for a mock session from its linked attempts."""
    rows = []
    for position, question in enumerate(session['questions']):
        attempt = attempts.get(session['answers'].get(str(position)))
        if not attempt:
            rows.append({'position': position + 1, 'question': question['text'], 'round': question['round'], 'answered': False})
            continue
        parts = components(attempt['summary'])
        row = {'position': position + 1, 'question': question['text'], 'round': question['round'], 'answered': True,
               'score': overall(parts), 'components': parts, 'needs_work': needs_work(attempt['summary']),
               'transcript': attempt['transcript'], 'summary': attempt['summary']}
        linked = session['answers'].get(f'{position}f')
        follow = attempts.get(linked['id']) if linked else None
        if follow:
            row['follow_up'] = {'question': linked['question'], 'score': overall(components(follow['summary'])),
                                'needs_work': needs_work(follow['summary']), 'transcript': follow['transcript']}
        rows.append(row)
    answered = [r for r in rows if r['answered']]
    if not answered:
        raise ValueError('Answer at least one question to get a readiness report.')
    total = round(mean(r['score'] for r in answered))
    by_part = {key: round(mean(r['components'][key] for r in answered if key in r['components']))
               for key in COMPONENT_LABELS if any(key in r['components'] for r in answered)}
    spoken = [r['summary'] for r in answered if r['summary'].get('words_per_minute')]
    averages = {'words_per_minute': round(mean(s['words_per_minute'] for s in spoken)) if spoken else 0,
                'fillers_per_minute': round(mean(s['fillers_per_minute'] for s in spoken), 1) if spoken else 0,
                'long_pauses': sum(s['long_pauses'] for s in spoken)}
    follow_ups = [r['follow_up']['score'] for r in answered if 'follow_up' in r]
    cross = round(mean(follow_ups)) if follow_ups else None
    strengths = [f"{COMPONENT_LABELS[k]} ({v}/100)" for k, v in sorted(by_part.items(), key=lambda kv: -kv[1]) if v >= 80]
    weak = [f"{COMPONENT_LABELS[k]} ({v}/100)" for k, v in sorted(by_part.items(), key=lambda kv: kv[1]) if v < 60]
    if cross is not None:
        (strengths if cross >= 80 else weak if cross < 60 else []).append(f'Answering follow-up questions ({cross}/100)')
    steps = list(dict.fromkeys(reason for r in sorted(answered, key=lambda r: r['score']) for reason in r['needs_work']))[:4]
    lowest = min(answered, key=lambda r: r['score'])
    if lowest['score'] < 80:
        steps.append(f"Practise question {lowest['position']} again: it scored lowest ({lowest['score']}/100).")
    missing = [r['position'] for r in rows if not r['answered']]
    if missing:
        steps.append(f"Answer the skipped question{'s' if len(missing) > 1 else ''} ({', '.join(map(str, missing))}) to complete the interview.")
    return {'session_id': session['id'], 'job': session['job'], 'created_at': session['created_at'], 'overall': total,
            'band': band(total) if len(answered) == len(rows) else 'Incomplete',
            'answered': len(answered), 'total': len(rows), 'cross_questioning': cross, 'by_part': by_part, 'averages': averages, 'strengths': strengths,
            'weak_spots': weak, 'next_steps': steps or ['Keep practising with new questions to stay sharp.'], 'questions': rows, 'method': METHOD}


def render_pdf(result, name):
    """The readiness report as an A4 PDF."""
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=48, rightMargin=48, topMargin=48, bottomMargin=48,
                                 title=f"Interview readiness report - {result['job']['title']}")
    ink, muted = colors.HexColor('#202622'), colors.HexColor('#6b6f6c')
    style = lambda size, **kw: ParagraphStyle(f's{size}{len(kw)}', fontName=kw.pop('font', 'Helvetica'), fontSize=size, leading=size * 1.35, textColor=kw.pop('color', ink), **kw)
    text = lambda value, s: Paragraph(escape(str(value).encode('cp1252', 'replace').decode('cp1252')), s)
    when = datetime.fromisoformat(result['created_at']).strftime('%d %B %Y')
    story = [text('INTERVIEW READINESS REPORT', style(9, color=muted)), text(result['job']['title'], style(20, font='Helvetica-Bold')),
             text(f"{name} · mock interview on {when} · {result['answered']} of {result['total']} questions answered", style(10, color=muted)), Spacer(1, 14),
             text(f"{result['overall']}/100 · {result['band']}", style(26, font='Helvetica-Bold', color=BAND_COLOURS.get(result['band'], muted))), Spacer(1, 6)]
    if result['by_part']:
        story.append(text(' · '.join(f"{COMPONENT_LABELS[k]}: {v}" for k, v in result['by_part'].items()), style(10)))
    if result.get('cross_questioning') is not None:
        story.append(text(f"Follow-up questions: {result['cross_questioning']}/100 on average", style(10)))
    a = result['averages']
    story += [text(f"Average pace {a['words_per_minute']} words/min · {a['fillers_per_minute']} filler words/min · {a['long_pauses']} long pauses in total", style(10, color=muted)), Spacer(1, 14)]
    for title, items in (('Strengths', result['strengths']), ('Weak spots', result['weak_spots']), ('Next steps', result['next_steps'])):
        if items:
            story.append(text(title, style(13, font='Helvetica-Bold')))
            story += [text(f'• {item}', style(10, leftIndent=8)) for item in items]
            story.append(Spacer(1, 10))
    table = [[text(h, style(9, font='Helvetica-Bold')) for h in ('#', 'Question', 'Score', 'Main issue')]]
    for r in result['questions']:
        issue = 'Not answered' if not r['answered'] else (r['needs_work'][0] if r['needs_work'] else 'None')
        table.append([text(r['position'], style(9)), text(r['question'], style(9)), text(r.get('score', '-'), style(9)), text(issue, style(9))])
        if r.get('follow_up'):
            f = r['follow_up']
            table.append(['', text(f"Follow-up: {f['question']}", style(8.5, color=muted)), text(f['score'], style(8.5, color=muted)),
                          text(f['needs_work'][0] if f['needs_work'] else 'None', style(8.5, color=muted))])
    grid = Table(table, colWidths=[20, 270, 40, 169], repeatRows=1)
    grid.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 0.8, ink), ('LINEBELOW', (0, 1), (-1, -1), 0.3, colors.HexColor('#d9d6cf')),
                              ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    story += [text('Question by question', style(13, font='Helvetica-Bold')), Spacer(1, 4), grid, Spacer(1, 14),
              text('How the score is calculated', style(10, font='Helvetica-Bold')), text(result['method'], style(8.5, color=muted)),
              Spacer(1, 6), text('Calculated locally from the recorded answers. No AI service was used to grade them.', style(8.5, color=muted))]
    document.build(story)
    return buffer.getvalue()

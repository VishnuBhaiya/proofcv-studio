"""Self-introduction deck: a short slide deck and speaker script built from confirmed facts.

Runs locally. Slide content comes from the confirmed profile and the job fit
(chunk 1): the strongest required matches, the project with the most evidence,
a past role and honest growth areas. Slides keep the CV wording; speaker notes
turn it into first person. Nothing is invented: missing details are
[bracketed prompts]. Rendered in the app and as a 16:9 PDF with ReportLab.
"""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from .fit import sentences
from .model_answer import achievements_about, closest, first_person, lower_first, stories

WORDS_PER_MINUTE = 140
TARGET_SECONDS = 120
PAGE = (960, 540)
INK, ACCENT, MUTED, PAPER = colors.HexColor('#202622'), colors.HexColor('#2f6b45'), colors.HexColor('#6b6f6c'), colors.HexColor('#f6f4ef')


def source_names(item):
    """Where a requirement's evidence comes from, e.g. 'Smart Intersection project' or 'Skills: Python'."""
    names = [e['label'].split(': ', 1)[1] for e in item['evidence'] if e['label'].startswith(('Project: ', 'Experience: '))]
    skills = [e['text'] for e in item['evidence'] if e['label'] == 'Skill']
    return list(dict.fromkeys(names)) or ([f"Skills: {', '.join(skills)}"] if skills else [])


def cv_style(sentence):
    """'I logged metrics.' -> 'Logged metrics.' so every slide bullet reads like the CV."""
    return sentence[2:3].upper() + sentence[3:] if sentence.startswith('I ') else sentence


def listed(texts):
    return texts[0] if len(texts) == 1 else ', '.join(texts[:-1]) + ' and ' + texts[-1]


def slide(kind, title, bullets, notes, point=None, subtitle=None):
    return {'kind': kind, 'title': title, 'subtitle': subtitle, 'bullets': bullets, 'notes': notes, 'point': point}


def build(profile, fit_items, job, backend):
    """Five or six slides with speaker notes, aimed at a two-minute introduction."""
    name = (profile.get('name') or '').strip()
    first = name.split(' ')[0] if name else ''
    facts = profile.get('summary_facts') or []
    who = sentences(facts[0])[0] if facts else ''
    spoken_who = first_person(who) if who and first_person(who) != who else (f"I'm {'an' if who[:1].lower() in 'aeiou' else 'a'} {lower_first(who)}" if who else '')
    deck = [slide('title', name or '[Your name]', [{'text': who, 'source': 'Summary fact'}] if who else [],
                  ' '.join(filter(None, [f"Hi, I'm {first}." if first else '[Say your name.]', spoken_who])), point=who or None,
                  subtitle=f"Applying for {job['title']}")]

    strong = sorted((r for r in fit_items if r['status'] == 'strong'), key=lambda r: (r['level'] != 'required', -r.get('similarity', 0)))[:3]
    if strong:
        projects_used = list(dict.fromkeys(n for r in strong for n in source_names(r) if not n.startswith('Skills:')))
        evidence = f" I have used them in {listed(['my ' + n + ' work' for n in projects_used])}." if projects_used else ''
        deck.append(slide('fit', 'Why I fit this role', [{'text': r['text'], 'source': ' · '.join(source_names(r)) or None} for r in strong],
                          f"The {job['title']} role asks for {listed([lower_first(r['text']) for r in strong])}, and I can show evidence for each.{evidence}",
                          point=' '.join(r['text'] for r in strong)))

    options = stories(profile)
    projects = [s for s in options if s['kind'] == 'project']
    if projects:
        story = projects[closest([' '.join(s['sentences']) for s in projects], ' '.join(r['text'] for r in strong) or job['title'], backend)[0]]
        original = next(p for p in profile['projects'] if p['title'] == story['title'])
        bullets = [{'text': s, 'source': None} for s in sentences(original.get('description') or '')[:3]]
        recognition = achievements_about(profile, story['title'])
        bullets += [{'text': a, 'source': 'Achievement'} for a in recognition[:1]]
        if (original.get('technologies') or '').strip():
            bullets.append({'text': 'Technologies: ' + original['technologies'].strip(), 'source': None})
        notes = f"My strongest example is my {story['title']} project. " + ' '.join(story['sentences'][:3])
        notes += f" It was recognised as well: {recognition[0].rstrip('.')}." if recognition else ' [Add the outcome: what changed, ideally with a number.]'
        deck.append(slide('project', story['title'], bullets, notes, point=f"{story['title']}. {story['sentences'][0]}", subtitle='Highlight project'))

    roles = [s for s in options if s['kind'] == 'role']
    if roles:
        role = roles[0]
        deck.append(slide('experience', role['title'], [{'text': cv_style(s), 'source': None} for s in role['sentences'][:3]],
                          f"I also worked {role['as']}, where {lower_first(role['sentences'][0])} " + ' '.join(role['sentences'][1:3]),
                          point=f"{role['title']}. {role['sentences'][0]}", subtitle=role['as'][3:].split(' at ', 1)[-1]))

    gaps = sorted((r for r in fit_items if r['status'] == 'gap' and r['level'] != 'responsibility'), key=lambda r: r['level'] != 'required')[:2]
    if gaps:
        deck.append(slide('growth', 'What I am building next', [{'text': r['text'], 'source': f"{r['level'].capitalize()} in the job ad"} for r in gaps],
                          f"I'm still building experience in {listed([lower_first(r['text']) for r in gaps])}. [Say how you plan to close this gap.]",
                          point=' '.join(r['text'] for r in gaps)))

    contact = [v for v in (profile.get('email'), profile.get('linkedin'), profile.get('github'), profile.get('portfolio')) if v]
    deck.append(slide('closing', 'Thank you', [{'text': c, 'source': None} for c in contact],
                      f"Thank you. I would be glad to bring this experience to the {job['title']} role.", subtitle='Questions are welcome'))
    words = sum(len(s['notes'].split()) for s in deck)
    return {'job': job, 'slides': deck, 'target_seconds': TARGET_SECONDS, 'estimated_seconds': round(words / WORDS_PER_MINUTE * 60),
            'note': 'Built only from your confirmed profile and your fit for this job. Speaker notes are a starting script: put [bracketed] parts in your own words.'}


def plain(text):
    """Keep characters the built-in PDF fonts can draw."""
    return (text or '').encode('cp1252', 'replace').decode('cp1252')


def render_pdf(deck):
    """The deck as 16:9 PDF slides, followed by a speaker-script page."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=PAGE)
    pdf.setTitle(plain(f"{deck['slides'][0]['title']} - {deck['job']['title']}"))
    width, height = PAGE
    bullet_style = ParagraphStyle('bullet', fontName='Helvetica', fontSize=19, leading=25, textColor=INK, leftIndent=22, bulletIndent=0, bulletFontSize=19, bulletColor=ACCENT)
    source_style = ParagraphStyle('source', fontName='Helvetica', fontSize=12, leading=15, textColor=MUTED, leftIndent=22)
    for number, item in enumerate(deck['slides'], 1):
        pdf.setFillColor(PAPER)
        pdf.rect(0, 0, width, height, stroke=0, fill=1)
        pdf.setFillColor(ACCENT)
        pdf.rect(0, height - 12, width, 12, stroke=0, fill=1)
        if item['kind'] in ('title', 'closing'):
            pdf.setFillColor(INK)
            pdf.setFont('Helvetica-Bold', 44)
            pdf.drawString(70, height - 210, plain(item['title']))
            pdf.setFillColor(ACCENT)
            pdf.setFont('Helvetica', 22)
            pdf.drawString(72, height - 250, plain(item['subtitle'] or ''))
            y = height - 310
        else:
            pdf.setFillColor(MUTED)
            pdf.setFont('Helvetica', 14)
            pdf.drawString(70, height - 70, plain((item['subtitle'] or '').upper()))
            pdf.setFillColor(INK)
            pdf.setFont('Helvetica-Bold', 32)
            pdf.drawString(70, height - 110, plain(item['title']))
            y = height - 160
        for bullet in item['bullets']:
            for text, style, mark in ((bullet['text'], bullet_style, '•'), (bullet['source'], source_style, None)):
                if not text:
                    continue
                paragraph = Paragraph(escape(plain(text)), style, bulletText=mark)
                _, used = paragraph.wrap(width - 160, y)
                paragraph.drawOn(pdf, 70, y - used)
                y -= used + (4 if style is bullet_style else 12)
        pdf.setFillColor(MUTED)
        pdf.setFont('Helvetica', 11)
        pdf.drawRightString(width - 40, 24, f"{number} / {len(deck['slides'])}")
        pdf.showPage()
    pdf.setFillColor(INK)
    pdf.setFont('Helvetica-Bold', 24)
    pdf.drawString(60, height - 70, f"Speaker script (about {deck['estimated_seconds']} seconds)")
    script_style = ParagraphStyle('script', fontName='Helvetica', fontSize=13, leading=18, textColor=INK)
    y = height - 100
    for number, item in enumerate(deck['slides'], 1):
        paragraph = Paragraph(f"<b>{number}. {escape(plain(item['title']))}</b> - {escape(plain(item['notes']))}", script_style)
        _, used = paragraph.wrap(width - 120, y)
        paragraph.drawOn(pdf, 60, y - used)
        y -= used + 10
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()

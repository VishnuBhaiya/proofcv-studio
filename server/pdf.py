"""Selectable-text A4 CV export, guarded by current confirmed source facts."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from .cv import validate_draft


def render(state):
    validate_draft(state)
    draft, profile = state['draft'], state['confirmed_profile']
    font, bold = 'Helvetica', 'Helvetica-Bold'
    for directory, regular, strong in [(Path('C:/Windows/Fonts'), 'arial.ttf', 'arialbd.ttf'),
            (Path('/usr/share/fonts/truetype/dejavu'), 'DejaVuSans.ttf', 'DejaVuSans-Bold.ttf')]:
        if (directory / regular).is_file() and (directory / strong).is_file():
            if 'ProofCV' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('ProofCV', str(directory / regular)))
                pdfmetrics.registerFont(TTFont('ProofCVBold', str(directory / strong)))
            font, bold = 'ProofCV', 'ProofCVBold'
            break
    design = draft.get('design', {})
    ats = bool(design.get('ats'))
    accent = colors.HexColor('#202820' if ats else draft['accent'])
    if design.get('font') == 'serif': font, bold = 'Times-Roman', 'Times-Bold'
    elif design.get('font') == 'mono': font, bold = 'Courier', 'Courier-Bold'
    elif ats: font, bold = 'Helvetica', 'Helvetica-Bold'
    sizes = {'compact': (8.5, 12), 'standard': (9.5, 14), 'large': (10.5, 16)}
    body_size, leading = sizes.get(design.get('size'), (9.5, 14))
    # Page preference must never silently override the user's text size.
    gaps = {'compact': 4, 'comfortable': 7, 'spacious': 11}
    base = ParagraphStyle('body', fontName=font, fontSize=body_size, leading=leading, spaceAfter=gaps.get(design.get('spacing'), 7), textColor=colors.HexColor('#39433c'))
    heading = ParagraphStyle('heading', parent=base, fontName=bold, fontSize=10, spaceBefore=14, spaceAfter=7, textColor=colors.HexColor('#202820') if ats else accent, keepWithNext=True)
    title = ParagraphStyle('name', parent=base, fontName=bold, fontSize=(22 if design.get('page') == 'one' else 27) if draft['template']=='editorial' else (20 if design.get('page') == 'one' else 23), leading=27 if design.get('page') == 'one' else 33, spaceAfter=9, textColor=colors.HexColor('#202820') if ats else accent, alignment=TA_LEFT if design.get('header') == 'left' or ats else TA_CENTER)
    if draft['template'] == 'classic':
        heading.textColor = colors.HexColor('#292929')
        heading.spaceBefore = 11
    if design.get('header') == 'left' or ats:
        title.alignment = TA_LEFT
    item = ParagraphStyle('item', parent=base, fontName=bold, keepWithNext=True)
    if not ats:
        if draft['template'] == 'modern':
            heading.borderColor = accent
            heading.borderWidth = 1
            heading.borderPadding = 5
        elif draft['template'] == 'minimal':
            heading.spaceBefore = 10
            title.fontSize = 23
        elif draft['template'] == 'executive':
            heading.backColor = colors.HexColor('#f0f2ec')
            heading.borderPadding = 5
            title.fontSize = 29
    small = ParagraphStyle('small', parent=base, fontSize=8, leading=11)
    def paragraph(text, style=base):
        return Paragraph(escape(str(text)).replace('\n', '<br/>'), style)
    output = BytesIO()
    margin = 36 if design.get('page') == 'one' else 48
    document = SimpleDocTemplate(output, pagesize=A4, rightMargin=margin, leftMargin=margin,
                                 topMargin=32 if design.get('page') == 'one' else 42, bottomMargin=40 if design.get('page') == 'one' else 46, title=profile['name'] + ' - ' + draft['job']['title'], author=profile['name'])
    contact_style = ParagraphStyle('contact', parent=small, alignment=TA_LEFT if design.get('header') == 'left' or ats else TA_CENTER)
    story = [paragraph(profile['name'], title), paragraph(' | '.join(profile.get(k, '') for k in ('email', 'phone', 'location', 'linkedin', 'github', 'portfolio') if profile.get(k)), contact_style),
             paragraph('Target role: ' + draft['job']['title'], small),
             *([] if ats else [HRFlowable(width='100%', thickness=1, color=accent)]),
             paragraph('PROFILE', heading), paragraph(draft['summary']),
             paragraph('TECHNICAL SKILLS', heading)]
    skills = draft['selection']['skills']
    if design.get('skills') == 'grouped':
        skills_text = '<br/>'.join(escape(' · '.join(skills[i:i + 4])) for i in range(0, len(skills), 4))
        story.append(Paragraph(skills_text, base))
    elif design.get('skills') == 'pills' and not ats:
        story.append(paragraph('  '.join('[' + skill + ']' for skill in skills)))
    else:
        story.append(paragraph((' | ' if ats else ' · ').join(skills)))
    section_order = design.get('visible_sections') or draft['selection']['section_order']
    section_order = [section for section in section_order if section in draft['selection']['section_order']]
    if design.get('page') == 'two' and section_order:
        story.append(PageBreak())
    for section in section_order:
        if section in ('experience', 'achievements') and profile[section].strip().lower() in ('none', 'no', 'n/a'):
            continue
        story.append(paragraph(section.upper(), heading))
        if section == 'projects':
            for index in draft['selection']['project_order']:
                project = profile['projects'][index]
                excerpt = draft.get('project_excerpts', {}).get(str(index), {}).get('text', project['description'])
                story.extend([paragraph(project['title'], item), paragraph(excerpt)])
                if project['technologies']:
                    story.append(paragraph(project['technologies'], small))
                story.append(Spacer(1, 4))
        elif section == 'experience':
            story.append(paragraph(draft.get('experience_excerpt', profile[section])))
        else:
            story.append(paragraph(profile[section]))
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(font, 7)
        canvas.setFillColor(colors.HexColor('#667369'))
        canvas.drawString(48, 26, draft['job']['document_id'])
        canvas.drawRightString(A4[0]-48, 26, f'Page {doc.page}')
        canvas.restoreState()
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()

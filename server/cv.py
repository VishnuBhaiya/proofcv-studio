"""Evidence-selected CVs: every rendered claim has an exact confirmed source."""
import json
import re
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from .prompts import CV_SYSTEM, CV_VERSION
from .store import require_confirmed

SECTIONS = ['projects', 'education', 'experience', 'achievements']

ROLE_TERMS = (
    'computer vision', 'video analytics', 'object detection', 'image classification',
    'openCV', 'YOLO', 'edge', 'GPU', 'NLP', 'multimodal', 'language model',
    'transformer', 'text', 'sentiment', 'RAG', 'agentic AI', 'machine learning',
    'deep learning', 'data analysis', 'statistics', 'Python', 'Java', 'SQL',
    'PyTorch', 'TensorFlow', 'scikit-learn', 'NumPy', 'Pandas', 'Flask',
    'deployment', 'API', 'CI/CD', 'Git', 'dataset', 'pipeline', 'evaluation')


def normalized(text):
    return ' ' + re.sub(r'[^a-z0-9+#]+', ' ', str(text).lower()).strip() + ' '


def phrase_in(text, phrase):
    return normalized(phrase) in normalized(text)


def relevance_score(text, job):
    """Transparent, deterministic tie-breaker for evidence emphasis."""
    evidence, target = str(text), job['title'] + ' ' + job['description']
    score = sum(4 for term in ROLE_TERMS if phrase_in(evidence, term) and phrase_in(target, term))
    evidence_tokens = {t for t in normalized(evidence).split() if len(t) > 4}
    target_tokens = {t for t in normalized(target).split() if len(t) > 4}
    return score + len(evidence_tokens & target_tokens)


def tailor_selection(selection, profile, job):
    """Apply safe relevance safeguards while retaining only confirmed evidence."""
    result = deepcopy(selection)
    model_order = {index: position for position, index in enumerate(result['project_order'])}
    is_early_career = bool(re.search(r'\b(?:graduate|intern|junior)\b', job['title'], re.I))
    # The model proposes an order, then this transparent safeguard makes the
    # evidence emphasis reproducible. The full profile is never changed.
    ranked_projects = sorted(range(len(profile['projects'])), key=lambda index: (
        -relevance_score(' '.join(profile['projects'][index].values()), job),
        model_order.get(index, len(profile['projects']) + index)))
    positive = [index for index in ranked_projects
                if relevance_score(' '.join(profile['projects'][index].values()), job) > 0]
    candidates = positive or ranked_projects
    specialist = bool(re.search(r'\bcomputer\s+vision\b', job['title'], re.I))
    result['project_order'] = candidates[:1 if specialist else min(2, len(candidates))]

    job_text = job['title'] + ' ' + job['description']
    exact_matches = [skill for skill in profile['skills'] if phrase_in(job_text, skill)]
    if len(exact_matches) >= 4:
        result['skills'] = exact_matches
    else:
        result['skills'] = list(dict.fromkeys(exact_matches + result['skills']))[:8]

    # Long project descriptions remain intact in the projects section. The
    # summary uses one exact confirmed sentence from the strongest project so
    # it is concise and visibly specific to the selected job.
    top = result['project_order'][0]
    sentence_ids = [key for key in facts(profile) if key.startswith(f'project:{top}:sentence:')]
    selected_project_evidence = any(key.startswith('project:') for key in result['summary_fact_ids'])
    if sentence_ids and selected_project_evidence:
        best = max(sentence_ids, key=lambda key: relevance_score(facts(profile)[key], job))
        non_project = [key for key in result['summary_fact_ids'] if not key.startswith('project:')]
        result['summary_fact_ids'] = list(dict.fromkeys(non_project[:2] + [best]))

    needed = {'projects', 'education'} | {section for section in ('experience', 'achievements')
        if profile[section].strip().lower() not in ('', 'none', 'no', 'n/a')}
    if is_early_career:
        preferred = ['education', 'projects', 'achievements', 'experience']
    else:
        preferred = ['projects', 'experience', 'education', 'achievements']
    result['section_order'] = [section for section in preferred if section in needed]
    # The deterministic safeguard can legitimately change the model's proposed
    # project order. Describe the final applied selection rather than retaining
    # a now-stale model rationale.
    project_titles = [profile['projects'][index]['title'] for index in result['project_order']]
    result['rationale'] = (
        f"Final applied emphasis for {job['title']}: "
        f"projects {', '.join(project_titles)}; "
        f"summary sources {', '.join(result['summary_fact_ids'])}; "
        f"{len(result['skills'])} confirmed role-matched skills. "
        'ProofCV applied confirmed-evidence relevance checks for this target job.'
    )[:4000]
    return result


def project_excerpt(project, job, position):
    """Select complete source sentences; retain full facts in the profile."""
    if position == 0:
        return project['description']
    sentences = list(dict.fromkeys(s.strip() for s in re.split(r'(?<=[.!?])\s+', project['description']) if s.strip()))
    limit = 2 if position == 1 else 1
    ranked = sorted(range(len(sentences)), key=lambda i: -relevance_score(sentences[i], job))[:limit]
    return '\n'.join(sentences[i] for i in sorted(ranked))


def experience_excerpt(experience, job):
    """Keep the role heading and select job-relevant confirmed experience sentences."""
    parts = [part.strip() for part in str(experience).splitlines() if part.strip()]
    if not parts:
        return ''
    heading = parts[0]
    detail_text = ' '.join(parts[1:])
    if not detail_text:
        return heading
    sentences = list(dict.fromkeys(
        sentence.strip() for sentence in re.split(r'(?<=[.!?])\s+', detail_text)
        if sentence.strip()))
    if not sentences:
        return str(experience).strip()
    specialist = bool(re.search(r'\bcomputer\s+vision\b', job['title'], re.I))
    early_career = bool(re.search(r'\b(?:graduate|intern|junior)\b', job['title'], re.I))
    limit = 2 if specialist else 3
    if early_career and not specialist:
        transferable = ('leadership', 'users', 'requirements', 'workflows', 'troubleshoot',
                        'errors', 'time', 'visibility', 'records', 'customer', 'supplier',
                        'communication', 'stakeholder')
        specialist_terms = ('deployment', 'model', 'computer vision', 'object detection')
        score = lambda sentence: (10 * sum(phrase_in(sentence, term) for term in transferable)
                                  - 4 * sum(phrase_in(sentence, term) for term in specialist_terms)
                                  + relevance_score(sentence, job))
    else:
        score = lambda sentence: relevance_score(sentence, job)
    ranked = sorted(range(len(sentences)), key=lambda i: (-score(sentences[i]), i))[:limit]
    return heading + '\n' + ' '.join(sentences[i] for i in sorted(ranked))


def refresh_excerpts(draft):
    if not draft.get('tailored_content'):
        return
    draft['project_excerpts'] = {
        str(i): {'source': draft['profile']['projects'][i]['description'],
                 'text': project_excerpt(draft['profile']['projects'][i], draft['job'], pos)}
        for pos, i in enumerate(draft['selection']['project_order'])}
    experience = draft['profile'].get('experience', '')
    draft['experience_excerpt'] = ('' if experience.strip().lower() in ('', 'none', 'no', 'n/a')
                                   else experience_excerpt(experience, draft['job']))


def facts(profile):
    result = {'education': profile['education']}
    for index, project in enumerate(profile['projects']):
        result[f'project:{index}'] = project['description']
        sentences = [sentence.strip() for sentence in re.split(r'(?<=[.!?])\s+', project['description'])
                     if sentence.strip()]
        for sentence_index, sentence in enumerate(sentences):
            result[f'project:{index}:sentence:{sentence_index}'] = sentence
    for index, text in enumerate(profile['summary_facts']):
        result[f'summary:{index}'] = text
    for field in ('experience', 'achievements'):
        if profile[field].lower() not in ('none', 'no', 'n/a'):
            result[field] = profile[field]
    return {key: value for key, value in result.items() if value.strip()}


def summary_sources(text, catalog):
    """Parse a summary as a sequence of exact facts, including multiline facts."""
    remaining = text.strip()
    selected = []
    while remaining:
        matched = next(((key, value) for key, value in sorted(catalog.items(), key=lambda pair:len(pair[1]), reverse=True)
                        if remaining == value.strip() or remaining.startswith(value.strip() + '\n\n')), None)
        if matched is None:
            raise ValueError('Summary contains unconfirmed wording. Add it as a profile summary fact, review and confirm, then regenerate.')
        key, value = matched
        selected.append(key)
        remaining = remaining[len(value.strip()):].strip()
    if not selected:
        raise ValueError('A CV summary must include at least one confirmed source fact.')
    return list(dict.fromkeys(selected))


def contains(text, term):
    return bool(re.search(r'(?<![\w])' + re.escape(term.lower()) + r'(?![\w])', text.lower()))


def match_analysis(profile, job):
    description = job['description']
    matched = [{'skill': skill, 'profile_source': 'Confirmed skills',
                'job_excerpt': next((s.strip() for s in re.split(r'(?<=[.;])\s+', description) if contains(s, skill)), description)}
               for skill in profile['skills'] if contains(description, skill)]
    requirements = ['Python', 'SQL', 'RAG', 'PyTorch', 'TensorFlow', 'Docker', 'AWS',
                    'Azure', 'machine learning', 'computer vision', 'MLOps', 'NLP',
                    'scikit-learn', 'production', 'deployment', "master", 'PhD']
    source = ' '.join(facts(profile).values()) + ' ' + ' '.join(profile['skills'])
    missing = [{'requirement': term, 'job_excerpt': next((s.strip() for s in re.split(r'(?<=[.;])\s+', description) if contains(s, term)), description)}
               for term in requirements if contains(description, term) and not contains(source, term)]
    if re.search(r'\b(senior|manager|lead)\b', job['title'], re.I):
        missing.append({'requirement': 'Seniority / leadership: verify eligibility',
                        'job_excerpt': job['title']})
    for sentence in re.split(r'(?<=[.;])\s+', description):
        if re.search(r'\b(?:\d+\+?|two|three|four|five|six|seven|eight|ten)\s+(?:or more\s+)?years?\b', sentence, re.I) and not re.search(r'up to|at most', sentence, re.I):
            missing.append({'requirement': 'Required experience duration: not automatically verified',
                            'job_excerpt': sentence.strip()})
    # No claim that this conservative lexicon exhaustively verifies eligibility.
    return dict(matched=matched, missing=missing,
                limitation='Conservative text-based evidence check, not an eligibility score. Read the full job for seniority, qualifications and other requirements.')


def validate_selection(selection, profile):
    required = {'summary_fact_ids', 'skills', 'project_order', 'section_order', 'rationale'}
    if not isinstance(selection, dict) or set(selection) != required:
        raise ValueError('AI selection has invalid fields.')
    catalog = facts(profile)
    ids = selection['summary_fact_ids']
    if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in catalog for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Summary refers to missing or repeated source facts.')
    skills = selection['skills']
    if not isinstance(skills, list) or any(not isinstance(s, str) or s not in profile['skills'] for s in skills) or len(set(skills)) != len(skills):
        raise ValueError('CV skills must come from the confirmed profile.')
    indexes = selection['project_order']
    if (not isinstance(indexes, list) or not indexes or any(type(i) is not int for i in indexes)
            or len(set(indexes)) != len(indexes) or any(i not in range(len(profile['projects'])) for i in indexes)):
        raise ValueError('Project order must select a non-empty unique subset of confirmed projects.')
    sections = selection['section_order']
    needed = {'projects', 'education'} | {s for s in ('experience','achievements') if profile[s].strip().lower() not in ('', 'none', 'no', 'n/a')}
    if not isinstance(sections, list) or any(not isinstance(s, str) for s in sections) or len(set(sections)) != len(sections) or set(sections)-set(SECTIONS) or not needed.issubset(sections):
        raise ValueError('Section order is invalid.')
    if not isinstance(selection['rationale'], str) or len(selection['rationale']) > 4000:
        raise ValueError('Invalid rationale.')


def selection_schema(profile):
    catalog = facts(profile)
    return {'type':'object','additionalProperties':False,
        'required':['summary_fact_ids','skills','project_order','section_order','rationale'],
        'properties':{
            'summary_fact_ids':{'type':'array','minItems':min(2,len(catalog)),'maxItems':min(3,len(catalog)),
                                'items':{'type':'string','enum':list(catalog)}},
            'skills':{'type':'array','items':{'type':'string','enum':profile['skills']}},
            'project_order':{'type':'array','minItems':1,'maxItems':len(profile['projects']),
                             'items':{'type':'integer','enum':list(range(len(profile['projects'])))}},
            'section_order':{'type':'array','minItems':2,'maxItems':4,'items':{'type':'string','enum':SECTIONS}},
            'rationale':{'type':'string'}}}


def generate(state, job, model):
    require_confirmed(state)
    profile = state['confirmed_profile']
    selection = json.loads(model.decide([{'role': 'system', 'content': CV_SYSTEM},
        {'role': 'user', 'content': json.dumps({'facts': facts(profile), 'profile': profile, 'job': job})}], {'_output_schema': selection_schema(profile)}))
    validate_selection(selection, profile)
    selection = tailor_selection(selection, profile, job)
    validate_selection(selection, profile)
    draft = dict(id=uuid.uuid4().hex, revision=state['revision'], job=job,
                 selection=selection, summary='\n\n'.join(facts(profile)[i] for i in selection['summary_fact_ids']),
                 template='classic', accent='#292929', design=dict(font='sans', size='compact', spacing='compact', header='left', skills='inline', page='one', ats=True, visible_sections=selection['section_order'][:]), profile=deepcopy(profile),
                 analysis=match_analysis(profile, job), prompt_version=CV_VERSION,
                 model=model.name, suggestion_status='accepted')
    draft['suggested_order'] = {'project_order': selection['project_order'][:], 'section_order': selection['section_order'][:]}
    draft['suggestion_note'] = 'Applied automatically when you selected this target job. You can still edit or dismiss the emphasis.'
    draft['tailored_content'] = True
    refresh_excerpts(draft)
    if state['draft']:
        save_version(state)
    state['draft'] = draft
    state['undo'] = None
    return draft


def validate_draft(state):
    require_confirmed(state)
    draft = state['draft']
    if not draft or draft['revision'] != state['revision'] or draft['profile'] != state['confirmed_profile']:
        raise ValueError('This draft uses an older profile. Generate a new CV after confirming your changes.')
    validate_selection(draft['selection'], draft['profile'])
    refresh_excerpts(draft)
    if not all(isinstance(draft.get(key), str) for key in ('summary', 'template', 'accent')):
        raise ValueError('Summary, template and accent must be text.')
    summary_sources(draft['summary'], facts(draft['profile']))
    if draft['template'] not in ('editorial', 'classic', 'modern', 'minimal', 'executive') or not re.fullmatch(r'#[0-9a-fA-F]{6}', draft['accent']):
        raise ValueError('Invalid document style.')
    if 'design' not in draft:
        draft['design'] = dict(font='sans', size='standard', spacing='comfortable', header='center', skills='inline', page='auto', ats=False, visible_sections=SECTIONS[:])
    design = draft.get('design', {})
    if not isinstance(design, dict) or design.get('font') not in ('sans', 'serif', 'mono') or design.get('size') not in ('compact', 'standard', 'large') or design.get('spacing') not in ('compact', 'comfortable', 'spacious') or design.get('header') not in ('center', 'left') or design.get('skills') not in ('inline', 'pills', 'grouped') or design.get('page') not in ('auto', 'one', 'two') or not isinstance(design.get('ats'), bool) or not isinstance(design.get('visible_sections'), list) or len(set(design['visible_sections'])) != len(design['visible_sections']) or not {'projects', 'education'}.issubset(design['visible_sections']) or any(s not in SECTIONS for s in design['visible_sections']):
        raise ValueError('Invalid design settings.')


def edit(state, patch):
    if not isinstance(patch, dict) or set(patch) - {'summary', 'template', 'accent', 'selection', 'design'}:
        raise ValueError('Unsupported CV change.')
    before = deepcopy(state['draft'])
    if before is None:
        raise ValueError('Generate a CV first.')
    state['draft'].update(patch)
    try:
        validate_draft(state)
    except ValueError:
        state['draft'] = before
        raise
    state['undo'] = before
    state['draft']['selection']['summary_fact_ids'] = summary_sources(state['draft']['summary'], facts(state['draft']['profile']))


def save_version(state):
    if state['draft']:
        state['versions'].insert(0, {'id': uuid.uuid4().hex,
            'saved_at': datetime.now(timezone.utc).isoformat(), 'draft': deepcopy(state['draft'])})

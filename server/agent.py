"""Live model chooses actions; Python executes an allowlisted bounded tool loop."""
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from .gemini import GeminiError
from .prompts import (AGENT_SYSTEM, AGENT_VERSION, CV_CHAT_SYSTEM, CV_CHAT_VERSION,
                      FOLLOWUP_SYSTEM, FOLLOWUP_VERSION)
from .store import update_profile, missing_fields, require_confirmed, validate_profile
from . import cv


def validate_explicit_empty_fields(patch, message, previous_answer=''):
    """Omitted experience/achievements are unknown, not implicitly absent."""
    if not isinstance(patch, dict):
        raise ValueError('Profile patch must be an object.')
    topics = {'experience': r'(?:experience|employment|work history)',
              'achievements': r'(?:achievements?|awards?|accomplishments?|certifications?)'}
    for field, topic in topics.items():
        value = patch.get(field)
        if not isinstance(value, str) or value.strip().lower() not in ('none', 'no', 'n/a'):
            continue
        explicit = bool(re.search(r'"'+field+r'"\s*:\s*"(?:none|no|n/a)"', message, re.I))
        explicit |= bool(re.search(r'\b(?:no|none|not any|don.t have any)\b[^.!?\n]{0,55}\b'+topic+r'\b', message, re.I))
        explicit |= bool(re.search(r'\b'+topic+r'\b[^.!?\n]{0,35}\b(?:none|n/a)\b', message, re.I))
        explicit |= (message.strip().lower().rstrip('.') in ('none','no','n/a') and '?' in previous_answer and bool(re.search(topic,previous_answer,re.I)))
        if not explicit:
            raise ValueError(f'{field} remains unknown. Ask the user about {field}; do not infer None from an omitted field or a different answer.')


def _normalise_skill_text(value):
    """Return a comparison-friendly skill phrase without changing its display text."""
    return re.sub(r'[^a-z0-9+#/.]+', ' ', str(value).casefold()).strip()


def _skill_is_named_in_message(skill, message):
    phrase = _normalise_skill_text(skill)
    if not phrase:
        return False
    message_text = ' ' + _normalise_skill_text(message) + ' '
    return f' {phrase} ' in message_text


def _unique_skill_names(values):
    result = []
    seen = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        clean = value.strip()
        key = clean.casefold()
        if key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def _skill_addition_requested(message, candidates):
    """Detect an explicit skill addition so model context cannot broaden it."""
    lower = message.casefold()
    if not re.search(r'\b(?:add|include|append|insert|put)\b', lower):
        return False
    if re.search(r'\bskills?\b', lower):
        return True
    return any(_skill_is_named_in_message(skill, message) for skill in candidates)


def _skill_replacement_requested(message):
    lower = message.casefold()
    return bool(re.search(r'\b(?:replace|set|change|update|edit)\b[^.!?\n]{0,80}\bskills?\b', lower)
                or re.search(r'\bskills?\b[^.!?\n]{0,80}\b(?:replace|set|change|update|edit)\b', lower))


def _requested_profile_fields(message):
    """Return only profile fields explicitly named in a CV-chat request.

    The model sees the full profile as context and can echo unrelated fields in a
    patch. Tying writes to the user's words prevents a narrow request such as
    "add MLOps" from overwriting achievements or expanding every project.
    """
    patterns = {
        'name': r'\b(?:name|full name)\b',
        'email': r'\b(?:email|e-mail)\b',
        'phone': r'\b(?:phone|mobile|telephone)\b',
        'location': r'\b(?:location|address|city|suburb)\b',
        'linkedin': r'\b(?:linked\s*in|links?)\b',
        'github': r'\b(?:github|links?)\b',
        'portfolio': r'\b(?:portfolio|personal website|portfolio website|links?)\b',
        'education': r'\b(?:education|degree|university|college|qualification|studying)\b',
        'skills': r'\bskills?\b',
        'projects': r'\bprojects?\b',
        'experience': r'\b(?:work experience|employment|job history|work history|employment history|worked at|role at|position at)\b',
        'achievements': r'\b(?:achievement|achievements|award|awards|scholarship|scholarships|accomplishment|accomplishments)\b',
        'goal': r'\b(?:goal|target role|career target|job target)\b',
        'summary_facts': r'\b(?:summary|profile statement|professional statement)\b',
    }
    return {field for field, pattern in patterns.items() if re.search(pattern, message, re.I)}


def run_turn(state, message, model, retrieve, save, max_steps=8, require_review=False):
    if not isinstance(message, str) or not 1 <= len(message.strip()) <= 12000:
        raise ValueError('Enter a message up to 12000 characters.')
    state['messages'].append({'role': 'user', 'content': message.strip()})
    state['trace'] = []
    state['stop_reason'] = None
    save(state)
    seen = set()
    response_repairs = 0
    def finish():
        state.setdefault('audit_runs', []).append(dict(at=datetime.now(timezone.utc).isoformat(),
            message=message, prompt_version=AGENT_VERSION + ('-review-v1' if require_review else ''), model=model.name,
            trace=deepcopy(state['trace']), stop_reason=state['stop_reason']))
        save(state)
    review_rules = ''' In this session update_profile proposes changes only: it never writes the profile.
After a pending_review observation, ask the user to Accept, edit or Dismiss the proposal in the UI.
Do not claim changes are saved. Do not retrieve jobs while a proposal is pending.
Even a confirmed profile may need corrections: process new facts before discussing jobs.
Improve grammar and expand clear abbreviations only; preserve studying versus graduated,
coursework versus employment, and skill qualifiers. Ask for responsibilities, tools and
outcomes before elaborating work. Never invent them.
The current profile is already provided in runtime context; get_profile is optional.
Answer conversationally in at most three short sentences. Ask only one question at a time.
Do not repeat contact details or dump the profile. To propose new wording, call update_profile.
Never claim a profile was updated, saved or changed: only the user's Accept action does that.''' if require_review else ''
    messages = [{'role': 'system', 'content': AGENT_SYSTEM + review_rules}] + state['messages'][-30:]
    for step in range(1, max_steps + 1):
        context = {'profile': state['profile'], 'revision': state['revision'],
                   'pending_profile': state.get('pending_profile'),
                   'confirmed': state['confirmed_revision'] == state['revision'],
                   'missing_fields': missing_fields(state['profile']), 'prompt_version': AGENT_VERSION}
        try:
            action = json.loads(model.decide(messages, context))
            if not isinstance(action, dict):
                raise ValueError('Expected an action object.')
        except (GeminiError, ValueError) as error:
            state['stop_reason'] = 'provider_error'
            state['trace'].append({'step': step, 'error': str(error), 'executed': False})
            finish()
            raise
        # Gemini occasionally omits the explicit discriminator while returning
        # the valid tool payload. Normalize that harmless formatting variation.
        if 'type' not in action and isinstance(action.get('tool'), str) and isinstance(action.get('arguments'), dict):
            action = {**action, 'type': 'tool_call'}
        elif (action.get('type') in {'get_profile', 'update_profile', 'retrieve_jobs'}
              and 'tool' not in action and isinstance(action.get('arguments'), dict)):
            action = {'type': 'tool_call', 'tool': action['type'],
                      'arguments': action['arguments']}
        if action.get('type') == 'final_answer' and isinstance(action.get('answer'), str) and action['answer'].strip():
            failed = any(not event.get('executed', False) for event in state['trace'])
            claimed_write = re.search(r"\b(?:I(?:'ve| have)?|we(?:'ve| have)?|your (?:profile|project|details?))\b[^.!?\n]{0,70}\b(?:updated|saved|recorded|added|changed|rewritten)\b", action['answer'], re.I)
            if require_review and not state.get('pending_profile') and (failed or claimed_write):
                if response_repairs == 0 and step < max_steps:
                    response_repairs += 1
                    messages.extend([{'role': 'assistant', 'content': json.dumps(action)},
                        {'role': 'user', 'content': 'Runtime validation: no profile proposal exists and no profile write occurred. Correct the failed tool call using update_profile with arguments.patch, or ask one clarification question. Do not claim success.'}])
                    state['trace'].append({'step': step, 'executed': False, 'observation': {'error': 'Unsupported success response blocked'}})
                    continue
                state['messages'].append({'role': 'assistant', 'content': 'I could not prepare that change for review. Your profile is unchanged. Please try again or edit the project details in the form.'})
                state['stop_reason'] = 'invalid_response'
                finish()
                return state
            answer = ('I have prepared suggested profile wording from your message. Nothing has been added to the form yet. Please accept, edit or dismiss the proposal below.' if require_review and state.get('pending_profile') else action['answer'])
            state['messages'].append({'role': 'assistant', 'content': answer})
            state['stop_reason'] = 'final_answer'
            finish()
            return state
        before = state['revision']
        key = json.dumps(action, sort_keys=True)
        if key in seen:
            state['stop_reason'] = 'repeated_action'
            state['trace'].append({'step': step, 'action': action, 'observation': {'error': 'Repeated action blocked'}, 'executed': False})
            break
        seen.add(key)
        executed = False
        try:
            if action.get('type') != 'tool_call' or not isinstance(action.get('arguments'), dict):
                raise ValueError('Expected a tool_call with an arguments object or final_answer.')
            tool, args = action.get('tool'), action['arguments']
            if tool == 'get_profile' and args == {}:
                observation = context
            elif tool == 'update_profile' and set(args) == {'patch'}:
                previous = next((m['content'] for m in reversed(state['messages'][:-1]) if m['role']=='assistant'), '')
                new_absences = {key:value for key,value in args['patch'].items() if state['profile'].get(key)!=value} if isinstance(args['patch'],dict) else args['patch']
                validate_explicit_empty_fields(new_absences, message, previous)
                if require_review:
                    # Never preserve placeholder technology text from an earlier
                    # model response; an unknown tool remains unanswered.
                    proposed_patch = deepcopy(args['patch'])
                    if isinstance(proposed_patch.get('projects'), list):
                        for project in proposed_patch['projects']:
                            if isinstance(project, dict) and str(project.get('technologies', '')).strip().upper() in ('UNKNOWN', 'TBD'):
                                project['technologies'] = ''
                    args = {**args, 'patch': proposed_patch}
                    candidate = deepcopy(state)
                    observation = update_profile(candidate, args['patch'])
                    patch = {k: v for k, v in args['patch'].items() if state['profile'].get(k) != v}
                    if patch:
                        import uuid
                        patch = {**state.get('pending_profile', {}).get('patch', {}), **patch}
                        known = {s.lower() for s in state['profile'].get('skills', [])}
                        related = ['Python', 'Java', 'JavaScript', 'TypeScript', 'HTML', 'CSS', 'React', 'SQL', 'Git', 'REST APIs', 'Testing', 'Docker', 'Linux', 'AWS', 'Azure', 'Kubernetes', 'CI/CD', 'Terraform', 'NumPy', 'Pandas', 'R', 'scikit-learn', 'TensorFlow', 'PyTorch', 'OpenCV', 'Jupyter', 'Tableau', 'Power BI', 'Excel', 'Figma', 'Adobe Creative Suite', 'UX research', 'Prototyping', 'Wireshark', 'SIEM', 'Burp Suite', 'Agile', 'Scrum', 'Jira', 'C++', 'Arduino', 'Computer vision']
                        skill_context = bool(args['patch'].get('skills')) or any(term in message.lower() for term in ('skill', 'know ', 'used ', 'program'))
                        options = [s for s in related if s.lower() not in known and s.lower() not in {str(x).lower() for x in args['patch'].get('skills', [])} and (s.lower() in message.lower() or skill_context)]
                        if any(term in message.lower() for term in ('bachelor', 'degree', 'ai', 'artificial intelligence')):
                            options += [s for s in ('NumPy', 'Pandas', 'Git', 'PyTorch') if s.lower() not in known and s.lower() not in {x.lower() for x in options}]
                        if not options:
                            options = [s for s in related if s.lower() not in known][:6]
                        state['pending_profile'] = dict(id=uuid.uuid4().hex, revision=state['revision'], patch=patch, source=message, skill_options=options[:6])
                        observation = {'pending_review': True, 'proposed_fields': patch, 'profile_unchanged': True}
                    else:
                        observation = {'no_change': True, 'profile_unchanged': True}
                else:
                    observation = update_profile(state, args['patch'])
            elif tool == 'retrieve_jobs' and args == {}:
                if state.get('pending_profile'):
                    raise ValueError('Accept or dismiss the proposed profile changes first.')
                require_confirmed(state)
                state['retrieval'] = retrieve(state['confirmed_profile'])
                observation = state['retrieval']
            else:
                raise ValueError('Unknown tool or invalid arguments. No operation performed.')
            executed = True
        except ValueError as error:
            observation = {'error': str(error)}
        event = dict(step=step, action=action, observation=observation, executed=executed,
                     revision_before=before, revision_after=state['revision'])
        state['trace'].append(event)
        save(state)
        if executed and action.get('tool') == 'retrieve_jobs':
            state['messages'].append({'role': 'assistant', 'content':
                'I chose the job-retrieval tool and found the three strongest semantic matches from the supplied records. Review the evidence and choose a target role.'})
            state['stop_reason'] = 'retrieval_complete'
            finish()
            return state
        if require_review and executed and observation.get('pending_review'):
            state['messages'].append({'role': 'assistant', 'content': 'Here is my suggested wording. Does it accurately describe your work? Review it below, then accept, edit or dismiss it.'})
            state['stop_reason'] = 'pending_review'
            finish()
            return state
        messages.extend([{'role': 'assistant', 'content': json.dumps(action)},
                         {'role': 'user', 'content': 'Python tool observation: ' + json.dumps(observation)}])
    state['stop_reason'] = state['stop_reason'] or 'step_limit'
    state['messages'].append({'role': 'assistant', 'content': 'Stopped at the safety limit. Your recorded facts are saved. Review the tool activity before continuing.'})
    finish()
    return state


_FOLLOWUP_TERMS = {
    'name': r'\b(?:name|called)\b',
    'email': r'\b(?:email|e-mail)\b',
    'phone': r'\b(?:phone|mobile|contact number|telephone)\b',
    'education': r'\b(?:education|study|studying|school|college|university|qualification|degree)\b',
    'skills': r'\b(?:skills?|tools?|technology|technologies|languages?)\b',
    'projects': r'\b(?:projects?|built|contributed|created|developed)\b',
    'experience': r'\b(?:experience|employment|work|job)\b',
    'achievements': r'\b(?:achievements?|awards?|scholarships?|accomplishments?|certifications?)\b',
    'goal': r'\b(?:goal|role|job|career|position|target)\b',
}


def run_followup_turn(state, model, save, max_steps=4):
    """Let the live model choose the next post-acceptance interview question.

    Python validates that the chosen final_answer targets the first missing field,
    or ends questioning when the profile is complete. No fixed question text is
    substituted, so the stored Action is genuine model evidence.
    """
    state['trace'] = []
    state['stop_reason'] = None
    save(state)
    runtime_prompt = (
        'The reviewed proposal was accepted. Choose the next Action from the updated '
        'runtime state. Ask one question only when a required field is still missing.'
    )
    messages = ([{'role': 'system', 'content': FOLLOWUP_SYSTEM}]
                + state.get('messages', [])[-30:]
                + [{'role': 'user', 'content': runtime_prompt}])
    seen = set()

    def finish():
        state.setdefault('audit_runs', []).append({
            'at': datetime.now(timezone.utc).isoformat(),
            'message': runtime_prompt,
            'prompt_version': FOLLOWUP_VERSION,
            'model': model.name,
            'trace': deepcopy(state['trace']),
            'stop_reason': state['stop_reason'],
        })
        save(state)

    for step in range(1, max_steps + 1):
        missing = missing_fields(state['profile'])
        context = {
            'profile': state['profile'],
            'revision': state['revision'],
            'confirmed': state['confirmed_revision'] == state['revision'],
            'missing_fields': missing,
            'prompt_version': FOLLOWUP_VERSION,
        }
        try:
            action = json.loads(model.decide(messages, context))
            if not isinstance(action, dict):
                raise ValueError('Expected an action object.')
        except (GeminiError, ValueError) as error:
            state['trace'].append({'step': step, 'error': str(error), 'executed': False})
            state['stop_reason'] = 'provider_error'
            finish()
            raise
        if 'type' not in action and isinstance(action.get('tool'), str) and isinstance(action.get('arguments'), dict):
            action = {**action, 'type': 'tool_call'}
        elif (action.get('type') == 'get_profile' and 'tool' not in action
              and isinstance(action.get('arguments'), dict)):
            action = {'type': 'tool_call', 'tool': 'get_profile',
                      'arguments': action['arguments']}
        key = json.dumps(action, sort_keys=True)
        if key in seen:
            state['trace'].append({'step': step, 'action': action,
                                   'observation': {'error': 'Repeated Action blocked.'},
                                   'executed': False})
            state['stop_reason'] = 'repeated_action'
            finish()
            raise ValueError('Gemini repeated the same follow-up Action.')
        seen.add(key)

        if action.get('type') == 'tool_call' and action.get('tool') == 'get_profile' and action.get('arguments') == {}:
            observation = context
            state['trace'].append({'step': step, 'action': action,
                                   'observation': observation, 'executed': True,
                                   'revision_before': state['revision'],
                                   'revision_after': state['revision']})
            messages.extend([
                {'role': 'assistant', 'content': json.dumps(action)},
                {'role': 'user', 'content': 'Python tool Observation: ' + json.dumps(observation)},
            ])
            continue

        if action.get('type') == 'final_answer' and isinstance(action.get('answer'), str):
            answer = action['answer'].strip()
            if missing:
                field = missing[0]
                useful = bool(answer and '?' in answer and re.search(_FOLLOWUP_TERMS[field], answer, re.I))
                if not useful:
                    observation = {'error': 'Ask exactly one useful question about the first missing field: ' + field}
                elif answer.count('?') != 1:
                    observation = {'error': 'Ask exactly one question, not multiple questions.'}
                else:
                    observation = {'validated': 'model_chosen_followup', 'missing_field': field}
                    state['trace'].append({'step': step, 'action': action,
                                           'observation': observation, 'executed': True,
                                           'revision_before': state['revision'],
                                           'revision_after': state['revision']})
                    state['messages'].append({'role': 'assistant', 'content': answer})
                    state['stop_reason'] = 'followup_question'
                    finish()
                    return state
            else:
                useful = bool(answer and '?' not in answer and re.search(r'\b(?:review|confirm)\b', answer, re.I))
                if useful:
                    observation = {'validated': 'profile_complete_no_extra_question'}
                    state['trace'].append({'step': step, 'action': action,
                                           'observation': observation, 'executed': True,
                                           'revision_before': state['revision'],
                                           'revision_after': state['revision']})
                    state['messages'].append({'role': 'assistant', 'content': answer})
                    state['stop_reason'] = 'profile_complete'
                    finish()
                    return state
                observation = {'error': 'The profile is complete. Do not ask another factual question; direct the user to review and confirm.'}
        else:
            observation = {'error': 'Only get_profile or final_answer is allowed for the post-acceptance decision.'}

        state['trace'].append({'step': step, 'action': action,
                               'observation': observation, 'executed': False,
                               'revision_before': state['revision'],
                               'revision_after': state['revision']})
        messages.extend([
            {'role': 'assistant', 'content': json.dumps(action)},
            {'role': 'user', 'content': 'Python validation Observation: ' + json.dumps(observation)},
        ])

    state['stop_reason'] = 'step_limit'
    finish()
    raise ValueError('Gemini did not produce a valid post-acceptance follow-up Action.')


def _apply_cv_patch(state, patch):
    """Merge a small, model-proposed CV change and validate it atomically."""
    if not isinstance(patch, dict) or not patch or set(patch) - {'summary_fact_ids', 'skills', 'project_order', 'section_order', 'design', 'template', 'accent'}:
        raise ValueError('Unsupported CV change.')
    draft = state.get('draft')
    if not draft:
        raise ValueError('Generate a CV before editing it.')
    candidate = deepcopy(draft)
    selection = deepcopy(candidate['selection'])
    profile = candidate['profile']
    if 'summary_fact_ids' in patch:
        ids = patch['summary_fact_ids']
        catalog = cv.facts(profile)
        if not isinstance(ids, list) or not ids or any(i not in catalog for i in ids) or len(set(ids)) != len(ids):
            raise ValueError('Choose only existing confirmed summary fact IDs.')
        selection['summary_fact_ids'] = ids
        candidate['summary'] = '\n\n'.join(catalog[i] for i in ids)
    if 'skills' in patch:
        if not isinstance(patch['skills'], list) or any(s not in profile['skills'] for s in patch['skills']):
            raise ValueError('CV skills must come from the confirmed profile.')
        selection['skills'] = patch['skills']
    if 'project_order' in patch:
        selection['project_order'] = patch['project_order']
    if 'section_order' in patch:
        selection['section_order'] = patch['section_order']
        if isinstance(patch['section_order'], list):
            current_visible = candidate.get('design', {}).get('visible_sections', cv.SECTIONS)
            candidate.setdefault('design', {})['visible_sections'] = [s for s in patch['section_order'] if s in current_visible]
    if 'project_order' in patch or 'section_order' in patch:
        candidate['suggestion_note'] = 'Updated from the Gemini CV studio chat.'
    selection['rationale'] = selection.get('rationale', 'Edited with confirmed profile evidence.')
    candidate['selection'] = selection
    if 'design' in patch:
        if not isinstance(patch['design'], dict):
            raise ValueError('Design settings must be an object.')
        candidate['design'] = {**candidate.get('design', {}), **patch['design']}
    for key in ('template', 'accent'):
        if key in patch:
            candidate[key] = patch[key]
    before = state['draft']
    state['draft'] = candidate
    try:
        cv.validate_draft(state)
    except Exception:
        state['draft'] = before
        raise
    state['undo'] = deepcopy(before)
    return {'updated': sorted(patch), 'summary': candidate['summary'], 'design': candidate.get('design', {})}


def merge_added_projects(existing, proposed):
    """Append additions without deleting or rewriting an existing project."""
    if not isinstance(proposed, list):
        raise ValueError('Projects must be a list.')
    result = deepcopy(existing)
    for project in proposed:
        if not isinstance(project, dict) or not isinstance(project.get('title'), str):
            raise ValueError('Each project needs a title.')
        matches = [p for p in result if p['title'].strip().casefold() == project['title'].strip().casefold()]
        if matches:
            if project != matches[0]:
                raise ValueError('An existing project has that title. Ask whether to edit it or use a different title for the new project.')
        else:
            result.append(deepcopy(project))
    return result


def local_cv_action(state, message):
    """Small deterministic editor for common requests while Gemini is unavailable."""
    text = message.strip()
    lower = text.casefold()
    patch = {}
    if re.search(r'ats[ -]?(?:friendly|ready)', lower) and not re.search(r'\b(?:not|disable|remove)\b', lower):
        patch = {'template': 'classic', 'accent': '#292929', 'design': {'ats': True, 'font': 'sans', 'header': 'left', 'skills': 'inline', 'size': 'compact', 'spacing': 'compact', 'page': 'one'}}
    elif 'achievement' in lower or 'award' in lower or 'accomplishment' in lower:
        value = re.sub(r'\b(?:add|include|put|in|my|the|section|achievement|achievements|award|awards|accomplishment|accomplishments)\b', ' ', text, flags=re.I)
        value = re.sub(r'\s+', ' ', value).strip(' .,:;-') or text
        current = state['profile'].get('achievements', '').strip()
        patch = {'profile_patch': {'achievements': value if current.casefold() in ('', 'none', 'no', 'n/a') else current + '\n\n' + value}}
    elif re.search(r'\b(?:skill|skills)\b', lower):
        match = re.search(r'(?:add|include|use)\s+(.+?)(?:\s+in\s+(?:my\s+)?skills?|\s+as\s+a\s+skill|$)', text, flags=re.I)
        value = match.group(1) if match else re.sub(r'.*?\bskills?\b', '', text, flags=re.I)
        skills = [s.strip(' .,:;-') for s in re.split(r'[,;\n]|\band\b', value, flags=re.I) if s.strip(' .,:;-')]
        if skills:
            patch = {'add_skills': skills}
    elif 'summary' in lower:
        ids = list(cv.facts(state['confirmed_profile']))[:3]
        if ids:
            patch = {'summary_fact_ids': ids}
    elif re.search(r'\b(?:large|bigger)\s+(?:font|text)|font\s+(?:large|bigger)|increase\s+(?:font|text)', lower):
        patch = {'design': {'font': 'sans', 'size': 'large'}}
    elif 'compact' in lower:
        patch = {'design': {'size': 'compact', 'spacing': 'compact'}}
    return {'type': 'tool_call', 'tool': 'update_cv', 'arguments': {'patch': patch}} if patch else None


def run_cv_turn(state, message, model, save, max_steps=6):
    """Run the dedicated CV Studio chat against the current confirmed draft."""
    if not isinstance(message, str) or not 1 <= len(message.strip()) <= 12000:
        raise ValueError('Enter a message up to 12000 characters.')
    require_confirmed(state)
    cv.validate_draft(state)
    if state.get('pending_cv'):
        raise ValueError('Accept or dismiss your current CV suggestion first.')
    state.setdefault('cv_messages', []).append({'role': 'user', 'content': message.strip()})
    state['cv_trace'] = []
    state['cv_stop_reason'] = None
    save(state)
    seen = set()
    messages = [{'role': 'system', 'content': CV_CHAT_SYSTEM}] + state['cv_messages'][-24:]
    for step in range(1, max_steps + 1):
        context = {'profile': state['confirmed_profile'], 'draft': state['draft'],
                   'revision': state['revision'], 'prompt_version': CV_CHAT_VERSION,
                   'confirmed_facts': cv.facts(state['confirmed_profile'])}
        try:
            action = json.loads(model.decide(messages, context))
            if not isinstance(action, dict):
                raise ValueError('Expected an object action.')
        except GeminiError as error:
            local = local_cv_action(state, message)
            if local is not None:
                action = local
                state['cv_trace'].append({'step': step, 'fallback': 'local_editor', 'error': str(error), 'executed': True})
            else:
                state['cv_stop_reason'] = 'provider_error'
                state['cv_trace'].append({'step': step, 'error': str(error), 'executed': False})
                state['cv_messages'].append({'role': 'assistant', 'content': 'Gemini is temporarily unavailable. I could not safely interpret that request; your current draft is unchanged.'})
                save(state)
                raise
        except ValueError as error:
            state['cv_stop_reason'] = 'provider_error'
            state['cv_trace'].append({'step': step, 'error': str(error), 'executed': False})
            state['cv_messages'].append({'role': 'assistant', 'content': 'Gemini could not complete that edit. Your current draft is unchanged.'})
            save(state)
            raise
        if 'type' not in action and isinstance(action.get('tool'), str) and isinstance(action.get('arguments'), dict):
            action['type'] = 'tool_call'
        if action.get('type') == 'final_answer' and isinstance(action.get('answer'), str) and action['answer'].strip():
            state['cv_messages'].append({'role': 'assistant', 'content': action['answer'].strip()})
            state['cv_stop_reason'] = 'final_answer'
            state.setdefault('audit_runs', []).append(dict(at=datetime.now(timezone.utc).isoformat(), message=message,
                prompt_version=CV_CHAT_VERSION, model=model.name, trace=deepcopy(state['cv_trace']), stop_reason=state['cv_stop_reason']))
            save(state)
            return state
        if action.get('tool') == 'update_cv' and action.get('arguments') == {}:
            state['cv_trace'].append({'step':step,'action':action,'executed':False,'observation':{'error':'Empty edit rejected; requesting a concrete patch.'}})
            messages.extend([{'role':'assistant','content':json.dumps(action)},
                {'role':'user','content':'Your edit was NOT executed: arguments must include patch. Example: {"type":"tool_call","tool":"update_cv","arguments":{"patch":{"design":{"size":"large"}}}}. For summaries use summary_fact_ids from confirmed_facts. Return a valid patch or explain why no edit is needed.'}])
            continue
        key = json.dumps(action, sort_keys=True)
        if key in seen:
            state['cv_stop_reason'] = 'repeated_action'
            state['cv_trace'].append({'step': step, 'action': action, 'executed': False, 'observation': {'error': 'Repeated action blocked'}})
            break
        seen.add(key)
        before = state['revision']
        executed = False
        if action.get('type') == 'tool_call' and action.get('tool') == 'get_draft' and action.get('arguments') == {}:
            observation = {'draft': state['draft'], 'confirmed_facts': cv.facts(state['confirmed_profile'])}
            executed = True
        elif action.get('type') == 'tool_call' and action.get('tool') == 'update_cv' and isinstance(action.get('arguments'), dict) and set(action['arguments']) == {'patch'}:
            try:
                candidate = deepcopy(state)
                patch = deepcopy(action['arguments']['patch'])
                profile_patch = patch.pop('profile_patch', {})
                if not isinstance(profile_patch, dict) or set(profile_patch) - {'name','email','phone','location','linkedin','github','portfolio','education','skills','projects','experience','achievements','goal','summary_facts'}:
                    raise ValueError('Profile changes contain an unsupported field.')
                # Gemini sometimes echoes the whole profile when asked for one
                # skill (for example, it returned every related skill for
                # “add Docker”). Treat additions as a delta: retain the
                # confirmed list and keep only names explicitly present in the
                # user's message. A replacement request remains supported.
                current_skills = list(candidate['profile'].get('skills', []))
                proposed_skills = profile_patch.get('skills', []) if isinstance(profile_patch.get('skills', []), list) else []
                proposed_additions = patch.get('add_skills', []) if isinstance(patch.get('add_skills', []), list) else []
                skill_addition = _skill_addition_requested(message, [*proposed_skills, *proposed_additions])
                requested_fields = _requested_profile_fields(message)
                if skill_addition:
                    requested_fields.add('skills')
                profile_patch = {key: value for key, value in profile_patch.items()
                                 if key in requested_fields}
                skill_only = skill_addition and requested_fields == {'skills'}
                if skill_only:
                    # Ignore model-proposed summary, project, section and design
                    # rewrites. The only valid delta is the named skill.
                    patch = {key: value for key, value in patch.items()
                             if key == 'add_skills'}
                if 'skills' in profile_patch and skill_addition:
                    explicit = [skill for skill in proposed_skills
                                if _skill_is_named_in_message(skill, message)
                                and skill.casefold() not in {s.casefold() for s in current_skills}]
                    profile_patch['skills'] = _unique_skill_names([*current_skills, *explicit])
                elif 'skills' in profile_patch and not _skill_replacement_requested(message):
                    # Do not let an unrelated request import model/context
                    # skills into the profile.
                    profile_patch.pop('skills', None)
                new_projects = patch.pop('add_projects', None)
                adding_project = bool(re.search(r'\b(?:add|append|include|another|new)\b', message, re.I) and re.search(r'\bprojects?\b', message, re.I))
                if new_projects is not None:
                    if 'projects' in profile_patch:
                        raise ValueError('Use add_projects alone for project additions.')
                    profile_patch['projects'] = merge_added_projects(candidate['profile']['projects'], new_projects)
                elif adding_project and 'projects' in profile_patch:
                    profile_patch['projects'] = merge_added_projects(candidate['profile']['projects'], profile_patch['projects'])
                if profile_patch:
                    previous_profile = deepcopy(candidate['profile'])
                    previous_order = list(candidate['draft']['selection'].get('project_order', []))
                    previous_selected_skills = list(candidate['draft']['selection'].get('skills', []))
                    profile = {**candidate['profile'], **profile_patch}
                    validate_profile(profile)
                    candidate['profile'] = deepcopy(profile)
                    candidate['confirmed_profile'] = deepcopy(profile)
                    candidate['draft']['profile'] = deepcopy(profile)
                    candidate['draft']['analysis'] = cv.match_analysis(profile, candidate['draft']['job'])
                    candidate['draft']['selection']['project_order'] = [
                        index for index in previous_order if 0 <= index < len(profile['projects'])]
                    if adding_project and len(profile['projects']) > len(previous_profile['projects']):
                        candidate['draft']['selection']['project_order'] += list(
                            range(len(previous_profile['projects']), len(profile['projects'])))
                    allowed_skills = {skill.casefold(): skill for skill in profile['skills']}
                    selected_skills = [allowed_skills[skill.casefold()]
                                       for skill in previous_selected_skills
                                       if skill.casefold() in allowed_skills]
                    if skill_addition:
                        selected_skills += [skill for skill in profile['skills']
                                            if _skill_is_named_in_message(skill, message)]
                    candidate['draft']['selection']['skills'] = _unique_skill_names(selected_skills)
                    if 'achievements' in profile_patch or 'experience' in profile_patch:
                        visible = [s for s in candidate['draft'].get('design', {}).get('visible_sections', cv.SECTIONS) if s in cv.SECTIONS]
                        for section in ('experience', 'achievements'):
                            if section in profile_patch and profile[section].strip().casefold() not in ('', 'none', 'no', 'n/a'):
                                if section not in candidate['draft']['selection']['section_order']:
                                    candidate['draft']['selection']['section_order'].append(section)
                                if section not in visible:
                                    visible.append(section)
                        candidate['draft'].setdefault('design', {})['visible_sections'] = visible
                    patch['skills'] = candidate['draft']['selection']['skills']
                    patch['project_order'] = candidate['draft']['selection']['project_order']
                    try:
                        patch['summary_fact_ids'] = cv.summary_sources(candidate['draft']['summary'], cv.facts(profile))
                    except ValueError:
                        ids = list(cv.facts(profile))[:3]
                        patch['summary_fact_ids'] = ids
                additions = patch.pop('add_skills', [])
                if skill_addition:
                    additions = [skill for skill in additions if _skill_is_named_in_message(skill, message)]
                else:
                    # An add_skills tool argument is only valid when the user
                    # actually asked to add a skill; ignore model hallucinated
                    # catalog expansions on other edits.
                    additions = []
                summary = patch.pop('summary_text', None)
                if not isinstance(additions, list) or any(not isinstance(s, str) or not s.strip() or len(s) > 100 for s in additions):
                    raise ValueError('New skills must be a list of short names.')
                if summary is not None and (not isinstance(summary, str) or not summary.strip() or len(summary) > 4000):
                    raise ValueError('Summary must be non-empty text up to 4000 characters.')
                if additions or summary is not None:
                    profile = candidate['profile']
                    for skill in additions:
                        if skill.strip().lower() not in [s.lower() for s in profile['skills']]:
                            profile['skills'].append(skill.strip())
                    if summary is not None:
                        summary = summary.strip()
                        if summary not in profile['summary_facts']:
                            profile['summary_facts'].append(summary)
                        patch['summary_fact_ids'] = ['summary:' + str(profile['summary_facts'].index(summary))]
                    candidate['confirmed_profile'] = deepcopy(profile)
                    candidate['draft']['profile'] = deepcopy(profile)
                    candidate['draft']['analysis'] = cv.match_analysis(profile, candidate['draft']['job'])
                    patch['skills'] = list(dict.fromkeys(patch.get('skills', candidate['draft']['selection']['skills']) + [s.strip() for s in additions]))
                if re.search(r'ats[ -]?(?:friendly|ready)', message, re.I) and not re.search(r'\b(?:not|disable|remove)\b', message, re.I):
                    patch = {**patch, 'template':'classic','accent':'#292929',
                        'design':{**patch.get('design', {}),'ats':True,'font':'sans','header':'left','skills':'inline','size':'compact','spacing':'compact','page':'one'}}
                observation = _apply_cv_patch(candidate, patch)
                import uuid
                state['pending_cv'] = {'id':uuid.uuid4().hex,'base':deepcopy(state['draft']),
                    'draft':candidate['draft'],'source':message,'base_profile':deepcopy(state['profile']),
                    'profile':deepcopy(candidate['profile'])}
                observation = {'updated':observation['updated'],'pending_review':True,'draft_unchanged':True}
                executed = True
            except (ValueError, KeyError, TypeError) as error:
                observation = {'error': str(error)}
        else:
            observation = {'error': 'Expected get_draft, update_cv, or final_answer.'}
        state['cv_trace'].append({'step': step, 'action': action, 'observation': observation, 'executed': executed,
                                  'revision_before': before, 'revision_after': state['revision']})
        if executed and action.get('tool') == 'update_cv':
            state['cv_messages'].append({'role':'assistant', 'content':'Here are my suggested CV changes. Review them below, then accept or dismiss. Your CV has not changed yet.'})
            state['cv_stop_reason'] = 'pending_review'
            save(state)
            return state
        save(state)
        messages.extend([{'role': 'assistant', 'content': json.dumps(action)},
                         {'role': 'user', 'content': 'Python CV tool observation: ' + json.dumps(observation)}])
    state['cv_stop_reason'] = state['cv_stop_reason'] or 'step_limit'
    state['cv_messages'].append({'role': 'assistant', 'content': 'I stopped before making another change. Review the CV tool activity and tell me what you want next.'})
    save(state)
    return state

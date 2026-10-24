"""Application operations, independent of HTTP and the React interface."""
import json
from copy import deepcopy
from pathlib import Path
from .store import Store, update_profile, require_confirmed, missing_fields
from .gemini import GeminiFallbackModel, GeminiSettings
from .retrieval import JobRetriever, SentenceTransformerBackend
from .agent import run_turn, run_cv_turn, run_followup_turn
from . import cv

ROOT = Path(__file__).resolve().parents[1]


def refresh_existing_draft(state):
    """Rebind a tailored draft to the newly confirmed profile without changing its job."""
    if not state.get('draft') or not state.get('confirmed_profile'):
        return
    draft = deepcopy(state['draft'])
    old_profile = deepcopy(draft.get('profile') or state['confirmed_profile'])
    profile = state['confirmed_profile']
    draft['profile'] = deepcopy(profile)
    draft['revision'] = state['revision']
    selection = draft.setdefault('selection', {})
    old_projects = old_profile.get('projects', [])
    current_projects = profile['projects']
    selected_titles = {
        old_projects[index]['title'].strip().casefold()
        for index in selection.get('project_order', [])
        if isinstance(index, int) and 0 <= index < len(old_projects)}
    old_titles = {project['title'].strip().casefold() for project in old_projects}
    selection['project_order'] = [
        index for index, project in enumerate(current_projects)
        if project['title'].strip().casefold() in selected_titles]
    # Append only genuinely new projects. Existing projects deliberately omitted
    # by this job-specific CV stay omitted.
    selection['project_order'] += [
        index for index, project in enumerate(current_projects)
        if project['title'].strip().casefold() not in old_titles]
    if not selection['project_order'] and current_projects:
        selection['project_order'] = [0]
    old_skill_names = {skill.casefold() for skill in old_profile.get('skills', [])}
    current_skill_names = {skill.casefold(): skill for skill in profile['skills']}
    retained = [current_skill_names[skill.casefold()] for skill in selection.get('skills', [])
                if skill.casefold() in current_skill_names]
    additions = [skill for skill in profile['skills'] if skill.casefold() not in old_skill_names]
    selection['skills'] = list(dict.fromkeys(retained + additions))
    try:
        selection['summary_fact_ids'] = cv.summary_sources(draft.get('summary', ''), cv.facts(profile))
    except ValueError:
        ids = list(cv.facts(profile))[:3]
        selection['summary_fact_ids'] = ids
        draft['summary'] = '\n\n'.join(cv.facts(profile)[i] for i in ids)
    needed = {'projects', 'education'}
    if profile['experience'].strip().lower() not in ('', 'none', 'no', 'n/a'): needed.add('experience')
    if profile['achievements'].strip().lower() not in ('', 'none', 'no', 'n/a'): needed.add('achievements')
    sections = [s for s in selection.get('section_order', cv.SECTIONS) if s in needed]
    selection['section_order'] = sections + [s for s in cv.SECTIONS if s in needed and s not in sections]
    draft.setdefault('design', {})['visible_sections'] = selection['section_order'][:]
    draft['analysis'] = cv.match_analysis(profile, draft['job'])
    candidate = {'draft': draft, 'confirmed_profile': profile, 'confirmed_revision': state['revision'], 'revision': state['revision']}
    try:
        cv.validate_draft(candidate)
    except ValueError:
        return
    state['draft'] = draft


def restore_with_current_profile(state, saved_draft):
    """Restore a saved CV while rebinding it to the latest confirmed profile."""
    profile = state['confirmed_profile']
    draft = deepcopy(saved_draft)
    old_profile = draft.get('profile') if isinstance(draft.get('profile'), dict) else profile
    selection = draft.setdefault('selection', {})

    # Project indexes belong to the saved profile. Remap them by project title
    # before appending projects that were added after the version was saved.
    old_projects = old_profile.get('projects', [])
    current_projects = profile['projects']
    unused = set(range(len(current_projects)))
    project_order = []
    for old_index in selection.get('project_order', []):
        if type(old_index) is not int or not 0 <= old_index < len(old_projects):
            continue
        old_project = old_projects[old_index]
        match = next((index for index in unused
                      if current_projects[index]['title'].strip().casefold() == old_project['title'].strip().casefold()), None)
        if match is None:
            match = next((index for index in unused
                          if current_projects[index]['description'].strip() == old_project['description'].strip()), None)
        if match is not None:
            project_order.append(match)
            unused.remove(match)
    old_titles = {project['title'].strip().casefold() for project in old_projects}
    genuinely_new = [index for index in sorted(unused)
                     if current_projects[index]['title'].strip().casefold() not in old_titles]
    selection['project_order'] = project_order + genuinely_new
    if not selection['project_order'] and current_projects:
        selection['project_order'] = [0]

    # Keep the saved role-specific skill selection and include skills confirmed
    # since that version was created. Never restore removed/unconfirmed skills.
    current_skill_names = {skill.casefold(): skill for skill in profile['skills']}
    old_skill_names = {skill.casefold() for skill in old_profile.get('skills', [])}
    restored_skills = [current_skill_names[skill.casefold()] for skill in selection.get('skills', [])
                       if isinstance(skill, str) and skill.casefold() in current_skill_names]
    restored_skills += [skill for skill in profile['skills'] if skill.casefold() not in old_skill_names]
    selection['skills'] = list(dict.fromkeys(restored_skills))

    needed = {'projects', 'education'} | {section for section in ('experience', 'achievements')
        if profile[section].strip().casefold() not in ('', 'none', 'no', 'n/a')}
    saved_sections = [section for section in selection.get('section_order', cv.SECTIONS)
                      if section in needed]
    selection['section_order'] = saved_sections + [section for section in cv.SECTIONS
                                                    if section in needed and section not in saved_sections]

    draft['profile'] = deepcopy(profile)
    draft['revision'] = state['revision']
    draft['analysis'] = cv.match_analysis(profile, draft['job'])

    # Preserve the saved summary when its exact evidence still exists. If a
    # source fact changed, map identical old facts to their current IDs and use
    # current education as a safe final fallback.
    current_catalog = cv.facts(profile)
    try:
        summary_ids = cv.summary_sources(draft.get('summary', ''), current_catalog)
    except ValueError:
        old_catalog = cv.facts(old_profile)
        summary_ids = []
        for old_id in selection.get('summary_fact_ids', []):
            value = old_catalog.get(old_id)
            current_id = next((key for key, current in current_catalog.items()
                               if current.strip() == str(value or '').strip() and key not in summary_ids), None)
            if current_id:
                summary_ids.append(current_id)
        if not summary_ids:
            summary_ids = ['education']
        draft['summary'] = '\n\n'.join(current_catalog[key] for key in summary_ids)
    selection['summary_fact_ids'] = summary_ids

    design = draft.setdefault('design', {})
    visible = [section for section in design.get('visible_sections', selection['section_order'])
               if section in needed]
    design['visible_sections'] = visible + [section for section in selection['section_order']
                                            if section not in visible]
    draft['selection'] = selection
    draft['suggested_order'] = {'project_order': selection['project_order'][:],
                                'section_order': selection['section_order'][:]}
    draft['suggestion_note'] = 'Restored this saved version and refreshed it with your current confirmed profile.'
    draft.pop('project_excerpts', None)
    return draft


class Service:
    def __init__(self, store=None, model=None, retriever=None):
        self.store = store or Store(ROOT / 'runtime' / 'proofcv.sqlite3')
        self.model = model or GeminiFallbackModel(GeminiSettings.load())
        self.jobs = [json.loads(line) for line in (ROOT / 'data' / 'jobs.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
        assert len(self.jobs) == 9 and len({j['document_id'] for j in self.jobs}) == 9
        self.retriever = retriever or JobRetriever(self.jobs, SentenceTransformerBackend('sentence-transformers/all-MiniLM-L6-v2'))

    def retrieve(self, profile):
        canonical = dict(target_roles=[profile['goal']], technical_skills=profile['skills'],
                         education=[profile['education']], experience=[profile['experience']],
                         projects=profile['projects'], achievements=[profile['achievements']],
                         skill_evidence=profile['summary_facts'])
        return self.retriever.search(canonical)

    def action(self, workspace_id, operation, data):
        if operation.startswith('portfolio-'):
            return self.portfolio.action(workspace_id, operation, data)
        with self.store.lock:
            if operation == 'restore-workspace':
                return self.store.restore_workspace(workspace_id)
            if operation == 'remove-workspace':
                if data.get('accepted') is not True:
                    raise ValueError('Confirm workspace removal first.')
                return self.store.move_to_trash(workspace_id, data.get('revision'))
            if operation == 'purge-removed-workspaces':
                if workspace_id != 'trash' or data.get('accepted') is not True:
                    raise ValueError('Explicit permanent-deletion confirmation is required.')
                return self.store.purge_trash()
            state = self.store.get(workspace_id)
            state.setdefault('cv_messages', [])
            state.setdefault('cv_trace', [])
            state.setdefault('cv_stop_reason', None)
            if data.get('revision') != state['revision']:
                raise ValueError('The profile changed in another request. Reload before continuing.')
            if operation == 'profile':
                was_confirmed = state.get('confirmed_profile') is not None and state.get('confirmed_revision') == state.get('revision')
                before_profile = deepcopy(state['profile'])
                update_profile(state, data['patch'])
                state.pop('pending_profile', None)
                full_profile_update = isinstance(data.get('patch'), dict) and {'name','email','phone','education','skills','projects','experience','achievements','goal','summary_facts'}.issubset(data['patch'])
                if (data.get('auto_confirm') is True or full_profile_update) and was_confirmed and state['profile'] != before_profile:
                    state['confirmed_profile'] = deepcopy(state['profile'])
                    state['confirmed_revision'] = state['revision']
                    refresh_existing_draft(state)
            elif operation == 'undo-profile':
                previous = state.get('profile_undo')
                if previous is None:
                    raise ValueError('No saved profile change to undo.')
                restored = {key: previous.get(key, '') for key in state['profile']}
                update_profile(state, restored)
                state.pop('pending_profile', None)
            elif operation == 'review-profile':
                proposal = state.get('pending_profile')
                if not proposal or proposal['id'] != data.get('proposal_id') or proposal['revision'] != state['revision']:
                    raise ValueError('This proposal is outdated. Ask the agent for an updated suggestion.')
                choice = data.get('choice')
                if choice == 'accept':
                    patch = data.get('patch', proposal['patch'])
                    if not isinstance(patch, dict) or set(patch) - set(proposal['patch']) - {'skills'} or set(proposal['patch']) - set(patch):
                        raise ValueError('Edit only the proposed fields.')
                    if 'skills' in patch:
                        skills = patch['skills']
                        if not isinstance(skills, list) or any(not isinstance(s, str) for s in skills):
                            raise ValueError('Selected skills must be text.')
                        # Checkbox additions preserve existing skills and ignore casing/whitespace duplicates.
                        skills = ([*state['profile']['skills'], *skills] if 'skills' not in proposal['patch'] else skills)
                        unique = {}
                        for skill in skills:
                            if skill.strip():
                                unique.setdefault(skill.strip().casefold(), skill.strip())
                        patch = {**patch, 'skills': list(unique.values())}
                    local = data.get('local_profile')
                    if local is not None:
                        from .store import validate_profile
                        validate_profile(local)
                        # Explicit Accept applies the reviewed fields over the locally edited form.
                        patch = {**local, **patch}
                    project_skills = data.get('project_skills')
                    if project_skills is not None:
                        if not isinstance(project_skills, dict) or set(project_skills) != {'project_index', 'skills'}:
                            raise ValueError('Choose a project and the skills you used there.')
                        index, selected = project_skills['project_index'], project_skills['skills']
                        projects = deepcopy(patch.get('projects', state['profile']['projects']))
                        if type(index) is not int or not 0 <= index < len(projects):
                            raise ValueError('The selected project is no longer available.')
                        if not isinstance(selected, list) or not selected or any(not isinstance(s, str) or s not in proposal.get('skill_options', []) for s in selected):
                            raise ValueError('Select skills from this review’s suggestions.')
                        import re
                        def unique_terms(values):
                            result = {}
                            for value in values:
                                if value.strip():
                                    result.setdefault(value.strip().casefold(), value.strip())
                            return list(result.values())
                        projects[index]['technologies'] = ', '.join(unique_terms(re.split(r'[,;\n]', projects[index]['technologies']) + selected))
                        patch = {**patch, 'projects': projects,
                                 'skills': unique_terms(patch.get('skills', state['profile']['skills']) + selected)}
                    update_profile(state, patch)
                elif choice != 'dismiss':
                    raise ValueError('Choose accept or dismiss.')
                else:
                    state['messages'].append({'role': 'assistant', 'content': 'Proposal dismissed. Your profile is unchanged.'})
                state.setdefault('profile_reviews', []).append({'proposal': proposal, 'choice': choice, 'accepted_patch': patch if choice == 'accept' else None})
                state.pop('pending_profile', None)
                if choice == 'accept':
                    # Persist the accepted human decision before the provider call.
                    # Gemini then chooses the next follow-up Action from updated state;
                    # Python validates that it targets the first missing field.
                    self.store.save(state)
                    return run_followup_turn(state, self.model, self.store.save)
            elif operation == 'confirm':
                if state.get('pending_profile'):
                    raise ValueError('Accept or dismiss your pending profile proposal first.')
                if data.get('accepted') is not True:
                    raise ValueError('Explicit profile acceptance is required.')
                missing = missing_fields(state['profile'])
                if missing:
                    raise ValueError('Complete: ' + ', '.join(missing))
                state['confirmed_profile'] = deepcopy(state['profile'])
                state['confirmed_revision'] = state['revision']
                refresh_existing_draft(state)
            elif operation == 'find-jobs':
                require_confirmed(state)
                if state.get('pending_profile'):
                    raise ValueError('Accept or dismiss the current profile proposal first.')
                # The visible "Ask agent" action must be a real model decision.
                # Gemini sees the confirmed state, chooses retrieve_jobs, and the
                # bounded Python loop validates and executes that tool call.
                return run_turn(
                    state,
                    'Find and return the three most relevant supplied jobs for my confirmed profile.',
                    self.model,
                    self.retrieve,
                    self.store.save,
                    require_review=True,
                )
            elif operation == 'chat':
                if state.get('pending_profile'):
                    raise ValueError('Accept, edit or dismiss the current proposal before sending another message.')
                return run_turn(state, data['message'], self.model, self.retrieve, self.store.save, require_review=True)
            elif operation == 'upload-document':
                from .documents import propose_document
                if state.get('pending_profile'):
                    raise ValueError('Accept or dismiss the current suggestion before uploading another document.')
                propose_document(state, data, self.model)
            elif operation == 'cv-chat':
                if state.get('pending_cv'):
                    raise ValueError('Accept or dismiss the CV suggestion first.')
                if 'draft_patch' in data:
                    cv.edit(state, data['draft_patch'])
                    self.store.save(state)
                if state.get('pending_profile'):
                    raise ValueError('Accept, edit or dismiss the current profile proposal before editing your CV.')
                return run_cv_turn(state, data['message'], self.model, self.store.save)
            elif operation == 'review-cv':
                pending = state.get('pending_cv')
                if not pending or pending['id'] != data.get('proposal_id'):
                    raise ValueError('This CV suggestion is no longer available.')
                if data.get('choice') == 'accept':
                    if state['draft'] != pending['base']:
                        raise ValueError('Your CV changed since this suggestion. Dismiss it and request a new suggestion.')
                    candidate = deepcopy(state)
                    candidate['draft'] = deepcopy(pending['draft'])
                    if pending.get('profile', state['profile']) != state['profile']:
                        if state['profile'] != pending.get('base_profile'):
                            raise ValueError('Your profile changed. Dismiss this suggestion and request a new one.')
                        candidate['profile'] = deepcopy(pending['profile'])
                        candidate['confirmed_profile'] = deepcopy(pending['profile'])
                        candidate['revision'] += 1
                        candidate['confirmed_revision'] = candidate['revision']
                        candidate['draft']['revision'] = candidate['revision']
                    cv.validate_draft(candidate)
                    if candidate['revision'] != state['revision']:
                        state['profile_undo'] = deepcopy(state['profile'])
                        for key in ('profile','confirmed_profile','revision','confirmed_revision'):
                            state[key] = candidate[key]
                        state['retrieval'] = None
                    state['undo'] = deepcopy(state['draft'])
                    state['draft'] = candidate['draft']
                    state['cv_messages'].append({'role':'assistant','content':'Your approved changes are now in the CV preview.'})
                elif data.get('choice') == 'dismiss':
                    state['cv_messages'].append({'role':'assistant','content':'Suggestion dismissed. Your CV is unchanged.'})
                else:
                    raise ValueError('Choose accept or dismiss.')
                state.pop('pending_cv', None)
            elif operation == 'retrieve':
                require_confirmed(state)
                state['retrieval'] = self.retrieve(state['confirmed_profile'])
            elif operation == 'generate':
                if state.get('pending_profile'):
                    raise ValueError('Review the proposed profile changes before generating a CV.')
                if not state['retrieval'] or data.get('job_id') not in [j['document_id'] for j in state['retrieval']['results']]:
                    raise ValueError('Select one of your three retrieved jobs first.')
                job = next(j for j in self.jobs if j['document_id'] == data['job_id'])
                cv.generate(state, job, self.model)
            elif operation == 'edit':
                cv.edit(state, data['patch'])
            elif operation == 'save':
                cv.validate_draft(state)
                cv.save_version(state)
            elif operation == 'restore':
                version = next((v for v in state['versions'] if v['id'] == data.get('version_id')), None)
                if not version:
                    raise ValueError('Version not found in this workspace.')
                candidate = deepcopy(state)
                candidate['draft'] = restore_with_current_profile(candidate, version['draft'])
                cv.validate_draft(candidate)
                state['undo'] = state['draft']
                state['draft'] = candidate['draft']
                state.setdefault('cv_messages', []).append({'role': 'assistant',
                    'content': 'Restored the saved CV and refreshed it with your current confirmed profile. The target job is unchanged.'})
            elif operation == 'undo':
                if not state['undo']:
                    raise ValueError('No edit to undo.')
                state['draft'], state['undo'] = state['undo'], state['draft']
                cv.validate_draft(state)
            elif operation == 'suggestion':
                cv.validate_draft(state)
                choice = data.get('choice')
                if choice not in ('accepted', 'dismissed'):
                    raise ValueError('Choose accept or dismiss.')
                state['undo'] = deepcopy(state['draft'])
                if choice == 'accepted':
                    proposed = state['draft'].get('suggested_order')
                    changes = []
                    if proposed:
                        if proposed.get('project_order') != state['draft']['selection'].get('project_order'):
                            changes.append('project order')
                        if proposed.get('section_order') != state['draft']['selection'].get('section_order'):
                            changes.append('section order')
                        state['draft']['selection'].update(deepcopy(proposed))
                    state['draft']['suggestion_status'] = 'accepted'
                    state['draft']['suggestion_note'] = ('Applied ' + ' and '.join(changes) + ' to this draft.' if changes else 'Accepted. The suggested order already matched this draft, so no content was rewritten.')
                else:
                    # Dismiss only the proposed emphasis/order. Keep the generated
                    # job-specific evidence subset instead of expanding the CV back
                    # to every confirmed project and skill.
                    selected_projects = state['draft']['selection'].get('project_order', [])
                    state['draft']['selection']['project_order'] = sorted(selected_projects)
                    selected_sections = set(state['draft']['selection'].get('section_order', []))
                    state['draft']['selection']['section_order'] = [
                        section for section in cv.SECTIONS if section in selected_sections]
                    state.setdefault('draft', {}).setdefault('design', {})['visible_sections'] = (
                        state['draft']['selection']['section_order'][:])
                    state['draft']['suggestion_status'] = 'dismissed'
                    state['draft']['suggestion_note'] = (
                        'Dismissed. Source ordering is restored within the selected '
                        'job-relevant evidence; omitted profile evidence remains omitted.')
            else:
                raise ValueError('Unknown operation.')
            self.store.save(state)
            return state

    @property
    def portfolio(self):
        from .portfolio import PortfolioService
        with self.store.lock:
            if not hasattr(self, '_portfolio'):
                self._portfolio = PortfolioService(self.store, self.model, self.jobs)
            return self._portfolio

"""Create the detailed fictional labelled sample used for tutor demonstration."""
import json
from copy import deepcopy
from pathlib import Path

from .store import Store, validate_profile
from . import cv

LABEL = 'Avery Morgan — labelled fictional sample'
LEGACY_LABEL = 'Alex Morgan — labelled fictional sample'


class CuratedSelection:
    name = 'manual:labelled-sample (not a Gemini run)'

    def __init__(self, selection):
        self.selection = selection

    def decide(self, messages, context):
        return json.dumps(self.selection)


def _profile():
    return dict(
        name='Avery Morgan', email='avery.morgan@example.test', phone='0400 000 010',
        location='Sydney, NSW', linkedin='linkedin.example.test/in/avery-morgan',
        github='github.example.test/avery-morgan', portfolio='avery-morgan.example.test',
        education=(
            'Advanced Diploma of Information Technology (Artificial Intelligence) | Harbour Technical College | February 2024 - November 2026\n\n'
            'Certificate IV in Information Technology (Programming) | City Skills Institute | February 2023 - December 2023'),
        goal='Junior Computer Vision Engineer; Graduate Machine Learning Engineer',
        skills=['Python', 'OpenCV', 'PyTorch', 'NumPy', 'pandas', 'scikit-learn',
                'Machine Learning', 'Computer Vision', 'YOLO', 'Object Detection',
                'Image Classification', 'Data Annotation', 'Model Evaluation', 'Git',
                'Docker', 'FastAPI', 'SQL', 'Jupyter Notebook'],
        projects=[
            dict(title='Smart Intersection Object Detection', description=(
                'Built a coursework computer-vision prototype that detects vehicles, cyclists and pedestrians in recorded intersection footage. '
                'Curated and labelled a small image dataset, trained a lightweight YOLO model, and compared precision, recall and mAP across experiments. '
                'Reviewed false positives and missed detections, then documented limitations caused by low light, occlusion and the deliberately small training set. '
                'The result is an offline demonstration, not a deployed traffic system.'), technologies='Python, PyTorch, OpenCV, YOLO, NumPy'),
            dict(title='Warehouse Safety Video Analytics', description=(
                'Developed a prototype for analysing recorded warehouse video and highlighting people entering marked safety zones. '
                'Added frame sampling, object tracking, event counts and annotated video output. Measured processing latency on a laptop, reviewed failure cases '
                'with reflective clothing and partial visibility, and produced a concise evaluation report. No real workers or live workplace cameras were used.'),
                technologies='Python, OpenCV, PyTorch, pandas, Model Evaluation'),
            dict(title='Dataset Quality Review Toolkit', description=(
                'Created a local toolkit for checking image dimensions, duplicate filenames, missing annotation files and class imbalance before model training. '
                'Exposed validation through a small FastAPI service, stored review runs in SQL, generated CSV summaries and added automated tests. '
                'Packaged the coursework tool with Docker and documented a repeatable setup workflow for classmates.'),
                technologies='Python, FastAPI, SQL, Docker, Git, pytest')],
        experience=(
            'Computer Vision Lab Assistant | Harbour Technical College Applied Computing Lab | March 2025 - November 2025\n'
            'Prepared and checked annotated training images, reproduced baseline experiments, logged metrics and documented setup steps. '
            'Helped classmates debug data-loading and evaluation scripts under lecturer supervision.\n\n'
            'Customer Technology Assistant | Harbour Electronics | November 2023 - February 2025\n'
            'Explained product features, resolved basic setup issues, recorded recurring customer questions and coordinated escalations during busy periods.'),
        achievements=(
            'Finalist, Harbour Applied AI Showcase (2025) - presented the Smart Intersection prototype and its error analysis.\n'
            'Peer Mentor Recognition (2025) - supported introductory Python and Git workshops.\n'
            'Responsible AI and Data Privacy micro-credential (2025).'),
        summary_facts=[
            'Artificial Intelligence diploma student with hands-on computer-vision coursework in object detection, video analytics and dataset quality. Uses Python, OpenCV and PyTorch to build reproducible prototypes, evaluate model behaviour and communicate limitations.',
            'Graduate machine-learning candidate with experience preparing labelled image data, comparing experiments and building small Python services around model workflows. Brings careful documentation, automated testing and customer-facing communication experience.',
            'Contributed to supervised computing-lab activities by checking annotations, reproducing baseline experiments and helping peers troubleshoot data-loading and evaluation scripts.'])


def seed(store=None):
    root = Path(__file__).resolve().parents[1]
    store = store or Store(root / 'runtime' / 'proofcv.sqlite3')
    workspaces = store.list()
    existing = next((w for w in workspaces if w['label'] == LABEL), None)
    legacy = next((w for w in workspaces if w['label'] == LEGACY_LABEL), None)
    state = store.get((existing or legacy)['id']) if (existing or legacy) else store.create(LABEL)

    profile = _profile()
    validate_profile(profile)
    state.update(label=LABEL, profile=profile, revision=0, confirmed_revision=0,
                 confirmed_profile=deepcopy(profile), messages=[], trace=[], audit_runs=[],
                 retrieval=None, draft=None, versions=[], undo=None, stop_reason=None,
                 cv_messages=[], cv_trace=[], cv_stop_reason=None)
    jobs = {job['document_id']: job for job in map(
        json.loads, (root / 'data/jobs.jsonl').read_text(encoding='utf-8').splitlines())}
    samples = [
        ('graduate_ai_engineer', dict(
            summary_fact_ids=['summary:1', 'summary:2'],
            skills=['Python', 'PyTorch', 'NumPy', 'pandas', 'scikit-learn', 'Machine Learning',
                    'Model Evaluation', 'FastAPI', 'SQL', 'Docker', 'Git'],
            project_order=[2, 0, 1], section_order=['projects', 'experience', 'education', 'achievements'],
            rationale='Highlights general ML workflow, evaluation, API and reproducibility evidence.')),
        ('computer_vision_engineer', dict(
            summary_fact_ids=['summary:0', 'summary:2'],
            skills=['Python', 'OpenCV', 'PyTorch', 'NumPy', 'Computer Vision', 'YOLO',
                    'Object Detection', 'Image Classification', 'Data Annotation', 'Model Evaluation', 'Git', 'Docker'],
            project_order=[0, 1, 2], section_order=['projects', 'experience', 'education', 'achievements'],
            rationale='Prioritises verified object-detection, video-analysis and dataset-quality evidence.'))]

    for job_id, selection in samples:
        cv.generate(state, jobs[job_id], CuratedSelection(selection))
        state['draft']['tailored_content'] = False
        state['draft'].pop('project_excerpts', None)
        state['draft']['suggestion_status'] = 'accepted'
        state['draft']['design'].update(font='sans', size='compact', spacing='compact',
            header='left', skills='inline', page='one', ats=True,
            visible_sections=selection['section_order'][:])
        cv.validate_draft(state)

    cv.save_version(state)
    assert len(state['versions']) == 2
    assert state['versions'][0]['draft']['profile'] == state['versions'][1]['draft']['profile']
    assert {v['draft']['job']['document_id'] for v in state['versions']} == {'graduate_ai_engineer', 'computer_vision_engineer'}
    state['messages'] = [{'role': 'assistant', 'content': (
        'Labelled fictional sample. Every Avery Morgan detail is invented for demonstration. '
        'The profile is deliberately complete so the full workflow can be assessed.')}]
    state['cv_messages'] = [{'role': 'assistant', 'content': (
        'This fictional profile has two saved CVs: Graduate AI Engineer and Computer Vision Engineer. '
        'Open Versions & comparison to inspect or restore either. Both use exactly the same confirmed profile, '
        'while their summaries, selected skills and project priorities differ.')}]
    store.save(state)
    return state['id']


if __name__ == '__main__':
    print(seed())

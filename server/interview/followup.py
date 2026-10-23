"""Follow-up questions: what an interviewer would ask next, chosen by rules from the analysis.

Priority follows how interviewers probe: first details the profile cannot back
up, then missing parts of the answer, then (for a strong answer) a deeper
question. At most MAX_DEPTH follow-ups per question.
"""
from .model_answer import lower_first

MAX_DEPTH = 2
FOLLOW_UP_SECONDS = 45
DEEPER = {
    'behavioural': 'What would you do differently if you faced that situation again?',
    'technical': 'What are the limitations or trade-offs of that approach?',
    'self_introduction': 'What are you hoping to learn in your next role?',
    'motivation_fit': 'What would you want to achieve in your first three months?',
}


def ask(question, why, kind, key_point=None):
    return {'question': question, 'why': why, 'kind': kind, 'key_point': key_point}


def from_fact_check(fact_check, personal_story):
    for claim in (fact_check or {}).get('claims', []):
        for flag in claim['flags']:
            if flag['type'] == 'tool':
                said = flag.get('said', flag['value'])
                return ask(f'You mentioned {said}. Where did you use it, and what exactly did you do with it?', f'{said} is not in your confirmed profile.', 'evidence')
            if flag['type'] == 'number':
                return ask(f"You said {flag['value']}. How did you measure that, and what was it compared against?", f"{flag['value']} is not in your confirmed profile.", 'evidence')
            if flag['type'] == 'leadership':
                return ask('You said you led others. How many people were involved, and what were you responsible for?', 'Leadership is not shown in your confirmed profile.', 'evidence')
    if personal_story:
        unmatched = [c for c in (fact_check or {}).get('claims', []) if c['status'] == 'unmatched']
        if unmatched:
            text = unmatched[0]['text']
            return ask(f'Tell me more about this: “{text[:90]}{"…" if len(text) > 90 else ""}” What was your exact role?', 'This part could not be matched to your profile.', 'evidence')
    return None


def from_star(star):
    present = star['present']
    notes = ' '.join(star['notes'])
    if not present.get('result'):
        return ask('What was the outcome? Can you put a number on it?', 'Your answer had no clear result.', 'structure')
    if 'no number' in notes:
        return ask('How did you know it worked? Can you put a number on the result?', 'Your result had no number.', 'structure')
    if not present.get('task'):
        return ask('What exactly were you trying to achieve, and why did it matter?', 'Your goal was not clear.', 'structure')
    if not present.get('action') or '"we"' in notes or 'set-up' in notes:
        return ask('What did you personally do, as opposed to the team?', 'Your own actions were not clear.', 'structure')
    if not present.get('situation'):
        return ask('Can you set the scene first: where was this, and what was going on?', 'The context was missing.', 'structure')
    return None


def follow_up(question, response, depth=0):
    """The next question an interviewer would ask after this answer, or None."""
    if depth >= MAX_DEPTH or not response.get('transcript'):
        return None
    personal = question['round'] != 'technical'
    chosen = from_fact_check(response.get('fact_check'), personal)
    if not chosen and response.get('star'):
        chosen = from_star(response['star'])
    if not chosen and response.get('content'):
        missed = [k['text'] for k in response['content']['key_points'] if k['status'] == 'missed']
        if missed:
            chosen = ask(f'You did not mention {lower_first(missed[0]).rstrip(".")}. How does that fit in?', 'A key point was missing.', 'content', key_point=missed[0])
    if not chosen and response['round'] == 'self_introduction' and response['delivery'].get('speaking_seconds', 0) < 0.6 * (response.get('target_seconds') or 0):
        chosen = ask('Can you tell me more about the project you are most proud of?', 'Your introduction was short.', 'detail')
    chosen = chosen or ask(DEEPER.get(question['round'], DEEPER['behavioural']), 'A strong answer, so the interviewer digs deeper.', 'deeper')
    return {**chosen, 'depth': depth + 1}

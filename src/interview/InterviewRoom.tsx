import { useEffect, useState } from 'react';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import AnswerRecorder from './AnswerRecorder';
import { speak } from './speech';
import { Overview, Question, Questions, questionStatus, ROUND_INFO, ROUNDS, targetFor } from './types';
import { Bubble } from './ui';

// Practice tab: questions grouped by round on the left, one interview conversation on the right.
export default function InterviewRoom({ workspaceId, questions, overview, onAnswered, focus }: {
    workspaceId: string; questions: Questions; overview: Overview; onAnswered: () => void; focus?: { id: string } | null }) {
    const [round, setRound] = useState(ROUNDS[0]);
    const [index, setIndex] = useState(0);
    const [readAloud, setReadAloud] = useState(false);
    const list = questions.rounds[round] || [];
    const question: Question | undefined = list[Math.min(index, list.length - 1)];
    useEffect(() => { if (readAloud && question) speak(question.text); }, [round, index, readAloud]);
    useEffect(() => { // Opened from the plan: jump to that question.
        const target = focus && ROUNDS.flatMap(r => (questions.rounds[r] || []).map((q, i) => ({ round: r, index: i, id: q.id }))).find(f => f.id === focus.id);
        if (target) { setRound(target.round); setIndex(target.index); }
    }, [focus]);
    const flat = ROUNDS.flatMap(r => (questions.rounds[r] || []).map((q, i) => ({ round: r, index: i, q })));
    const position = flat.findIndex(f => f.round === round && f.index === index);
    const go = (step: number) => { const next = flat[position + step]; if (next) { setRound(next.round); setIndex(next.index); } };

    return <div className="ic-practice">
        <aside className="ic-qlist" aria-label="Questions">
            {ROUNDS.map(r => {
                const items = questions.rounds[r] || [];
                if (!items.length) return null;
                return <section key={r}>
                    <h4>{ROUND_INFO[r].title}<span>{items.filter(q => overview[q.id]).length}/{items.length}</span></h4>
                    <ol>{items.map((q, i) => <li key={`${q.id}-${i}`}>
                        <button type="button" className={`ic-q ${questionStatus(overview, q.id)} ${r === round && i === index ? 'current' : ''}`} aria-current={r === round && i === index ? 'step' : undefined}
                            onClick={() => { setRound(r); setIndex(i); }}><span className="ic-dot" aria-hidden="true" /><span className="ic-q-text">{q.text}</span></button>
                    </li>)}</ol>
                </section>;
            })}
            <p className="ic-legend"><i className="new" />not practised <i className="work" />needs work <i className="strong" />strong</p>
        </aside>
        {question ? <div className="ic-stage">
            <div className="ic-stage-bar">
                <span>{ROUND_INFO[round].title} · question {index + 1} of {list.length}{question.seconds ? ` · aim for about ${question.seconds} seconds` : ''}</span>
                <label className="ic-switch"><input type="checkbox" checked={readAloud} onChange={e => setReadAloud(e.target.checked)} /><span />Read questions aloud</label>
            </div>
            <div className="ic-thread">
                <Bubble who="interviewer" meta={`Why this question: ${question.reason}`}><span className="ic-question">{question.text}</span></Bubble>
                <AnswerRecorder key={`${round}-${index}`} workspaceId={workspaceId} questionId={question.id} questionText={question.text}
                    jobId={questions.job.document_id} requirementId={question.requirement?.id} onResult={onAnswered} readAloud={readAloud} targetSeconds={targetFor(question)} />
            </div>
            <div className="ic-stage-nav">
                <button type="button" className="button subtle" disabled={position <= 0} onClick={() => go(-1)}><ArrowLeft size={15} />Previous</button>
                <button type="button" className="button dark" disabled={position >= flat.length - 1} onClick={() => go(1)}>Next question<ArrowRight size={15} /></button>
            </div>
        </div> : <p className="coach-method">No questions in this round for this job.</p>}
    </div>;
}

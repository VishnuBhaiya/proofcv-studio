import { useEffect, useState } from 'react';
import { ArrowLeft, ArrowRight, Presentation } from 'lucide-react';
import { api } from '../api';
import AnswerRecorder, { speak } from './AnswerRecorder';
import SlideDeck from './SlideDeck';
import { Question, Questions, ROUND_INFO } from './types';

type Overview = Record<string, { attempts: number; needs_work: string[] }>;
const ROUNDS = ['self_introduction', 'behavioural', 'technical', 'motivation_fit'];
const STATUS_LABEL = { new: 'Not practised yet', work: 'Last attempt needs work', strong: 'Last attempt was strong' };

export default function InterviewRoom({ workspaceId, questions }: { workspaceId: string; questions: Questions }) {
    const [round, setRound] = useState(ROUNDS[0]);
    const [index, setIndex] = useState(0);
    const [overview, setOverview] = useState<Overview>({});
    const [readAloud, setReadAloud] = useState(false);
    const [deckOpen, setDeckOpen] = useState(false);
    const refresh = () => api<Overview>(`/interview/${workspaceId}/attempts`).then(setOverview).catch(() => undefined);
    useEffect(() => { void refresh(); }, [workspaceId]);
    const list = questions.rounds[round] || [];
    const question: Question | undefined = list[Math.min(index, list.length - 1)];
    useEffect(() => { if (readAloud && question) speak(question.text); }, [round, index, readAloud]);
    const status = (q: Question): keyof typeof STATUS_LABEL => !overview[q.id] ? 'new' : overview[q.id].needs_work.length ? 'work' : 'strong';
    const nextRound = ROUNDS[ROUNDS.indexOf(round) + 1];
    function go(target: string, position: number) {
        setRound(target);
        setIndex(position);
    }
    return <section className="coach-room" aria-label="Interview practice">
        <div className="room-toolbar">
            <div className="room-tabs" role="tablist" aria-label="Interview rounds">{ROUNDS.map(id => {
                const items = questions.rounds[id] || [];
                return <button type="button" role="tab" key={id} aria-selected={round === id} className={round === id ? 'active' : ''} onClick={() => go(id, 0)}>
                    {ROUND_INFO[id].title}<span>{items.filter(q => overview[q.id]).length}/{items.length}</span></button>;
            })}</div>
            <label className="room-aloud"><input type="checkbox" checked={readAloud} onChange={e => setReadAloud(e.target.checked)} />Read each question aloud</label>
        </div>
        {round === 'self_introduction' && <div className="room-deck">
            <button type="button" className="button subtle" aria-expanded={deckOpen} onClick={() => setDeckOpen(v => !v)}><Presentation size={15} />{deckOpen ? 'Hide slide deck' : 'Open your 2-minute introduction slide deck'}</button>
            {deckOpen && <SlideDeck workspaceId={workspaceId} jobId={questions.job.document_id} />}
        </div>}
        <div className="room-steps" aria-label={`${ROUND_INFO[round].title} questions`}>{list.map((q, i) =>
            <button type="button" key={`${q.id}-${i}`} className={`room-step ${status(q)} ${i === index ? 'current' : ''}`} aria-current={i === index ? 'step' : undefined}
                title={`${q.text} (${STATUS_LABEL[status(q)]})`} onClick={() => setIndex(i)}>{i + 1}</button>)}
            <span className="room-legend"><i className="new" />not practised <i className="work" />needs work <i className="strong" />strong</span>
        </div>
        {question ? <div className="room-main">
            <p className="room-meta">{ROUND_INFO[round].title} · Question {index + 1} of {list.length}{question.seconds ? ` · Aim for about ${question.seconds} seconds` : ''}{overview[question.id] ? ` · ${overview[question.id].attempts} attempt${overview[question.id].attempts > 1 ? 's' : ''} so far` : ''}</p>
            <h2 className="room-question">{question.text}</h2>
            <p className={question.requirement ? `coach-why ${question.requirement.status}` : 'coach-why'}>Why this question: {question.reason}</p>
            <AnswerRecorder key={`${round}-${index}`} workspaceId={workspaceId} questionId={question.id} questionText={question.text}
                jobId={questions.job.document_id} requirementId={question.requirement?.id} onResult={() => void refresh()} />
            <div className="room-nav">
                <button type="button" className="button subtle" disabled={index === 0} onClick={() => setIndex(index - 1)}><ArrowLeft size={15} />Previous</button>
                {index < list.length - 1
                    ? <button type="button" className="button dark" onClick={() => setIndex(index + 1)}>Next question<ArrowRight size={15} /></button>
                    : nextRound
                        ? <button type="button" className="button dark" onClick={() => go(nextRound, 0)}>Next round: {ROUND_INFO[nextRound].title}<ArrowRight size={15} /></button>
                        : <span className="room-done">That’s the last question. Revisit any amber ones to improve them.</span>}
            </div>
        </div> : <p className="coach-method">No questions in this round for this job.</p>}
    </section>;
}

import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Download, Maximize } from 'lucide-react';
import { api } from '../api';
import AnswerRecorder from './AnswerRecorder';

type Slide = { kind: string; title: string; subtitle: string | null; bullets: { text: string; source: string | null }[]; notes: string; point: string | null };
type Deck = { job: { document_id: string; title: string }; slides: Slide[]; target_seconds: number; estimated_seconds: number; note: string };

function Notes({ text }: { text: string }) {
    return <>{text.split(/(\[[^\]]+\])/).map((piece, i) => piece.startsWith('[') ? <mark className="notes-prompt" key={i}>{piece}</mark> : piece)}</>;
}

export default function SlideDeck({ workspaceId, jobId }: { workspaceId: string; jobId: string }) {
    const [deck, setDeck] = useState<Deck | null>(null);
    const [error, setError] = useState('');
    const [index, setIndex] = useState(0);
    const frame = useRef<HTMLDivElement>(null);
    useEffect(() => {
        api<Deck>(`/interview/${workspaceId}/slides?job=${encodeURIComponent(jobId)}`).then(setDeck).catch(e => setError(e.message));
    }, [workspaceId, jobId]);
    if (error) return <p className="live-error" role="alert">{error}</p>;
    if (!deck) return <p className="live-progress"><span className="live-dot" /> Building your deck from your confirmed facts…</p>;
    const slide = deck.slides[index];
    const move = (step: number) => setIndex(i => Math.min(deck.slides.length - 1, Math.max(0, i + step)));
    return <div className="coach-deck">
        <div className="deck-toolbar">
            <span>{deck.slides.length} slides · script about {deck.estimated_seconds} seconds (target {deck.target_seconds})</span>
            <div>
                <button type="button" className="text-button" onClick={() => void frame.current?.requestFullscreen?.()}><Maximize size={15} />Present full screen</button>
                <a className="button subtle" href={`/api/interview/${workspaceId}/slides.pdf?job=${encodeURIComponent(jobId)}`} download="introduction-deck.pdf"><Download size={15} />Download PDF</a>
            </div>
        </div>
        <div className="deck-stage">
            <div ref={frame} className={`deck-frame kind-${slide.kind}`} tabIndex={0} aria-label={`Slide ${index + 1} of ${deck.slides.length}: ${slide.title}`}
                onKeyDown={e => { if (e.key === 'ArrowRight' || e.key === ' ') { e.preventDefault(); move(1); } if (e.key === 'ArrowLeft') move(-1); }} onClick={() => move(1)}>
                {slide.subtitle && slide.kind !== 'title' && slide.kind !== 'closing' && <p className="deck-kicker">{slide.subtitle}</p>}
                <h3 className="deck-title">{slide.title}</h3>
                {(slide.kind === 'title' || slide.kind === 'closing') && slide.subtitle && <p className="deck-subtitle">{slide.subtitle}</p>}
                <ul className="deck-bullets">{slide.bullets.map((b, i) => <li key={i}>{b.text}{b.source && <small>{b.source}</small>}</li>)}</ul>
                <span className="deck-number">{index + 1} / {deck.slides.length}</span>
            </div>
        </div>
        <div className="deck-nav">
            <button type="button" className="button subtle" disabled={index === 0} onClick={() => move(-1)}><ArrowLeft size={15} />Previous slide</button>
            <span>{index + 1} / {deck.slides.length}</span>
            <button type="button" className="button subtle" disabled={index === deck.slides.length - 1} onClick={() => move(1)}>Next slide<ArrowRight size={15} /></button>
        </div>
        <div className="deck-notes"><strong>Speaker notes</strong><p><Notes text={slide.notes} /></p></div>
        <p className="coach-method">{deck.note}</p>
        <div className="deck-rehearse">
            <h4>Rehearse with the deck</h4>
            <p className="coach-method">Record yourself presenting while you move through the slides. You will see which slides you talked about, plus the usual delivery feedback and fact check.</p>
            <AnswerRecorder workspaceId={workspaceId} questionId="si-120" questionText="Present your two-minute introduction using your slide deck." jobId={jobId} extra={{ rehearsal: true }} />
        </div>
    </div>;
}

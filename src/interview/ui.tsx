import { ReactNode } from 'react';
import { tone } from './types';

// Small visual building blocks shared by the Interview Coach screens.

export function ScoreRing({ value, size = 96, label }: { value: number | null | undefined; size?: number; label?: string }) {
    const radius = size / 2 - 7;
    const circumference = 2 * Math.PI * radius;
    const filled = value == null ? 0 : Math.max(0, Math.min(100, value)) / 100 * circumference;
    return <div className={`ic-ring tone-${tone(value)}`} style={{ width: size, height: size }} role="img" aria-label={value == null ? 'No score yet' : `${value} out of 100`}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
            <circle className="ic-ring-track" cx={size / 2} cy={size / 2} r={radius} />
            <circle className="ic-ring-fill" cx={size / 2} cy={size / 2} r={radius} strokeDasharray={`${filled} ${circumference}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
        </svg>
        <span className="ic-ring-value" style={{ fontSize: size * 0.3 }}>{value == null ? '–' : value}</span>
        {label && <span className="ic-ring-label">{label}</span>}
    </div>;
}

export function Bar({ label, value }: { label: string; value: number }) {
    return <div className={`ic-bar tone-${tone(value)}`}>
        <span className="ic-bar-label">{label}</span>
        <span className="ic-bar-track"><span style={{ width: `${Math.max(3, value)}%` }} /></span>
        <span className="ic-bar-value">{value}</span>
    </div>;
}

export function Bubble({ who, children, meta, kind }: { who: 'interviewer' | 'you'; children: ReactNode; meta?: ReactNode; kind?: string }) {
    return <div className={`ic-bubble ic-${who} ${kind ? `ic-${kind}` : ''}`}>
        <span className="ic-avatar" aria-hidden="true">{who === 'interviewer' ? 'AI' : 'You'}</span>
        <div className="ic-bubble-body">
            <span className="ic-bubble-who">{who === 'interviewer' ? (kind === 'follow-up' ? 'Interviewer · follow-up' : 'Interviewer') : 'You'}</span>
            <div className="ic-bubble-text">{children}</div>
            {meta && <div className="ic-bubble-meta">{meta}</div>}
        </div>
    </div>;
}

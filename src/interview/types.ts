export type RequirementStatus = 'strong' | 'partial' | 'gap' | 'verify';
export type Question = { id: string; round: string; text: string; reason: string; seconds?: number; requirement?: { id: string; text: string; status: RequirementStatus } };
export type Questions = { job: { document_id: string; title: string }; review_status: string; rounds: Record<string, Question[]> };
export type Overview = Record<string, { attempts: number; needs_work: string[] }>;
export type ReportRow = { position: number; question: string; round: string; answered: boolean; score?: number; needs_work?: string[];
    follow_up?: { question: string; score: number; needs_work: string[] } };
export type Report = { session_id: string; job: { title: string }; created_at: string; overall: number; band: string; answered: number; total: number;
    cross_questioning: number | null; by_part: Record<string, number>; averages: { words_per_minute: number; fillers_per_minute: number; long_pauses: number };
    strengths: string[]; weak_spots: string[]; next_steps: string[]; questions: ReportRow[]; method: string };
export type ReportItem = { id: string; created_at: string; job: { document_id: string; title: string }; total: number; answered: number;
    overall: number | null; band: string; cross_questioning: number | null };

export const ROUNDS = ['self_introduction', 'behavioural', 'technical', 'motivation_fit'];
export const ROUND_INFO: Record<string, { title: string; detail: string }> = {
    self_introduction: { title: 'Self-introduction', detail: '30-second, 90-second and 2-minute versions.' },
    behavioural: { title: 'Behavioural', detail: 'STAR stories checked against your confirmed facts.' },
    technical: { title: 'Technical', detail: 'Drawn from the job’s own requirements.' },
    motivation_fit: { title: 'Motivation & fit', detail: 'Why this role, and honest answers about gaps.' },
};
export const PART_LABEL: Record<string, string> = { delivery: 'Delivery', length: 'Length', structure: 'STAR structure', content: 'Key points', honesty: 'Backed by profile' };

export function questionStatus(overview: Overview, id: string): 'new' | 'work' | 'strong' {
    return !overview[id] ? 'new' : overview[id].needs_work.length ? 'work' : 'strong';
}

export function tone(score: number | null | undefined) {
    return score == null ? 'none' : score >= 80 ? 'good' : score >= 60 ? 'fair' : 'poor';
}

// Target answer length in seconds; matches ROUND_TARGET_SECONDS on the server.
const ROUND_TARGET: Record<string, number> = { behavioural: 90, technical: 75, motivation_fit: 60 };
export function targetFor(question: Question) {
    return question.seconds ?? ROUND_TARGET[question.round] ?? null;
}

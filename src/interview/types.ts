export type RequirementStatus = 'strong' | 'partial' | 'gap' | 'verify';
export type Question = { id: string; round: string; text: string; reason: string; seconds?: number; requirement?: { id: string; text: string; status: RequirementStatus } };
export type Questions = { job: { document_id: string; title: string }; review_status: string; rounds: Record<string, Question[]> };
export const ROUND_INFO: Record<string, { title: string; detail: string }> = {
    self_introduction: { title: 'Self-introduction', detail: '30-second, 90-second and 2-minute versions, with a short slide deck to rehearse.' },
    behavioural: { title: 'Behavioural', detail: 'STAR answers on teamwork, conflict and failure, checked against your confirmed facts.' },
    technical: { title: 'Technical', detail: 'Questions drawn from the target job’s own requirements.' },
    motivation_fit: { title: 'Motivation & fit', detail: 'Why this role, and how to answer honestly about requirements you don’t meet yet.' },
};

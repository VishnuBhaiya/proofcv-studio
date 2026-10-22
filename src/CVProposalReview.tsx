import { Draft } from './api';

export default function CVProposalReview({ proposal, busy, review }: {
    proposal: { base: Draft; draft: Draft }; busy: boolean;
    review: (choice: 'accept' | 'dismiss') => void;
}) {
    const describe = (draft: Draft): Record<string, string> => ({
        Summary: draft.summary,
        Name: draft.profile.name,
        LinkedIn: draft.profile.linkedin || '',
        GitHub: draft.profile.github || '',
        Portfolio: draft.profile.portfolio || '',
        Education: draft.profile.education,
        Experience: draft.profile.experience,
        Achievements: draft.profile.achievements,
        Goal: draft.profile.goal,
        Contact: [draft.profile.email, draft.profile.phone, draft.profile.location].filter(Boolean).join(' · '),
        Skills: draft.selection.skills.join(', '),
        Projects: draft.selection.project_order.map(i => { const p = draft.profile.projects[i]; return p ? `${p.title}${p.technologies ? ` (${p.technologies})` : ''}` : ''; }).join(' → '),
        Sections: (draft.design?.visible_sections || draft.selection.section_order).join(' → '),
        Layout: draft.template, Colour: draft.accent,
        Font: draft.design?.font || 'sans', 'Text size': draft.design?.size || 'standard',
        Spacing: draft.design?.spacing || 'comfortable', Header: draft.design?.header || 'center',
        'Skills layout': draft.design?.skills || 'inline', 'Page preference': draft.design?.page || 'auto',
        'ATS-friendly formatting': draft.design?.ats ? 'Enabled — simple, undecorated formatting' : 'Off',
    });
    const before = describe(proposal.base), after = describe(proposal.draft);
    const changes = Object.keys(after).filter(key => before[key] !== after[key]);
    return <section className="cv-chat-intro" aria-label="Review suggested CV changes">
        <h3>Apply these changes to your CV?</h3>
        <p>Your CV stays unchanged until you accept. Accepting profile changes confirms the displayed details and updates both My profile and this CV.</p>
        {changes.map(key => <div key={key}><h4>{key}</h4><p>Current: {before[key] || 'None'}</p><p>Suggested: {after[key] || 'None'}</p></div>)}
        {!changes.length && <p>These settings already match your CV.</p>}
        <div><button type="button" className="button dark" disabled={busy} onClick={() => review('accept')}>Accept & update CV</button> <button type="button" className="button" disabled={busy} onClick={() => review('dismiss')}>Dismiss suggestion</button></div>
    </section>;
}

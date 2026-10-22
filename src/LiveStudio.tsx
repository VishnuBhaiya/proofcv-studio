import { useEffect, useState } from 'react';
import { ArrowRight, ArrowUpRight, Check, FileText, GitCompareArrows, History, LayoutDashboard, Menu, MessageCircle, Plus, RotateCcw, Save, ShieldCheck, Sparkles, Target, UserRound, X } from 'lucide-react';
import { api, Draft, Profile, Workspace, ProfileProposal, Design } from './api';
import './live.css';
import './suggestions.css';
import './design.css';
import './design-extra.css';
import './workflow.css';
import './cv-chat.css';
import './preview-design.css';
import './studio-layout.css';
import { educationEntries } from './education';
import ProfileEditor from './ProfileEditor';
import DocumentUpload from './DocumentUpload';
import InterviewProgress from './InterviewProgress';
import ProposalReview from './ProposalReview';
import CVProposalReview from './CVProposalReview';
type Page = 'overview' | 'profile' | 'jobs' | 'studio' | 'history';
type GeminiStatus = {
    configured: boolean;
    model: string;
    models: string[];
    models_tried: string[];
    failure_kind: '' | 'temporary' | 'configuration' | 'not_configured';
    connection_verified: boolean;
    availability: 'available' | 'unavailable' | 'not_checked' | 'not_configured';
};
function DesignControls({ draft, setDraft, sectionsOnly = false }: { draft: Draft; setDraft: (draft: Draft) => void; sectionsOnly?: boolean }) {
    const defaults: Design = { font: 'sans', size: 'standard', spacing: 'comfortable', header: 'center', skills: 'inline', page: 'auto', ats: false, visible_sections: ['projects', 'education', 'experience', 'achievements'] };
    const design: Design = { ...defaults, ...(draft.design || {}) };
    const update = (patch: Partial<Design>) => setDraft({ ...draft, design: { ...design, ...patch } });
    const labels: Record<string, string> = { projects: 'Projects', education: 'Education', experience: 'Experience', achievements: 'Achievements' };
    const available = Object.keys(labels);
    const visible = available.filter(section => design.visible_sections.includes(section));
    const toggleSection = (section: string) => {
        if (design.visible_sections.includes(section)) {
            if (section === 'projects' || section === 'education') return;
            update({ visible_sections: design.visible_sections.filter(item => item !== section) });
        } else {
            update({ visible_sections: [...design.visible_sections, section] });
        }
    };
    const moveSection = (section: string, direction: -1 | 1) => {
        const index = visible.indexOf(section);
        const next = index + direction;
        if (index < 0 || next < 0 || next >= visible.length) return;
        const reordered = [...visible];
        [reordered[index], reordered[next]] = [reordered[next], reordered[index]];
        update({ visible_sections: reordered });
    };
    const reset = () => update({ ...defaults });
    const applyPreset = (preset: 'editorial' | 'ats' | 'showcase') => {
        const presets: Record<typeof preset, Partial<Design> & { template: Draft['template']; accent: string }> = {
            editorial: { template: 'editorial', accent: '#2c6554', ...defaults },
            ats: { template: 'classic', accent: '#292929', font: 'sans', size: 'compact', spacing: 'compact', header: 'left', skills: 'inline', page: 'one', ats: true },
            showcase: { template: 'editorial', accent: '#935345', font: 'serif', size: 'large', spacing: 'spacious', header: 'center', skills: 'pills', page: 'auto', ats: false }
        };
        const selected = presets[preset];
        const { template, accent, ...designPatch } = selected;
        setDraft({ ...draft, template, accent, design: { ...design, ...designPatch } });
    };
    const words = [draft.summary, draft.profile.education, draft.profile.experience, draft.profile.achievements, ...draft.selection.project_order.map(index => `${draft.profile.projects[index].title} ${draft.profile.projects[index].description}`)].join(' ').trim().split(/\s+/).filter(Boolean).length;
    const estimatedPages = design.page === 'one' ? 1 : design.page === 'two' ? 2 : words > 520 || design.size === 'large' || design.spacing === 'spacious' ? 2 : 1;
    return <section className={`design-controls ${sectionsOnly ? 'sections-only' : ''}`} aria-label={sectionsOnly ? 'CV section controls' : 'CV design controls'}>
        {!sectionsOnly && <>
            <div className="design-heading"><div><strong>Design controls</strong><small>Make the document feel like yours. Changes appear in the preview immediately.</small></div><span className="design-badge">LIVE PREVIEW</span></div>
            <div className="design-grid">
                <label>Layout<select value={draft.template} onChange={e => setDraft({ ...draft, template: e.target.value as Draft['template'], design: {...design, ats:false} })}><option value="editorial">Editorial</option><option value="classic">Classic</option><option value="modern">Modern</option><option value="minimal">Minimal</option><option value="executive">Executive</option></select></label>
                <label>Font<select value={design.font} onChange={e => update({ font: e.target.value as Design['font'] })}><option value="sans">Sans serif</option><option value="serif">Serif</option><option value="mono">Monospace</option></select></label>
                <label>Text size<select value={design.size} onChange={e => update({ size: e.target.value as Design['size'] })}><option value="compact">Compact</option><option value="standard">Standard</option><option value="large">Large</option></select></label>
                <label>Spacing<select value={design.spacing} onChange={e => update({ spacing: e.target.value as Design['spacing'] })}><option value="compact">Compact</option><option value="comfortable">Comfortable</option><option value="spacious">Spacious</option></select></label>
                <label>Header<select value={design.header} onChange={e => update({ header: e.target.value as Design['header'] })}><option value="center">Centered</option><option value="left">Left aligned</option></select></label>
                <label>Skills layout<select value={design.skills} onChange={e => update({ skills: e.target.value as Design['skills'] })}><option value="inline">Inline</option><option value="pills">Pills</option><option value="grouped">Grouped</option></select></label>
                <label>Page mode<select value={design.page} onChange={e => update({ page: e.target.value as Design['page'] })}><option value="auto">Automatic</option><option value="one">One page</option><option value="two">Two pages</option></select></label>
            </div>
            <div className="design-presets"><span>Quick start</span><button type="button" onClick={() => applyPreset('editorial')}>Editorial</button><button type="button" aria-pressed={design.ats} style={design.ats ? {background: '#dce9ce', fontWeight: 700} : undefined} onClick={() => applyPreset('ats')}>{design.ats ? '✓ ATS-ready' : 'ATS-ready'}</button><button type="button" onClick={() => applyPreset('showcase')}>Showcase</button><span className="page-estimate">Estimated {estimatedPages} page{estimatedPages === 1 ? '' : 's'}</span></div>
            <div className="design-toggles"><button type="button" className="text-button" onClick={reset}>Reset design</button></div>
            <small>Validate & save edits sends these settings to the Python service and keeps them with this CV version.</small>
        </>}
        {sectionsOnly && <div className="design-section-editor"><div><strong>Sections</strong><small>Choose what appears and change its order.</small></div><div className="section-checks">{available.map(section => <label key={section} className={!design.visible_sections.includes(section) ? 'muted' : ''}><input type="checkbox" checked={design.visible_sections.includes(section)} disabled={section === 'projects' || section === 'education'} onChange={() => toggleSection(section)} />{labels[section]}{(section === 'projects' || section === 'education') && <em>required</em>}</label>)}</div><div className="section-order">{visible.map((section, index) => <div className="section-order-row" key={section}><span>{index + 1}</span><strong>{labels[section]}</strong><div><button type="button" className="icon-button" aria-label={`Move ${labels[section]} up`} disabled={index === 0} onClick={() => moveSection(section, -1)}>↑</button><button type="button" className="icon-button" aria-label={`Move ${labels[section]} down`} disabled={index === visible.length - 1} onClick={() => moveSection(section, 1)}>↓</button></div></div>)}</div></div>}
    </section>;
}
function CVChat({ workspace, busy, error, send, review }: { workspace: Workspace; busy: boolean; error: string; send: (message: string) => void; review: (choice: 'accept' | 'dismiss') => void }) {
    const [text, setText] = useState('');
    const [pending, setPending] = useState('');
    const messages = workspace.cv_messages || [];
    const quick = ['Strengthen my summary', 'Make this ATS-friendly', 'Show only my strongest evidence', 'What changed?'];
    return <section className="cv-chat" aria-label="Gemini CV studio chat">
        <div className="cv-chat-heading"><span className="sparkle-icon"><Sparkles size={18}/></span><div><strong>Gemini CV studio</strong><span>Live editor · confirmed facts only</span></div></div>
        <div className="cv-chat-intro"><strong>Shape this CV with a conversation.</strong><span>Ask for a safe edit, a layout change, or an explanation. The preview changes only after you accept a suggestion.</span></div>
        <div className="cv-chat-history" aria-live="polite">{!messages.length && <p className="cv-chat-empty">Try a quick request below, or tell Gemini exactly what you want changed.</p>}{messages.map((m, i) => <div className={`cv-chat-message ${m.role}`} key={i}><small>{m.role === 'user' ? 'You' : 'Gemini'}</small><p>{m.content}</p></div>)}{busy && pending && <InterviewProgress message={pending}/>}</div>
        {error && <p role="alert" className="live-error">{error}</p>}
        <p className="helper">Sending saves your current CV edits first. Gemini then works with that draft.</p>
        {workspace.pending_cv && <CVProposalReview proposal={workspace.pending_cv} busy={busy} review={review}/>}
        <div className="cv-chat-quick">{quick.map(item => <button type="button" key={item} disabled={busy || !!workspace.pending_cv} onClick={() => { setPending(item); setText(''); send(item); }}>{item}</button>)}</div>
        <form className="cv-chat-composer" onSubmit={e => { e.preventDefault(); if (text.trim()) { setPending(text.trim()); send(text.trim()); setText(''); } }}><textarea value={text} onChange={e => setText(e.target.value)} rows={2} placeholder="e.g. Put education first and use a compact layout" disabled={busy || !!workspace.pending_cv}/><button className="button dark" disabled={busy || !!workspace.pending_cv || !text.trim()}><MessageCircle size={15}/>Send to Gemini</button></form>
        <details className="tool-trace"><summary>Actual CV tool activity · {(workspace.cv_trace || []).length} steps</summary><p>Stopping condition: {workspace.cv_stop_reason || 'Not run'}</p><pre>{JSON.stringify(workspace.cv_trace || [], null, 2)}</pre></details>
    </section>;
}
const routes = [{ id: 'overview', label: 'Overview', icon: LayoutDashboard }, { id: 'profile', label: 'My profile', icon: UserRound }, { id: 'jobs', label: 'Discover jobs', icon: Target }, { id: 'studio', label: 'CV studio', icon: FileText }, { id: 'history', label: 'Versions & comparison', icon: GitCompareArrows }] as const;
function LiveOverview({ workspace: w, confirmed, go, start, busy }: { workspace: Workspace; confirmed: boolean; go: (page: Page) => void; start: (reuse: boolean, name: string) => Promise<void>; busy: boolean }) {
    const [showStart, setShowStart] = useState(false);
    const [newName, setNewName] = useState('');
    const hasProfile = !!w.profile.name.trim();
    const usableDraft = confirmed && w.draft?.revision === w.revision;
    const jobCount = confirmed ? (w.retrieval?.results.length ?? 0) : 0;
    const next: Page = !confirmed ? 'profile' : usableDraft ? 'studio' : 'jobs';
    const action = !hasProfile ? 'Start your profile' : !confirmed ? 'Review your profile' : usableDraft ? 'Continue your CV' : jobCount ? 'Choose your target role' : 'Find your next role';
    return <div className="page-content live-overview">
        <div className="welcome-card">
            <div><span className="eyebrow">{hasProfile ? `HELLO, ${w.profile.name.trim().split(/\s+/)[0].toUpperCase()}` : 'A BETTER BEGINNING'}</span>
                <h2>Your experience has a story.<br /><em>Let’s give it a great opening.</em></h2>
                <p>Bring your profile, your next role and your best work together in one thoughtful workspace.</p>
                <div className="overview-actions"><button className="button dark" onClick={() => go(next)}>{action}<ArrowRight size={17} /></button><button className="button subtle" aria-expanded={showStart} aria-controls="new-cv-options" onClick={() => setShowStart(v => !v)}><Plus size={17} />Start a new CV</button></div>
            </div>
            <div className="welcome-art" aria-hidden="true"><span className="art-orbit" /><div className="art-paper"><FileText size={32} /><h3>{w.profile.name || 'Your next chapter'}</h3><span /><span /><hr /><span /><span /><span /></div><span className="art-badge"><ShieldCheck size={18} />A story you can stand behind</span></div>
        </div>
        {showStart && <section id="new-cv-options" className="new-cv-panel" aria-labelledby="new-cv-title"><div className="section-heading"><h2 id="new-cv-title">A fresh start. Your choice.</h2><button className="text-button" disabled={busy} onClick={() => setShowStart(false)}>Cancel</button></div><p>Your current workspace, CV and saved versions stay untouched. Each option creates a separate workspace.</p><label className="wide-label">New CV / workspace name<input value={newName} disabled={busy} onChange={e => setNewName(e.target.value)} placeholder="e.g. My next application" /></label><div className="live-recent-work"><button className="live-work-card" disabled={busy || !hasProfile} onClick={() => void start(true, newName)}><UserRound /><div><strong>Use my existing profile</strong><p>Copy your saved facts, review and confirm them, then choose another role. No retyping.</p></div><ArrowUpRight /></button><button className="live-work-card" disabled={busy} onClick={() => void start(false, newName)}><Plus /><div><strong>Start with a new profile</strong><p>Begin with blank details and a fresh interview.</p></div><ArrowUpRight /></button></div></section>}
        <div className="overview-stats">
            <button onClick={() => go('profile')}><UserRound /><div><span>YOUR PROFILE</span><strong>{confirmed ? 'Confirmed' : hasProfile ? 'Needs review' : 'Ready to begin'}</strong></div><ArrowUpRight /></button>
            <button onClick={() => go('jobs')}><Target /><div><span>EXPLORE</span><strong>{jobCount ? `${jobCount} retrieved roles` : 'Find your matches'}</strong></div><ArrowUpRight /></button>
            <button onClick={() => go('history')}><History /><div><span>SAVED VERSIONS</span><strong>{w.versions.length} saved {w.versions.length === 1 ? 'version' : 'versions'}</strong></div><ArrowUpRight /></button>
        </div>
        <div className="section-heading"><h2>Your recent work</h2><span>Saved on this computer</span></div>
        <div className="live-recent-work">
            {w.draft ? <button className="live-work-card" onClick={() => go(usableDraft ? 'studio' : 'profile')}><FileText /><div><strong>{w.draft.job.title}</strong><p>{usableDraft ? 'Current draft · continue tailoring your CV' : 'Profile changed · review and reconfirm before regenerating'}</p></div><ArrowUpRight /></button> : <div className="live-work-card"><FileText /><div><strong>Your first draft starts with you.</strong><p>Confirm your profile, discover three relevant roles, then build a grounded CV.</p></div></div>}
            {w.versions.slice(-2).reverse().map(v => <button className="live-work-card" key={v.id} onClick={() => go('history')}><History /><div><strong>{v.draft.job.title}</strong><p>Saved version · {new Date(v.saved_at).toLocaleDateString()}</p></div><ArrowUpRight /></button>)}
        </div>
    </div>;
}
export default function LiveStudio() {
    const [studioTab, setStudioTab] = useState<'content' | 'design'>('content');
    const [removeTarget, setRemoveTarget] = useState<Workspace | null>(null);
    const [trashOpen, setTrashOpen] = useState(false);
    const [purgeTrashConfirm, setPurgeTrashConfirm] = useState(false);
    const [trash, setTrash] = useState<{ id: string; label: string }[]>([]);
    const [workspaces, setWorkspaces] = useState<{
        id: string;
        label: string;
    }[]>([]), [current, setCurrent] = useState<Workspace | null>(null), [page, setPage] = useState<Page>('overview');
    const [status, setStatus] = useState<GeminiStatus | null>(null), [error, setError] = useState(''), [busy, setBusy] = useState(''), [notice, setNotice] = useState(''), [message, setMessage] = useState(''), [label, setLabel] = useState(''), [mobile, setMobile] = useState(false), [compare, setCompare] = useState('');
    const [profileEdit, setProfileEdit] = useState<Profile | null>(null), [draftEdit, setDraftEdit] = useState<Draft | null>(null), [accepted, setAccepted] = useState(false);
    async function load() { try {
        const [s, w] = await Promise.all([api<GeminiStatus>('/status'), api<{
                id: string;
                label: string;
            }[]>('/workspaces')]);
        setStatus(s);
        setWorkspaces(w);
        if (w.length) {
            const state = await api<Workspace>('/workspaces/' + w[0].id);
            receive(state);
        }
    }
    catch (e) {
        setError(String(e));
    } }
    useEffect(() => { void load(); }, []);
    async function refreshGeminiStatus() {
        try { setStatus(await api<GeminiStatus>('/status')); }
        catch { /* The primary operation reports connection errors. */ }
    }
    function receive(w: Workspace) { setCurrent(w); setProfileEdit(structuredClone(w.profile)); setDraftEdit(w.draft ? structuredClone(w.draft) : null); setAccepted(false); }
    const confirmed = !!current && current.confirmed_revision === current.revision;
    const dirty = !!current && JSON.stringify(profileEdit) !== JSON.stringify(current.profile);
    const draftDirty = !!current && JSON.stringify(draftEdit) !== JSON.stringify(current.draft);
    const proposal = (current as (Workspace & {pending_profile?: ProfileProposal}) | null)?.pending_profile;
    async function showTrash() {
        setTrashOpen(true); setError('');
        try { setTrash(await api<{ id: string; label: string }[]>('/workspace-trash')); }
        catch (e) { setError(String(e)); }
    }
    async function removeWorkspace() {
        if (!removeTarget || busy) return;
        if (dirty || draftDirty) { setError('Save or discard your edits before removing this workspace.'); setRemoveTarget(null); return; }
        setBusy('remove'); setError('');
        try {
            await api(`/workspaces/${removeTarget.id}/remove-workspace`, { revision: removeTarget.revision, accepted: true });
            const remaining = workspaces.filter(w => w.id !== removeTarget.id);
            setWorkspaces(remaining); setCurrent(null); setProfileEdit(null); setDraftEdit(null);
            setAccepted(false); setMessage(''); setCompare(''); setPage('overview'); setRemoveTarget(null);
            setNotice('Workspace moved to Removed workspaces. Its profile, CV and versions can be restored.');
            if (remaining.length) receive(await api<Workspace>('/workspaces/' + remaining[0].id));
            if (trashOpen) setTrash(await api<{ id: string; label: string }[]>('/workspace-trash'));
        } catch (e) { setError(String(e)); }
        finally { setBusy(''); }
    }
    async function restoreWorkspace(id: string) {
        if (busy) return;
        if (dirty || draftDirty) { setError('Save or discard your edits before restoring a workspace.'); return; }
        setBusy('restore'); setError('');
        try {
            const restored = await api<Workspace>(`/workspaces/${id}/restore-workspace`, {});
            setWorkspaces(v => [...v.filter(w => w.id !== id), { id, label: restored.label }]);
            setTrash(v => v.filter(w => w.id !== id)); receive(restored); setPage('overview'); setMessage(''); setCompare('');
            setNotice('Workspace restored with its saved profile, CV and versions.');
        } catch (e) { setError(String(e)); }
        finally { setBusy(''); }
    }
    async function purgeRemovedWorkspaces() {
        if (busy || !purgeTrashConfirm) return;
        setBusy('purge'); setError('');
        try {
            const result = await api<{deleted: number}>('/workspaces/trash/purge-removed-workspaces', { accepted: true });
            setTrash([]); setPurgeTrashConfirm(false);
            setNotice(`${result.deleted} removed workspace${result.deleted === 1 ? '' : 's'} permanently deleted. This cannot be undone.`);
        } catch (e) { setError(String(e)); }
        finally { setBusy(''); }
    }
    async function startNewCV(reuse: boolean, name: string) {
        if (!current || busy) return;
        if (dirty || draftDirty) { setError('Save or discard your current edits before starting a new CV.'); return; }
        setBusy('create'); setError('');
        let created: Workspace | null = null;
        try {
            created = await api<Workspace>('/workspaces', { label: name.trim() || (reuse ? `${current.profile.name} — new CV` : 'New CV workspace') });
            setWorkspaces(v => [...v, { id: created!.id, label: created!.label }]);
            if (reuse) created = await api<Workspace>(`/workspaces/${created.id}/profile`, { revision: created.revision, patch: structuredClone(current.profile) });
            receive(created); setPage('profile'); setMobile(false); setMessage(''); setCompare('');
            setNotice(reuse ? 'New workspace created with your saved facts. Review and confirm them before choosing a role. Your original CV is unchanged.' : 'Your new workspace is ready. Introduce yourself to begin. Your previous work is unchanged.');
        } catch (e) {
            if (created) { receive(created); setPage('profile'); }
            setError(e instanceof Error ? e.message : String(e));
        } finally { setBusy(''); }
    }
    async function run(operation: string, data: Record<string, unknown> = {}, next?: Page) { if (!current || busy)
        return; if (dirty && operation !== 'profile' && operation !== 'review-profile') {
        setError('Save or discard your profile edits before continuing.');
        return;
    } if (draftDirty && operation !== 'edit' && operation !== 'cv-chat') {
        setError('Validate and save, or discard, your CV edits before continuing.');
        return;
    } setBusy(operation); setError(''); setNotice(''); try {
        const local = operation === 'review-profile' && data.choice === 'accept' && dirty && profileEdit ? { local_profile: {...profileEdit, skills:profileEdit.skills.map(s=>s.trim()).filter(Boolean), summary_facts:profileEdit.summary_facts.map(s=>s.trim()).filter(Boolean)} } : {};
        const draftPatch = operation === 'cv-chat' && draftDirty && draftEdit ? {draft_patch:{summary:draftEdit.summary,selection:draftEdit.selection,template:draftEdit.template,accent:draftEdit.accent,design:draftEdit.design}} : {};
        const w = await api<Workspace>(`/workspaces/${current.id}/${operation}`, { revision: current.revision, ...data, ...local, ...draftPatch });
        receive(w);
        if (operation === 'chat' || operation === 'cv-chat' || operation === 'find-jobs' || operation === 'generate') await refreshGeminiStatus();
        if (operation === 'review-profile' && data.choice === 'dismiss' && dirty && profileEdit) setProfileEdit(profileEdit);
        if (next)
            setPage(next);
        setNotice(operation === 'find-jobs' ? 'Gemini chose the retrieval tool and Python returned your three semantic matches.' : operation === 'chat' ? 'Agent turn complete.' : operation === 'confirm' ? 'Profile confirmed. This snapshot is reusable.' : 'Saved to your local Python workspace.');
        if (operation === 'chat')
            setMessage('');
    }
    catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        if (operation === 'chat' || operation === 'cv-chat' || operation === 'find-jobs' || operation === 'generate') await refreshGeminiStatus();
        if (operation === 'chat' || operation === 'cv-chat') {
            try {
                const refreshed = await api<Workspace>('/workspaces/' + current.id);
                if (operation === 'cv-chat' && draftDirty) setCurrent(refreshed);
                else receive(refreshed);
            }
            catch { /* retain current UI */ }
        }
    }
    finally {
        setBusy('');
    } }
    async function create() { if (!label.trim() || busy)
        return; if (dirty || draftDirty) {
        setError('Save or discard your current edits before creating another workspace.');
        return;
    } setBusy('create'); setError(''); try {
        const w = await api<Workspace>('/workspaces', { label });
        setWorkspaces(v => [...v, { id: w.id, label: w.label }]);
        receive(w);
        setLabel('');
        setPage('overview');
        setMessage('');
    }
    catch (e) {
        setError(String(e));
    }
    finally {
        setBusy('');
    } }
    async function openLabelledSample() {
        if (busy) return;
        if (dirty || draftDirty) { setError('Save or discard your edits before opening the sample.'); window.scrollTo({top:0}); return; }
        setBusy('load'); setError('');
        try {
            const available = await api<{id:string;label:string}[]>('/workspaces');
            setWorkspaces(available);
            const sample = available.find(w => w.label === 'Avery Morgan — labelled fictional sample');
            if (!sample) throw new Error('The labelled sample workspace is unavailable.');
            const workspace = await api<Workspace>('/workspaces/' + sample.id);
            receive(workspace);
            setPage('studio'); setMobile(false); setMessage(''); setCompare('');
            setNotice('Fictional sample: Avery Morgan. Two detailed, manually curated CVs are saved in Versions & comparison. All candidate details are synthetic.');
            window.scrollTo({top:0});
        } catch (e) { setError(String(e)); }
        finally { setBusy(''); }
    }
    async function switchWorkspace(id: string) { if (dirty || draftDirty) {
        setError('Save or discard your current edits before switching workspace.');
        return;
    } setBusy('load'); setError(''); try {
        receive(await api<Workspace>('/workspaces/' + id));
        setPage('overview');
        setMessage('');
        setCompare('');
        setNotice('');
    }
    catch (e) {
        setError(String(e));
    }
    finally {
        setBusy('');
    } }
    async function download() { if (!current)
        return; if (draftDirty) {
        setError('Validate and save your CV edits before downloading.');
        return;
    } setBusy('pdf'); setError(''); try {
        const response = await fetch(`/api/workspaces/${current.id}/pdf`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ revision: current.revision }) });
        if (!response.ok)
            throw new Error((await response.json()).error);
        const url = URL.createObjectURL(await response.blob()), a = document.createElement('a');
        a.href = url;
        a.download = `ProofCV-${current.draft?.job.document_id}.pdf`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        setNotice('PDF downloaded from the confirmed server draft.');
    }
    catch (e) {
        setError(String(e));
    }
    finally {
        setBusy('');
    } }
    function patchProfile(patch: Partial<Profile>) { if (profileEdit) {
        setProfileEdit({ ...profileEdit, ...patch });
        setAccepted(false);
    } }
    return <div className="app-shell live-app">
 {mobile && <button className="nav-backdrop" aria-label="Close navigation" onClick={() => setMobile(false)}/>}
 <aside className={`sidebar ${mobile ? 'open' : ''}`}><a className="brand" href="#" onClick={e => e.preventDefault()}><span className="brand-mark"><FileText size={23}/></span>proof<span>cv</span><i>®</i></a><div className="workspace-label">YOUR NEXT CHAPTER</div><nav>{routes.map(r => <button key={r.id} className={`nav-item ${page === r.id ? 'active' : ''}`} aria-current={page === r.id ? 'page' : undefined} onClick={() => { setPage(r.id); setMobile(false); }}><r.icon size={18}/>{r.label}</button>)}</nav><div className="sidebar-divider"/><div className="workspace-label">LOCAL WORKSPACES</div><select aria-label="Select workspace" value={current?.id || ''} disabled={!!busy} onChange={e => void switchWorkspace(e.target.value)}><option value="" disabled>Choose a workspace</option>{workspaces.map(w => <option key={w.id} value={w.id}>{w.label}</option>)}</select><div className="new-workspace"><label htmlFor="new-workspace">New person / workspace</label><input id="new-workspace" value={label} onChange={e => setLabel(e.target.value)} placeholder="e.g. My graduate applications"/><button className="new-version" disabled={!label.trim() || !!busy} onClick={() => void create()}><Plus size={15}/>Create workspace</button></div><div className="sidebar-bottom"><div className="integrity-card"><ShieldCheck /><strong>Your story. Your words.</strong><p>Confirmed facts. Visible sources.<br />No invented achievements.</p></div><button className="text-button sample-link" disabled={!!busy} onClick={() => void openLabelledSample()}>Open labelled sample interface</button></div></aside>
 <div className="main-shell"><header className="topbar"><div className="breadcrumbs"><button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobile(true)}><Menu /></button><span>{current?.label || 'ProofCV'}</span><ArrowRight size={12}/><strong>{routes.find(r => r.id === page)?.label}</strong></div><span className={`demo-badge status-${status?.availability || 'not_checked'}`} title={status?.connection_verified ? `The most recent Gemini request succeeded using ${status.model}.` : status?.availability === 'unavailable' ? `${status.failure_kind === 'configuration' ? 'Stopped after a non-retryable key, permission or model configuration error.' : 'Every configured fallback was attempted.'} Tried: ${(status.models_tried || []).join(', ') || 'none'}.` : 'Gemini has not been contacted in this server session.'}><span />{!status?.configured ? 'Live AI not configured' : status.connection_verified ? `Gemini live · ${status.model}` : status.availability === 'unavailable' ? `Gemini unavailable · ${(status.models_tried || []).length} model${(status.models_tried || []).length === 1 ? '' : 's'} tried` : `Gemini configured · ${status.models.length} models · not checked`}</span></header>
 <main><div className="studio-heading"><div><div className="eyebrow">{page === 'overview' ? 'YOUR NEXT CHAPTER STARTS HERE' : 'MAKE YOUR EXPERIENCE COUNT'}</div><h1>{page === 'overview' ? 'Your workspace' : <>Your next chapter, <em>well written.</em></>}</h1><p>{page === 'overview' ? 'A little intention. A lot of possibility.' : 'A thoughtful CV. A stronger application. Always your story.'}</p></div>{page !== 'overview' && current?.draft && <button className="button dark" disabled={!!busy || !confirmed || dirty || current.draft.revision !== current.revision} onClick={() => void download()}><ArrowUpRight size={16}/>Download PDF</button>}</div>
 <div className="workspace-management"><button className="text-button" disabled={!current || !!busy} onClick={() => { if (dirty || draftDirty) { setError('Save or discard your edits before removing this workspace.'); return; } setRemoveTarget(current); }}>Remove workspace</button><button className="text-button" disabled={!!busy} onClick={() => trashOpen ? setTrashOpen(false) : void showTrash()}>{trashOpen ? 'Hide removed workspaces' : 'Removed workspaces'}</button></div>
 {removeTarget && <section className="workspace-remove-panel" role="alertdialog" aria-modal="false" aria-labelledby="remove-title"><h2 id="remove-title">Remove “{removeTarget.label}”?</h2><p>This moves the whole workspace—including its profile, chat, current CV and saved versions—to Removed workspaces. You can restore it later. Other workspaces are unaffected.</p><div className="overview-actions"><button className="button dark" disabled={!!busy} onClick={() => void removeWorkspace()}>Move to removed workspaces</button><button className="button subtle" disabled={!!busy} onClick={() => setRemoveTarget(null)}>Cancel removal</button></div></section>}
 {trashOpen && <section className="workspace-remove-panel" aria-label="Removed workspaces"><h2>Removed workspaces</h2><p>These workspaces remain recoverable until you permanently delete them.</p>{trash.length ? <>{trash.map(w => <div className="trash-row" key={w.id}><span>{w.label}</span><button className="button subtle" disabled={!!busy} onClick={() => void restoreWorkspace(w.id)}>Restore {w.label}</button></div>)}{purgeTrashConfirm ? <div className="purge-confirm" role="alert"><strong>Permanently delete all {trash.length} removed workspaces?</strong><p>This erases their profiles, chats, CVs and saved versions. It cannot be undone.</p><div className="overview-actions"><button className="button danger" disabled={!!busy} onClick={() => void purgeRemovedWorkspaces()}>Yes, permanently delete all</button><button className="button subtle" disabled={!!busy} onClick={() => setPurgeTrashConfirm(false)}>Cancel</button></div></div> : <button className="text-button purge-button" disabled={!!busy} onClick={() => setPurgeTrashConfirm(true)}>Permanently delete all removed workspaces</button>}</> : <p>No removed workspaces.</p>}</section>}
 <div className="live-messages" aria-live="polite">{(dirty || draftDirty) && <div className="live-progress"><span>Unsaved {dirty ? 'profile' : 'CV'} edits</span><button className="text-button" disabled={!!busy} onClick={() => { if (current) {
        setProfileEdit(structuredClone(current.profile));
        setDraftEdit(current.draft ? structuredClone(current.draft) : null);
        setError('');
    } }}>Discard unsaved edits</button></div>}{busy && <p className="live-progress"><span className="live-dot"/> {busy === 'chat' ? 'Gemini is choosing and executing profile tools…' : busy === 'find-jobs' ? 'Gemini is choosing an action from your confirmed profile…' : busy === 'generate' ? 'Selecting confirmed evidence for your target role…' : busy === 'retrieve' ? 'Embedding your profile and searching all nine jobs…' : `${busy} in progress…`}</p>}{error && <div role="alert" className="live-error">{error}<button className="icon-button" aria-label="Dismiss error" onClick={() => setError('')}><X size={16}/></button></div>}{notice && <p className="live-success"><Check size={15}/>{notice}</p>}</div>
 {!current ? <div className="page-content"><div className="welcome-card"><div><span className="eyebrow">A BETTER BEGINNING</span><h2>Your experience has a story.<br /><em>Let’s find the right words.</em></h2><p>Create a workspace using the sidebar. Then introduce yourself to the live agent. It will save your facts and ask about what’s missing.</p><p>Profiles stay on this computer. Information sent to the agent is shared with Gemini. Use synthetic data for assessment testing.</p>{error && <button className="button dark" onClick={() => void load()}>Retry server connection</button>}</div></div></div> : <>
 {page === 'overview' && <LiveOverview key={current.id} workspace={current} confirmed={confirmed} go={setPage} start={startNewCV} busy={!!busy} />}
 {page !== 'overview' && <div className="workflow-strip" aria-label="CV workflow">{['Introduce', 'Review & confirm', 'Find three jobs', 'Tailor & export'].map((s, i) => { const target: Page = i < 2 ? 'profile' : i === 2 ? 'jobs' : 'studio'; const done = i === 0 || i === 1 && confirmed || i === 2 && current.retrieval || i === 3 && current.draft; return <button type="button" key={s} className={done ? 'done' : ''} aria-current={(i === 0 && page === 'profile' && !confirmed) || (i === 1 && page === 'profile' && confirmed) || (i === 2 && page === 'jobs') || (i === 3 && page === 'studio') ? 'step' : undefined} onClick={() => { setPage(target); window.scrollTo({ top: 0, behavior: 'smooth' }); }}><span>{i + 1}</span>{s}</button>; })}</div>}
 {page === 'profile' && profileEdit && <div className="page-content live-profile-grid"><section className="profile-form"><div className="profile-banner"><span className="avatar large"><UserRound /></span><div><h2>{profileEdit.name || 'Your profile'}</h2><p>Revision {current.revision} · {confirmed ? 'Confirmed snapshot' : 'Needs review'}</p></div><ShieldCheck /></div><DocumentUpload busy={!!busy} blocked={dirty || !!proposal} upload={data => run('upload-document',data)}/><ProfileEditor key={current.id} profile={profileEdit} busy={!!busy} dirty={dirty} confirmed={confirmed} canUndo={!!current.profile_undo} patch={patchProfile} undo={() => void run('undo-profile')} ask={message => void run('chat', {message})}/><div className="profile-footer"><button className="button subtle" disabled={!!busy || !dirty} onClick={() => void run('profile', { patch: { ...profileEdit, skills: profileEdit.skills.map(s => s.trim()).filter(Boolean), summary_facts: profileEdit.summary_facts.map(s => s.trim()).filter(Boolean) } })}>Save profile changes</button><label className="accept-label"><input type="checkbox" checked={accepted} disabled={!!busy || dirty} onChange={e => setAccepted(e.target.checked)}/>I reviewed every fact above and confirm it is accurate.</label><button className="button dark" disabled={!!busy || dirty || !accepted} onClick={() => void run('confirm', { accepted: true })}><ShieldCheck size={16}/>Confirm profile</button></div></section>
 <aside className="assistant-panel live-interview"><div className="assistant-heading"><span className="sparkle-icon"><Sparkles size={19}/></span><div><strong>Let’s tell your story.</strong><span>Live Gemini · review before writing</span></div></div><div className="conversation" aria-live="polite">{!current.messages.length && <div className="assistant-intro"><h3>Start with you.<br /><em>We’ll find the details.</em></h3><p>Tell me your education, skills, projects and the kind of role you want. I’ll propose wording for you to review before adding it.</p></div>}{current.messages.map((m, i) => <div className={`chat-message ${m.role}`} key={i}><strong>{m.role === 'user' ? 'You' : 'ProofCV'}</strong><p>{m.content}</p></div>)}{busy === 'chat' && <InterviewProgress message={message}/>}</div>{proposal && <ProposalReview key={proposal.id} proposal={proposal} dirty={dirty} error={error} profile={current.profile} busy={!!busy} review={(choice, patch, projectSkills) => void run('review-profile', { ...(projectSkills ? {project_skills: projectSkills} : {}), proposal_id: proposal.id, choice, ...(patch ? { patch } : {}) })} />}<form className="live-composer" onSubmit={e => { e.preventDefault(); void run('chat', { message }); }}><label htmlFor="introduction">Your message</label><textarea id="introduction" value={message} onChange={e => setMessage(e.target.value)} placeholder="I’m Parth, currently studying a Bachelor of AI…" rows={4} disabled={!!busy}/><button className="button dark" disabled={!!busy || !message.trim() || dirty || !!proposal}><MessageCircle size={15}/>Send to Gemini</button>{proposal && <p className="helper">Accept, edit or dismiss the suggestion above before continuing.</p>}{dirty && <p className="helper">Save your form edits before sending a message.</p>}</form><details className="tool-trace"><summary>Actual tool activity · {current.trace.length} steps</summary><p>Stopping condition: {current.stop_reason || 'Not run'}</p><pre>{JSON.stringify(current.trace, null, 2)}</pre></details></aside></div>}
 {page === 'jobs' && <div className="page-content"><div className="page-heading"><div><h2>Find your next chapter.</h2><p>Semantic retrieval across all nine supplied jobs. Similarity is not a probability of being hired.</p></div><button className="button dark" disabled={!!busy || !confirmed || dirty} onClick={() => void run('find-jobs')}><Target size={16}/>Ask agent to find jobs</button></div>{!confirmed && <div className="job-notice">Confirm your profile before retrieval.</div>}{current.retrieval && <><div className="job-notice"><ShieldCheck size={18}/>{current.retrieval.embedding_backend} · {current.retrieval.indexed_documents} embedded records · top three cosine matches</div><div className="jobs-grid">{current.retrieval.results.map((j, i) => <article className="job-card" key={j.document_id}><div className="job-card-top"><span className={`job-logo ${['mint', 'peach', 'lavender'][i]}`}>{i + 1}</span><span className="pill">Cosine {j.score.toFixed(3)}</span></div><h2>{j.title}</h2><p>{j.job.location}</p><code>{j.document_id}</code><div className="job-source"><span className="eyebrow">RETRIEVED EVIDENCE</span><blockquote>{j.excerpt}</blockquote></div><details><summary>Read the complete supplied job</summary><p>{j.job.description}</p></details><button className="button dark" disabled={!!busy} onClick={() => void run('generate', { job_id: j.document_id }, 'studio')}>Tailor my CV <ArrowUpRight size={15}/></button></article>)}</div><details className="tool-trace"><summary>Agent retrieval actions and observations</summary><p>Stopped: {current.stop_reason}</p><pre>{JSON.stringify(current.trace, null, 2)}</pre></details></>}</div>}
 {page === 'studio' && (draftEdit ? <><div className="studio-toolbar"><div className="document-name"><FileText /><div><strong>{draftEdit.profile.name}’s tailored CV</strong><span>{draftEdit.job.title} · Profile revision {draftEdit.revision}</span></div></div><button className="text-button" disabled={!!busy} onClick={() => void run('save')}><Save size={15}/>Save version</button></div>{(!confirmed || draftEdit.revision !== current.revision) && <p className="live-error">Save and confirm your profile to refresh this CV for the same job.</p>}<div className="studio-grid live-studio-layout"><section className="editor-panel"><div className="tabbar" role="tablist" aria-label="CV editor"><button type="button" role="tab" aria-selected={studioTab === 'content'} className={studioTab === 'content' ? 'selected' : ''} onClick={() => setStudioTab('content')}><FileText size={15}/>Content</button><button type="button" role="tab" aria-selected={studioTab === 'design'} className={studioTab === 'design' ? 'selected' : ''} onClick={() => setStudioTab('design')}><Menu size={15}/>Design</button></div><div className="editor-body"><div role="tabpanel" aria-label="Content" hidden={studioTab !== 'content'}><div className="studio-target"><span className="eyebrow">Your target role</span><button type="button" className="studio-role-button" onClick={() => setPage('jobs')}><span>{draftEdit.job.title}</span><Target size={16}/></button><small>Choose a target role from Discover jobs.</small></div><div className="studio-personal"><button type="button" className="studio-personal-heading" onClick={() => setPage('profile')}><span>01 · Personal details</span><ArrowUpRight size={16}/></button><button type="button" className="studio-personal-card" onClick={() => setPage('profile')}><span className="avatar">{draftEdit.profile.name.split(/\s+/).map(word => word[0]).slice(0,2).join('')}</span><span><strong>{draftEdit.profile.name}</strong><small>{draftEdit.profile.email}</small></span></button></div><label className="wide-label">Professional summary<textarea rows={10} value={draftEdit.summary} onChange={e => setDraftEdit({ ...draftEdit, summary: e.target.value })}/></label><p className="helper">Keep exact confirmed source paragraphs, separated by a blank line. For new wording, add a summary fact in your profile and reconfirm it.</p><div className="editor-section"><strong>Technical skills</strong><div className="skill-picker">{draftEdit.profile.skills.map(s => <button key={s} className={`skill ${draftEdit.selection.skills.includes(s) ? 'selected' : ''}`} onClick={() => setDraftEdit({ ...draftEdit, selection: { ...draftEdit.selection, skills: draftEdit.selection.skills.includes(s) ? draftEdit.selection.skills.filter(x => x !== s) : [...draftEdit.selection.skills, s] } })}>{s}</button>)}</div></div><div className="editor-section"><strong>Project emphasis</strong>{draftEdit.selection.project_order.map((i, pos) => <div className="order-item" key={i}><strong>{draftEdit.profile.projects[i].title}</strong><button className="icon-button" aria-label={`Move ${draftEdit.profile.projects[i].title} up`} disabled={pos === 0} onClick={() => { const order = [...draftEdit.selection.project_order]; [order[pos - 1], order[pos]] = [order[pos], order[pos - 1]]; setDraftEdit({ ...draftEdit, selection: { ...draftEdit.selection, project_order: order } }); }}>↑</button></div>)}</div></div><div role="tabpanel" aria-label="Design" hidden={studioTab !== 'design'}><DesignControls draft={draftEdit} setDraft={setDraftEdit}/><div className="swatches">{['#2c6554', '#343e67', '#292929', '#935345'].map(c => <button key={c} aria-label={`Use ${c} accent`} aria-pressed={draftEdit.accent === c} style={{ background: c }} onClick={() => setDraftEdit({ ...draftEdit, accent: c })}>{draftEdit.accent === c && <Check size={16}/>}</button>)}</div></div><button className="button dark" disabled={!!busy} onClick={() => void run('edit', { patch: { summary: draftEdit.summary, selection: draftEdit.selection, template: draftEdit.template, accent: draftEdit.accent, design: draftEdit.design }  })}>Validate & save edits</button><button className="text-button" disabled={!!busy || !current.undo} onClick={() => void run('undo')}><RotateCcw size={15}/>Undo last saved edit</button></div></section><section className="canvas-panel"><div className="canvas-top"><span><span className="live-dot"/>DOCUMENT PREVIEW</span><span>Save edits before export</span></div><div className="paper-scroll"><Paper draft={draftEdit}/></div></section><aside className="assistant-panel studio-guidance"><div className="assistant-heading"><Sparkles /><strong>A source behind the story.</strong></div><div className="assistant-body"><div className="suggestion-card"><span className="eyebrow">GEMINI’S EMPHASIS SUGGESTION</span><p>{draftEdit.selection.rationale}</p><span className="source-caption">{draftEdit.suggestion_note || `Shown in current draft · ${draftEdit.suggestion_status}`}</span><div className="suggestion-actions"><button className="button green" disabled={!!busy || draftEdit.suggestion_status === 'accepted'} onClick={() => void run('suggestion', { choice: 'accepted' })}>{draftEdit.suggestion_status === 'accepted' ? 'Accepted ✓' : 'Accept suggestion'}</button><button className="text-button" disabled={!!busy} onClick={() => void run('suggestion', { choice: 'dismissed' })}>Dismiss order</button></div><p className="helper">Dismiss restores source project and section order. Undo restores the prior draft. Edit selections in the content panel.</p></div><h3>Matched skills</h3>{draftEdit.analysis.matched.map(m => <details className="match-item" key={m.skill}><summary><Check size={13}/>{m.skill}</summary><p>Profile source: confirmed skills.</p><blockquote>{m.job_excerpt}</blockquote></details>)}<h3>Missing evidence</h3>{draftEdit.analysis.missing.map(m => <details className="match-item gap" key={m.requirement}><summary>{m.requirement}</summary><blockquote>{m.job_excerpt}</blockquote></details>)}<p className="helper">{draftEdit.analysis.limitation}</p><DesignControls draft={draftEdit} setDraft={setDraftEdit} sectionsOnly/><details className="tool-trace"><summary>Exact confirmed source facts</summary><pre>{JSON.stringify(draftEdit.profile, null, 2)}</pre></details></div></aside></div><div className="studio-chat-below"><CVChat workspace={current} error={error} busy={!!busy} send={message => void run('cv-chat', { message })} review={choice => void run('review-cv', {choice, proposal_id: current.pending_cv?.id})}/></div></> : <div className="empty-state"><FileText size={36}/><h2>Your first draft is waiting.</h2><p>Confirm your profile, retrieve three jobs and select a target role.</p><button className="button dark" onClick={() => setPage('jobs')}>Explore jobs</button></div>)}
 {page === 'history' && <div className="page-content"><div className="page-heading"><div><h2>A record of your progress.</h2><p>Saved snapshots stay with this workspace. Changing target jobs saves the outgoing draft.</p></div><button className="button dark" disabled={!!busy || !current.draft} onClick={() => void run('save')}><History size={16}/>Save current version</button></div><label className="wide-label">Compare current draft with<select value={compare} onChange={e => setCompare(e.target.value)}><option value="">Choose a saved version</option>{current.versions.map(v => <option key={v.id} value={v.id}>{v.draft.job.title} · {new Date(v.saved_at).toLocaleString()}</option>)}</select></label>{current.versions.find(v => v.id === compare) && current.draft && <><div className="diff-summary"><div><span>PROFILE SNAPSHOT</span><strong>{JSON.stringify(current.draft.profile) === JSON.stringify(current.versions.find(v => v.id === compare)!.draft.profile) ? 'Same confirmed facts' : 'Different revisions'}</strong></div><div><span>SUMMARY</span><strong>{current.draft.summary === current.versions.find(v => v.id === compare)!.draft.summary ? 'Unchanged' : 'Different emphasis'}</strong></div><div><span>SECTION ORDER</span><strong>{JSON.stringify(current.draft.selection.section_order) === JSON.stringify(current.versions.find(v => v.id === compare)!.draft.selection.section_order) ? 'Unchanged' : 'Changed'}</strong></div></div><div className="comparison-grid"><Paper draft={current.draft}/><Paper draft={current.versions.find(v => v.id === compare)!.draft}/></div></>}{current.versions.map(v => <div className="history-row" key={v.id}><FileText /><div><strong>{v.draft.job.title}</strong><span>{new Date(v.saved_at).toLocaleString()} · revision {v.draft.revision}</span></div><button className="text-button" disabled={!!busy} onClick={() => void run('restore', { version_id: v.id }, 'studio')}>Restore</button></div>)}{!current.versions.length && <div className="empty-state">Save a draft to start your version history.</div>}</div>}
 </>}<footer className="app-footer"><span>PROOFCV · CONFIRMED FACTS, THOUGHTFULLY PRESENTED</span><span>Local single-operator app · not authenticated accounts</span></footer></main></div></div>;
}
function EducationPreview({ value }: { value: string }) {
    return <>{educationEntries(value).map((entry, index) => {
        return <div className="studio-education" key={index}><div className="cv-line"><h4>{entry.degree}</h4>{entry.date && <span>{entry.date}</span>}</div>{entry.institution && <p>{entry.institution}</p>}</div>;
    })}</>;
}
function Paper({ draft }: {
    draft: Draft;
 }) {
     const p = draft.profile;
     const design: Design = { font: 'sans', size: 'standard', spacing: 'comfortable', header: 'center', skills: 'inline', page: 'auto', ats: false, visible_sections: ['projects', 'education', 'experience', 'achievements'], ...(draft.design || {}) };
     const sections = (design.visible_sections?.length ? design.visible_sections : draft.selection.section_order).filter(section => draft.selection.section_order.includes(section));
     return <article className={`cv-paper ${draft.template} cv-${design.font} cv-size-${design.size} cv-space-${design.spacing} cv-header-${design.header} cv-skills-${design.skills} ${design.ats ? 'cv-ats' : ''}`} style={{ '--cv-accent': draft.accent } as React.CSSProperties}>
        <header className="cv-header"><span className="cv-overline">CURRICULUM VITAE</span><h2>{p.name}</h2><div className="cv-contact">{[p.email,p.phone,p.location,p.linkedin,p.github,p.portfolio].filter(Boolean).map((value,i)=><span key={i}>{value}</span>)}</div></header>
         <section className="cv-section"><div className="cv-section-title"><h3>Profile</h3></div><p className="preserve-lines">{draft.summary}</p></section>
         <section className="cv-section"><div className="cv-section-title"><h3>Technical skills</h3></div><div className="cv-skills">{draft.selection.skills.map(s => <span key={s}>{s}</span>)}</div></section>
         {sections.map(section => (section === 'experience' || section === 'achievements') && ['none', 'no', 'n/a'].includes(p[section].toLowerCase()) ? null : <section className="cv-section" key={section}><div className="cv-section-title"><h3>{section}</h3></div>{section === 'projects' ? draft.selection.project_order.map(i => <div className="cv-project" key={i}><h4>{p.projects[i].title}</h4><p className="preserve-lines">{draft.project_excerpts?.[i]?.source === p.projects[i].description ? draft.project_excerpts[i].text : p.projects[i].description}</p>{p.projects[i].technologies && <p className="cv-technologies">{p.projects[i].technologies}</p>}</div>) : section === 'education' ? <EducationPreview value={p.education}/> : <p className="preserve-lines">{p[section as 'education' | 'experience' | 'achievements']}</p>}</section>)}
         <footer className="cv-footer"><span>{draft.job.title}</span><span>{draft.job.document_id}</span></footer>
     </article>;
 }

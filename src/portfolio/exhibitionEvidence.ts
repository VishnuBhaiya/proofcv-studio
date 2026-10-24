import type { Project,PublicSite,RoleView } from './types';

function mentions(text:string,skill:string){const escaped=skill.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');return new RegExp('(^|[^a-z0-9+#])'+escaped+'(?=$|[^a-z0-9+#])','i').test(text);}
export function exhibitEvidence(site:PublicSite,project:Project,view:RoleView){
 const profile=new Set(site.person.skills.map(s=>s.toLowerCase()));
 const skills=view.skills.filter(s=>profile.has(s.toLowerCase())&&mentions(project.description+' '+project.technologies,s));
 const assets=site.assets.filter(a=>a.project_id===project.id&&a.analysis);
 return {skills,assets,source:site.sources[project.id]||'',featured:view.project_ids.includes(project.id),viewTitle:view.title};
}
export type TourStop={kind:'intro'}|{kind:'project';projectId:string}|{kind:'experience'};
export function exhibitionTour(projects:Project[]):TourStop[]{return [{kind:'intro'},...projects.slice(0,3).map(project=>({kind:'project' as const,projectId:project.id})),{kind:'experience'}];}

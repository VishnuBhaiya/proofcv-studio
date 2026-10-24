import type { Project } from './types';

export function coverKind(project:Project){const text=(project.title+' '+project.technologies).toLowerCase();return /vision|detect|opencv|yolo|video/.test(text)?'vision':/data|sql|api|analytics/.test(text)?'systems':/web|html|react|website/.test(text)?'web':'notes';}
export function coverScene(project:Project){
 const title=project.title.toLowerCase();
 if(/solar|panel|photovoltaic/.test(title))return 'solar';
 if(/warehouse|safety|surveillance/.test(title))return 'warehouse';
 if(/intersection|traffic|vehicle/.test(title))return 'intersection';
 if(/news|sentiment|nlp|language/.test(title))return 'news';
 return coverKind(project);
}
// Stable identity, not list position: role reordering never swaps an illustration.
export function coverSeed(project:Project){let hash=2166136261;for(const c of project.id+'|'+project.title)hash=Math.imul(hash^c.charCodeAt(0),16777619);return hash>>>0;}
export const EXHIBIT_LABELS:Record<string,string>={intersection:'The intersection',warehouse:'The safety lab',solar:'The solar field',news:'The language desk',vision:'The vision lab',systems:'The data workshop',web:'The interface studio',notes:'The ideas archive'};

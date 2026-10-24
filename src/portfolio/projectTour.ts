import type { Project } from './types';

export type TourChapter={title:string;text:string;camera:number;start:number;end:number};
export const TOUR_SECONDS=36;
export function projectTour(project:Project):TourChapter[]{
 return [
  {title:'The project',text:project.description.trim()||'No project description is included in this profile.',camera:0,start:0,end:12},
  {title:'Tools & approach',text:project.technologies.trim()||'No technologies are listed for this project.',camera:1,start:12,end:24},
  {title:'Context & evidence',text:'This scene illustrates the project context. It is not footage of the working project. Open the case study for the confirmed description and any reviewed media.',camera:2,start:24,end:36}
 ];
}
export function tourChapterAt(time:number){return Math.max(0,Math.min(2,Math.floor((Number.isFinite(time)?time:0)/12)));}
export function isDemoPortfolio(name:string){return /\b(avery morgan|demo|synthetic|sample)\b/i.test(name);}
export function profileEntries(value:string){return value.split(/\n\s*\n/).map(s=>s.trim()).filter(s=>s&&!/^(none|no|n\/a)$/i.test(s));}

import type { Project } from './types';

// The scene is a symbolic exhibit, never a simulation or evidence of project results.
export const WORLD_LIMIT=6;
const POSITIONS:readonly [number,number,number][]=[[-4.4,.52,2.2],[0,.52,4.2],[4.4,.52,2.2],[-5,.52,-1.6],[4.8,.52,-1.7],[0,.52,-4.4]];
export function worldStations(projects:Project[]){return projects.slice(0,WORLD_LIMIT).map((project,index)=>({project,index,position:POSITIONS[index]}));}
export function stationIndex(value:number,count:number){return count?((Math.trunc(value)%count)+count)%count:-1;}
export function stationLabel(title:string,limit=25){return title.length>limit?title.slice(0,limit-1).trimEnd()+'…':title;}

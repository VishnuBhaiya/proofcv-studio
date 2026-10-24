import {useEffect,useState,type RefObject} from 'react';

/** Browser-owned fullscreen keeps the same canvas, camera and input controller. */
export default function SceneFullscreen({target,label}:{target:RefObject<HTMLElement|null>;label:string}){
 const [native,setNative]=useState(false),[expanded,setExpanded]=useState(false),[pending,setPending]=useState(false);
 const active=native||expanded;
 useEffect(()=>{
  const element=target.current;
  const change=()=>{setNative(document.fullscreenElement===element);setPending(false);};
  document.addEventListener('fullscreenchange',change);
  return()=>{document.removeEventListener('fullscreenchange',change);if(element&&document.fullscreenElement===element)void document.exitFullscreen().catch(()=>{});};
 },[target]);
 useEffect(()=>{
  const element=target.current;if(!expanded||!element)return;
  const container=element.closest('.pf-island,.pf-project-world'),overflow=document.body.style.overflow,previous=document.activeElement instanceof HTMLElement?document.activeElement:null;
  const attributes=['role','aria-modal','aria-label'].map(key=>[key,element.getAttribute(key)] as const);
  element.classList.add('pf-scene-expanded');container?.classList.add('pf-has-expanded-scene');document.body.style.overflow='hidden';
  element.setAttribute('role','dialog');element.setAttribute('aria-modal','true');element.setAttribute('aria-label',`${label} expanded view`);
  const keyboard=(event:KeyboardEvent)=>{
   if(event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();setExpanded(false);return;}
   if(event.key!=='Tab')return;
   const items=[...element.querySelectorAll<HTMLElement>('button:not(:disabled),select:not(:disabled),a[href],canvas[tabindex="0"]')].filter(item=>item.getClientRects().length);
   const first=items[0],last=items.at(-1);if(!first)return;
   if(event.shiftKey&&(document.activeElement===first||!element.contains(document.activeElement))){event.preventDefault();last?.focus();}
   else if(!event.shiftKey&&(document.activeElement===last||!element.contains(document.activeElement))){event.preventDefault();first.focus();}
  };
  document.addEventListener('keydown',keyboard,true);
  return()=>{document.removeEventListener('keydown',keyboard,true);element.classList.remove('pf-scene-expanded');container?.classList.remove('pf-has-expanded-scene');document.body.style.overflow=overflow;attributes.forEach(([key,value])=>value===null?element.removeAttribute(key):element.setAttribute(key,value));if(previous?.isConnected)previous.focus({preventScroll:true});};
 },[expanded,target,label]);
 async function toggle(){
  const element=target.current;if(!element||pending)return;
  if(expanded){setExpanded(false);return;}setPending(true);
  try{if(document.fullscreenElement===element)await document.exitFullscreen();else if(element.requestFullscreen)await element.requestFullscreen();else throw new Error('unavailable');}
  catch{setExpanded(true);}
  finally{setPending(false);}
 }
 return <div className="pf-scene-fullscreen"><button type="button" disabled={pending} aria-label={active?`Exit ${label} full screen`:`Open ${label} full screen`} aria-pressed={active} onClick={()=>void toggle()}>{active?'↙ Exit full screen':'⛶ Full screen'}</button></div>;
}

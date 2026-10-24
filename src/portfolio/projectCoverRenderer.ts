import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import type { Project } from './types';
import { createProjectEnvironment,projectShots,projectCameraGeometry,projectFogDensity } from './projectEnvironments';

type Preview={canvas:HTMLCanvasElement;scene:THREE.Scene;camera:THREE.PerspectiveCamera;subject:THREE.Box3;environment:ReturnType<typeof createProjectEnvironment>;visible:boolean;active:boolean;dirty:boolean;time:number;hover:number;pointer:number;onFailure:()=>void};
const previews=new Set<Preview>();
let renderer:THREE.WebGLRenderer|null=null,reflection:THREE.WebGLRenderTarget|null=null,frame=0,last=0,clock=0;

/** One shared WebGL context; covers render serially, never eight GPU engines. */
function getRenderer(){
 if(renderer)return renderer;
 renderer=new THREE.WebGLRenderer({alpha:false,antialias:true,powerPreference:'low-power'});
 renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();cancelAnimationFrame(frame);frame=0;for(const p of previews){p.visible=false;p.onFailure();}});
 renderer.setPixelRatio(1);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.15;
 try{const room=new RoomEnvironment(),pmrem=new THREE.PMREMGenerator(renderer);try{reflection=pmrem.fromScene(room,.08);}finally{room.dispose();pmrem.dispose();}}catch(error){renderer.dispose();renderer.forceContextLoss();renderer=null;throw error;}
 return renderer;
}
function disposeScene(p:Preview){const gs=new Set<THREE.BufferGeometry>(),ms=new Set<THREE.Material>(p.environment.materials);p.scene.traverse(o=>{if(o instanceof THREE.Mesh||o instanceof THREE.LineSegments){gs.add(o.geometry);for(const m of Array.isArray(o.material)?o.material:[o.material])ms.add(m);}});gs.forEach(g=>g.dispose());ms.forEach(m=>m.dispose());}
function tick(now:number){
 frame=0;if(!previews.size||document.hidden||document.querySelector('dialog.pf-project-world[open]'))return;
 const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
 if(!document.hidden&&now-last>=(reduced?250:65)){
  const dt=Math.min(.12,(now-(clock||now))/1000);clock=now;last=now;
  for(const p of previews){
   if(!p.visible||(!p.dirty&&(!p.active||reduced)))continue;
   const rect=p.canvas.getBoundingClientRect();if(rect.width<1||rect.height<1)continue;
   try{
    const r=getRenderer(),w=Math.min(1000,Math.round(rect.width)),h=Math.max(1,Math.round(w*rect.height/rect.width));
    const shot=projectShots(p.environment.kind)[0];p.camera.aspect=w/h;
    p.hover+=(p.pointer-p.hover)*.08;p.camera.position.set(...shot.position);p.camera.position.x+=p.hover*.6;p.camera.lookAt(new THREE.Vector3(...shot.target));p.camera.updateProjectionMatrix();
    if(p.scene.fog instanceof THREE.FogExp2)p.scene.fog.density=projectFogDensity(p.environment.palette.density,p.camera.position,p.subject);
    if(!reduced&&p.active)p.time+=dt;p.environment.animate(p.time);r.setSize(w,h,false);r.render(p.scene,p.camera);
    if(p.canvas.width!==w||p.canvas.height!==h){p.canvas.width=w;p.canvas.height=h;}
    const ctx=p.canvas.getContext('2d');if(!ctx)throw Error('Canvas unavailable');ctx.drawImage(r.domElement,0,0,w,h);p.dirty=false;
   }catch{p.visible=false;p.onFailure();}
  }
 }
 if([...previews].some(p=>p.visible&&(p.dirty||(!reduced&&p.active))))frame=requestAnimationFrame(tick);
}
function wake(){if(!frame)frame=requestAnimationFrame(tick);}

export function mountProjectCover(canvas:HTMLCanvasElement,project:Project,onFailure:()=>void){
 const environment=createProjectEnvironment(project,true),palette=environment.palette,scene=new THREE.Scene();
 scene.background=new THREE.Color(palette.sky);scene.fog=new THREE.FogExp2(palette.fog,palette.density);scene.add(environment.root);
 scene.add(new THREE.HemisphereLight('#edf3ff',palette.fog,2));const key=new THREE.DirectionalLight(palette.sun,3.2);key.position.set(-10,18,10);scene.add(key);const rim=new THREE.DirectionalLight(palette.accent,1.5);rim.position.set(10,8,-9);scene.add(rim);
 const p:Preview={canvas,scene,camera:new THREE.PerspectiveCamera(50,2,.1,250),subject:projectCameraGeometry(environment.root).subject,environment,visible:false,active:false,dirty:true,time:0,hover:0,pointer:0,onFailure};
 try{getRenderer();scene.environment=reflection!.texture;scene.environmentIntensity=.4;}catch{disposeScene(p);onFailure();return()=>{};}
 previews.add(p);
 const observer=new IntersectionObserver(entries=>{p.visible=entries[0]?.isIntersecting??false;p.dirty=true;wake();},{rootMargin:'80px'});observer.observe(canvas);
 const resize=new ResizeObserver(()=>{p.dirty=true;wake();});resize.observe(canvas);
 const move=(e:PointerEvent)=>{if(window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;const rect=canvas.getBoundingClientRect();p.pointer=((e.clientX-rect.left)/Math.max(1,rect.width)-.5)*2;p.dirty=true;wake();};
 const enter=()=>{p.active=true;p.dirty=true;clock=0;wake();};
 const leave=()=>{p.active=false;p.pointer=0;p.hover=0;p.dirty=true;wake();};
 const visibility=()=>{clock=0;p.dirty=true;if(!document.hidden)wake();};
 const owner=canvas.parentElement!,query=window.matchMedia('(prefers-reduced-motion: reduce)'),preference=()=>{p.dirty=true;wake();};
 canvas.addEventListener('pointermove',move);owner.addEventListener('pointerenter',enter);owner.addEventListener('pointerleave',leave);owner.addEventListener('focusin',enter);owner.addEventListener('focusout',leave);query.addEventListener('change',preference);document.addEventListener('visibilitychange',visibility);wake();
 return()=>{observer.disconnect();resize.disconnect();canvas.removeEventListener('pointermove',move);owner.removeEventListener('pointerenter',enter);owner.removeEventListener('pointerleave',leave);owner.removeEventListener('focusin',enter);owner.removeEventListener('focusout',leave);query.removeEventListener('change',preference);document.removeEventListener('visibilitychange',visibility);previews.delete(p);disposeScene(p);if(!previews.size){cancelAnimationFrame(frame);frame=0;reflection?.dispose();reflection=null;renderer?.dispose();renderer?.forceContextLoss();renderer=null;clock=0;}};
}

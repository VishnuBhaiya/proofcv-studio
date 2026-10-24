import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import type { Project } from './types';
import { worldStations } from './worldLayout';
import { createIsland } from './islandModels';
import { createProjectEnvironment,projectShots,fitProjectOverview,projectCameraGeometry,constrainProjectCamera,projectFogDensity } from './projectEnvironments';
import { cameraGesture,explorerGesture } from './worldInput';
import { createIslandAtmosphere,ISLAND_LIGHTING,type IslandLighting } from './islandAtmosphere';
import { createIslandExplorer } from './islandExplorer';
export type { IslandLighting } from './islandAtmosphere';

export type ExhibitionQuality='balanced'|'lite';
export type WorldMetrics={calls:number;triangles:number;fps:number};
type Options={project?:Project;onEscape?:()=>void;onInteract?:()=>void;onHover?:(index:number)=>void;onExploreChange?:(enabled:boolean)=>void;onFrame?:(canvas:HTMLCanvasElement)=>void;projects:Project[];motion:boolean;lighting?:IslandLighting;quality:ExhibitionQuality;onSelect:(index:number)=>void;onError:()=>void;onMetrics?:(value:WorldMetrics)=>void};
export type WorldEngine={focus:(index:number)=>void;rotate:(direction:number)=>void;zoom:(direction:number)=>void;highlight:(index:number)=>void;lighting:(mode:IslandLighting)=>void;explore:(enabled:boolean)=>void;step:(forward:number,right:number,pressed:boolean)=>void;motion:(enabled:boolean)=>void;dispose:()=>void};

const islandFrames=new WeakMap<THREE.Object3D,{points:THREE.Vector3[];frames:Map<number,{position:THREE.Vector3;target:THREE.Vector3;maxDistance:number}>}>();
/** Fit actual island surfaces, not the empty corners of rotated torus/mesh AABBs. */
export function islandHomeFrame(root:THREE.Object3D,aspect:number){
 aspect=Math.max(.2,aspect);let saved=islandFrames.get(root);
 if(!saved){
  root.updateMatrixWorld(true);const points:THREE.Vector3[]=[];
  root.traverse(object=>{if(!(object instanceof THREE.Mesh))return;const positions=object.geometry.getAttribute('position');if(!positions)return;for(let n=0;n<positions.count;n++)points.push(new THREE.Vector3().fromBufferAttribute(positions,n).applyMatrix4(object.matrixWorld));});
  saved={points,frames:new Map()};islandFrames.set(root,saved);
 }
 const key=Math.round(aspect*10000),cached=saved.frames.get(key);
 if(cached)return {position:cached.position.clone(),target:cached.target.clone(),maxDistance:cached.maxDistance};
 const points=saved.points,bounds=new THREE.Box3().setFromPoints(points),target=bounds.getCenter(new THREE.Vector3());
 const camera=new THREE.PerspectiveCamera(32,aspect,.1,500),direction=new THREE.Vector3(11.5,9.5,13.8).sub(target).normalize(),point=new THREE.Vector3();
 const extent=(distance:number)=>{
  camera.position.copy(target).addScaledVector(direction,distance);camera.lookAt(target);camera.updateMatrixWorld();
  let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity,clipped=false;
  for(const p of points){point.copy(p).project(camera);minX=Math.min(minX,point.x);maxX=Math.max(maxX,point.x);minY=Math.min(minY,point.y);maxY=Math.max(maxY,point.y);clipped||=point.z< -1||point.z>1;}
  return {minX,maxX,minY,maxY,clipped};
 };
 let distance=25;
 for(let pass=0;pass<4;pass++){
  let near=.5,far=Math.max(30,bounds.getSize(new THREE.Vector3()).length()*2);
  for(let n=0;n<22;n++){const mid=(near+far)/2,e=extent(mid);if(!e.clipped&&e.maxX-e.minX<=1.64&&e.maxY-e.minY<=1.64)far=mid;else near=mid;}
  distance=far;const e=extent(distance),scale=distance*Math.tan(THREE.MathUtils.degToRad(16));
  // Centre the real projected silhouette: the low broad platform and tall roof are asymmetric.
  const right=new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld,0),up=new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld,1);
  target.addScaledVector(right,(e.minX+e.maxX)/2*scale*aspect).addScaledVector(up,(e.minY+e.maxY)/2*scale);
 }
 const position=target.clone().addScaledVector(direction,distance),result={position,target,maxDistance:Math.max(38,distance*1.15)};
 saved.frames.set(key,result);return {position:position.clone(),target:target.clone(),maxDistance:result.maxDistance};
}

/** Original locally bundled exhibition. All miniature scenes are illustrative. */
export function createWorld(host:HTMLElement,options:Options):WorldEngine {
 const lite=options.quality==='lite',scene=new THREE.Scene();
 scene.fog=new THREE.FogExp2(options.project?'#101824':'#11132e',options.project ? .009 : .015);
 const renderer=new THREE.WebGLRenderer({alpha:true,antialias:!lite,powerPreference:'low-power'});
 let reflection:THREE.WebGLRenderTarget|null=null;
 let composer:EffectComposer|null=null;const passes:{dispose:()=>void}[]=[],cleanups:(()=>void)[]=[];
 function disposeComposition(){passes.splice(0).forEach(p=>p.dispose());composer?.dispose();composer=null;}
 function releaseInteractions(){cleanups.splice(0).forEach(cleanup=>cleanup());}
 try {
 renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,lite?1:1.5));
 renderer.setClearColor('#0b1420',0);renderer.outputColorSpace=THREE.SRGBColorSpace;
 renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=options.project?1.25:1.35;
 renderer.shadowMap.enabled=!lite;renderer.shadowMap.type=THREE.PCFShadowMap;
 host.appendChild(renderer.domElement);
 const canvas=renderer.domElement;canvas.tabIndex=0;
 const orbitDescription=options.project?'Cinematic project world. Two fingers or drag to orbit; pinch to zoom. Arrow keys rotate. Home resets. Escape returns to the island.':'Living Exhibition. Purple floating-island tour. Two fingers or drag to orbit; pinch to zoom. Select a console to enter its separate project world. Scroll outside the scene to read.';
 canvas.setAttribute('aria-label',orbitDescription);
 const camera=new THREE.PerspectiveCamera(options.project?50:32,1,.1,500);
 const controls=new OrbitControls(camera,canvas);cleanups.push(()=>controls.dispose());controls.target.set(0,options.project?1.5:.5,0);controls.enableDamping=true;controls.dampingFactor=.085;
 controls.enablePan=false;controls.enableZoom=true;controls.minPolarAngle=.15;controls.maxPolarAngle=Math.PI/2-(options.project?.025:.12);
 controls.minDistance=options.project?2.5:4.5;controls.maxDistance=options.project?120:38;
 scene.add(new THREE.AmbientLight(options.project?'#b5c7df':'#b5b3ff',options.project?1.5:.8),new THREE.HemisphereLight(options.project?'#edf5ff':'#e3ecff',options.project?'#302a36':'#291c5a',options.project?2:1.7));
 const key=new THREE.DirectionalLight('#fff0d9',4);key.position.set(-3,13,9);key.castShadow=!lite;
 key.shadow.mapSize.set(1024,1024);Object.assign(key.shadow.camera,{left:-22,right:22,top:22,bottom:-22,near:.1,far:70});key.shadow.bias=-.0005;scene.add(key);
 const rim=new THREE.DirectionalLight('#789dff',3);rim.position.set(8,7,-8);scene.add(rim);
 const fill=new THREE.DirectionalLight('#d7a4ef',1.4);fill.position.set(-9,4,-1);scene.add(fill);
 const stations=worldStations(options.projects);
 const island=options.project?null:createIsland(options.projects,lite);
 const atmosphere=island?createIslandAtmosphere(lite):null,explorer=island?createIslandExplorer(island.root):null;
 if(atmosphere)scene.add(atmosphere.root);
 const environment=options.project?createProjectEnvironment(options.project,lite):null;
 if(environment){
  const palette=environment.palette;scene.background=new THREE.Color(palette.sky);scene.fog=new THREE.FogExp2(palette.fog,palette.density);
  key.color.set(palette.sun);key.intensity=3.2;key.position.set(-10,18,10);rim.color.set(palette.accent);rim.intensity=1.3;fill.intensity=.55;
  const room=new RoomEnvironment(),pmrem=new THREE.PMREMGenerator(renderer);reflection=pmrem.fromScene(room,.06);scene.environment=reflection.texture;scene.environmentIntensity=.45;room.dispose();pmrem.dispose();
 }
 if(island&&!lite){const room=new RoomEnvironment(),pmrem=new THREE.PMREMGenerator(renderer);try{reflection=pmrem.fromScene(room,.07);scene.environment=reflection.texture;scene.environmentIntensity=.32;}catch{reflection?.dispose();reflection=null;scene.environment=null;}finally{room.dispose();pmrem.dispose();}}
 scene.add((island?.root||environment!.root));
 const groups=island?.groups||[],movingParts=island?.moving||environment!.moving,rims=island?.rims||[],textures=island?.textures||[];
 const extraMaterials=[...(island?.materials||environment!.materials),...(atmosphere?.materials||[])];
 if(island&&!lite){try{composer=new EffectComposer(renderer);const render=new RenderPass(scene,camera),bloom=new UnrealBloomPass(new THREE.Vector2(1,1),.24,.5,1.55),output=new OutputPass();passes.push(render,bloom,output);composer.addPass(render);composer.addPass(bloom);composer.addPass(output);composer.setPixelRatio(Math.min(1.25,renderer.getPixelRatio()));renderer.info.autoReset=false;}catch{disposeComposition();renderer.info.autoReset=true;}}
 if(!options.project){const cyan=new THREE.PointLight('#27d9ff',32,18,2);cyan.position.set(3,3.5,0);scene.add(cyan);const pink=new THREE.PointLight('#ff58d9',23,15,2);pink.position.set(-4,3,1);scene.add(pink);}
 const shots=projectShots(environment?.kind||'notes');
 let disposed=false,visible=true,dirty=true,moving=options.motion,userMoved=false,exploring=false,hovered=-1,selected=-1,lastFrame=0,elapsed=0,frames=0,sampleStart=performance.now();
 const keys=new Set<string>(),steps=new Set<string>();
 const setLighting=(mode:IslandLighting)=>{if(!island)return;const p=ISLAND_LIGHTING[mode];key.color.set(p.key);key.intensity=mode==='midnight'?2.2:3.1;rim.color.set(p.rim);rim.intensity=mode==='midnight'?2:1.7;fill.intensity=.75;renderer.toneMappingExposure=p.exposure;if(scene.fog instanceof THREE.FogExp2){scene.fog.color.set(p.fog);scene.fog.density=.009;}atmosphere?.lighting(mode);dirty=true;};
 if(island)setLighting(options.lighting||'twilight');
 const highlight=(index:number)=>{if(index===hovered)return;hovered=index;dirty=true;options.onHover?.(index);};
 let flight:{from:THREE.Vector3;to:THREE.Vector3;fromTarget:THREE.Vector3;target:THREE.Vector3;start:number}|null=null;
 const cameraGeometry=environment?projectCameraGeometry(environment.root):null,projectBounds=cameraGeometry?.subject||null;
 const lastSafePosition=new THREE.Vector3();let cameraReady=false;
 function cutTo(position:THREE.Vector3,target:THREE.Vector3){
  // Flush a previous drag's damping before applying a selected shot. Otherwise the next
  // animation frame continues that drag and can pull the camera back into a shelf.
  const damping=controls.enableDamping;controls.enableDamping=false;controls.update();
  camera.position.copy(position);controls.target.copy(target);controls.update();controls.enableDamping=damping;
  lastSafePosition.copy(camera.position);cameraReady=true;
 }
 function enforceCamera(){if(!cameraGeometry)return;if(cameraReady&&camera.position.distanceToSquared(lastSafePosition)<1e-12)return;if(cameraReady)camera.position.copy(constrainProjectCamera(lastSafePosition,camera.position,cameraGeometry.solids));lastSafePosition.copy(camera.position);cameraReady=true;camera.lookAt(controls.target);}
 function updateFog(){if(environment&&projectBounds&&scene.fog instanceof THREE.FogExp2)scene.fog.density=projectFogDensity(environment.palette.density,camera.position,projectBounds);}
 const homeFrame=()=>islandHomeFrame(island!.root,camera.aspect);
 const home=()=>{if(options.project)return new THREE.Vector3(...shots[0].position);const frame=homeFrame();controls.maxDistance=frame.maxDistance;return frame.position;};
 const focus=(index:number)=>{
  selected=index;userMoved=false;const station=options.project?null:stations[index],shot=shots[Math.max(0,Math.min(2,index))];
  if(exploring&&explorer){if(index<0){explorer.reset();explorer.apply(camera);}dirty=true;return;}
  const target=options.project?new THREE.Vector3(...shot.target):station?new THREE.Vector3(...station.position).add(new THREE.Vector3(0,1,0)):homeFrame().target;
  const to=options.project?(index===2&&projectBounds?fitProjectOverview(projectBounds,camera.aspect,new THREE.Vector3(...shot.position),target):new THREE.Vector3(...shot.position)):station?target.clone().add(new THREE.Vector3(station.position[0]*.35+5,4.7,7)):home();
  // A straight animated flight between interior shots crosses solid racks and walls.
  // Project shots are deliberate cinematic cuts; manual orbit/zoom is collision-constrained.
  if(moving&&!options.project)flight={from:camera.position.clone(),to,fromTarget:controls.target.clone(),target,start:performance.now()};
  else{cutTo(to,target);flight=null;}
  dirty=true;
 };
 const raycaster=new THREE.Raycaster(),pointer=new THREE.Vector2();let down:[number,number]|null=null,lastPointer:[number,number]|null=null,dragTravel=0;
 const clearMovement=()=>{keys.clear();steps.clear();};
 let explorationTrigger:HTMLElement|null=null;
 const setExplore=(enabled:boolean)=>{if(!explorer||enabled===exploring)return;clearMovement();flight=null;down=null;lastPointer=null;dragTravel=0;highlight(-1);exploring=enabled;controls.enabled=!enabled;camera.fov=enabled?58:32;camera.updateProjectionMatrix();canvas.setAttribute('aria-label',enabled?'Island explorer. Two-finger vertical scroll walks. Horizontal swipe turns. Shift and scroll sidesteps. Drag to look freely. Pinch to step. W A S D or arrow keys also walk. Home returns to the entry. Escape returns to orbit view.':orbitDescription);if(enabled){explorationTrigger=document.activeElement instanceof HTMLElement?document.activeElement:null;explorer.reset();explorer.apply(camera);userMoved=true;canvas.focus({preventScroll:true});}else{selected=-1;userMoved=false;cutTo(home(),homeFrame().target);if(document.activeElement===canvas&&explorationTrigger?.isConnected)explorationTrigger.focus({preventScroll:true});}options.onExploreChange?.(enabled);dirty=true;};
 function hit(event:PointerEvent){const rect=canvas.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);const hits=raycaster.intersectObjects(groups,true);if(!hits.length)return -1;let object:THREE.Object3D|null=hits[0].object;while(object&&object.userData.index===undefined)object=object.parent;return typeof object?.userData.index==='number'?object.userData.index:-1;}
 const onDown=(event:PointerEvent)=>{down=[event.clientX,event.clientY];lastPointer=down;dragTravel=0;highlight(-1);if(exploring){canvas.focus({preventScroll:true});canvas.setPointerCapture(event.pointerId);}};
 const onCancel=()=>{down=null;lastPointer=null;dragTravel=0;highlight(-1);};
 const onUp=(event:PointerEvent)=>{const clicked=down&&dragTravel<=6&&Math.hypot(event.clientX-down[0],event.clientY-down[1])<=6;down=null;lastPointer=null;dragTravel=0;if(!clicked)return;const index=hit(event);if(index>=0&&!options.project)options.onSelect(index);};
 const onMove=(event:PointerEvent)=>{if(down){if(lastPointer){const dx=event.clientX-lastPointer[0],dy=event.clientY-lastPointer[1];dragTravel+=Math.hypot(dx,dy);if(exploring&&explorer){explorer.turn(dx,dy);explorer.apply(camera);dirty=true;}lastPointer=[event.clientX,event.clientY];}return;}if(!options.project){const index=hit(event);canvas.style.cursor=index>=0?'pointer':'grab';highlight(index);}};
 const onLeave=()=>{highlight(-1);if(!exploring)onCancel();};
 const blur=()=>{clearMovement();onCancel();};
 const interact=()=>{options.onInteract?.();flight=null;userMoved=true;dirty=true;};
 const onStart=()=>{interact();},onChange=()=>{dirty=true;};
 controls.addEventListener('start',onStart);controls.addEventListener('change',onChange);
 cleanups.push(()=>{controls.removeEventListener('start',onStart);controls.removeEventListener('change',onChange);});
 const rotate=(direction:number)=>{interact();if(exploring&&explorer){explorer.turn(direction*60,0);explorer.apply(camera);return;}const offset=camera.position.clone().sub(controls.target);offset.applyAxisAngle(new THREE.Vector3(0,1,0),direction*.23);camera.position.copy(controls.target).add(offset);controls.update();enforceCamera();dirty=true;};
 const zoom=(direction:number)=>{interact();if(exploring&&explorer){for(let n=0;n<4;n++)explorer.move(direction>0?1:-1,0,.05);explorer.apply(camera);return;}const offset=camera.position.clone().sub(controls.target);offset.setLength(THREE.MathUtils.clamp(offset.length()*(direction>0?.85:1.18),controls.minDistance,controls.maxDistance));camera.position.copy(controls.target).add(offset);controls.update();enforceCamera();dirty=true;};
 const keyboard=(event:KeyboardEvent)=>{const code=event.key.toLowerCase();if(exploring&&['w','a','s','d','arrowleft','arrowright','arrowup','arrowdown'].includes(code)){event.preventDefault();keys.add(code);dirty=true;return;}if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','Escape'].includes(event.key)){event.preventDefault();if(event.key==='Escape'){if(options.onEscape)options.onEscape();else if(exploring)setExplore(false);else canvas.blur();}else if(event.key==='Home'){interact();if(options.project){options.onSelect(0);focus(0);}else options.onSelect(-1);}else if(event.key==='ArrowLeft'||event.key==='ArrowRight')rotate(event.key==='ArrowLeft'?-1:1);else zoom(event.key==='ArrowUp'?1:-1);}};
 const keyup=(event:KeyboardEvent)=>{keys.delete(event.key.toLowerCase());};
 const wheel=(event:WheelEvent)=>{
  event.stopImmediatePropagation();if(!event.cancelable)return;event.preventDefault();interact();
  if(exploring&&explorer){const gesture=explorerGesture(event,host.clientHeight);explorer.turn(gesture.yaw/.003,0);explorer.travel(gesture.forward,gesture.right);explorer.apply(camera);dirty=true;return;}
  const gesture=cameraGesture(event,host.clientHeight),offset=camera.position.clone().sub(controls.target),spherical=new THREE.Spherical().setFromVector3(offset);
  spherical.theta+=gesture.azimuth;spherical.phi=THREE.MathUtils.clamp(spherical.phi+gesture.elevation,controls.minPolarAngle,controls.maxPolarAngle);spherical.radius=THREE.MathUtils.clamp(spherical.radius*gesture.zoom,controls.minDistance,controls.maxDistance);
  camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(spherical));controls.update();enforceCamera();dirty=true;
 };
 canvas.addEventListener('wheel',wheel,{passive:false,capture:true});canvas.addEventListener('pointerdown',onDown);canvas.addEventListener('pointerup',onUp);canvas.addEventListener('pointercancel',onCancel);canvas.addEventListener('pointermove',onMove);canvas.addEventListener('pointerleave',onLeave);canvas.addEventListener('keydown',keyboard);canvas.addEventListener('keyup',keyup);canvas.addEventListener('blur',blur);window.addEventListener('blur',blur);
 const onVisibility=()=>{if(document.hidden)blur();lastFrame=performance.now();dirty=true;};document.addEventListener('visibilitychange',onVisibility);
 cleanups.push(()=>{clearMovement();canvas.removeEventListener('pointerdown',onDown);canvas.removeEventListener('pointerup',onUp);canvas.removeEventListener('pointercancel',onCancel);canvas.removeEventListener('pointermove',onMove);canvas.removeEventListener('pointerleave',onLeave);canvas.removeEventListener('keydown',keyboard);canvas.removeEventListener('keyup',keyup);canvas.removeEventListener('blur',blur);window.removeEventListener('blur',blur);document.removeEventListener('visibilitychange',onVisibility);canvas.removeEventListener('wheel',wheel,true);});
 const onLost=(event:Event)=>{event.preventDefault();options.onError();};canvas.addEventListener('webglcontextlost',onLost);
 cleanups.push(()=>canvas.removeEventListener('webglcontextlost',onLost));
 const resize=()=>{const w=Math.max(1,host.clientWidth),h=Math.max(1,host.clientHeight);camera.aspect=w/h;camera.updateProjectionMatrix();renderer.setSize(w,h,false);composer?.setSize(w,h);if(exploring){explorer?.apply(camera);}else if(!userMoved&&options.project&&selected===2&&!flight){cutTo(fitProjectOverview(projectBounds!,camera.aspect,new THREE.Vector3(...shots[2].position),new THREE.Vector3(...shots[2].target)),new THREE.Vector3(...shots[2].target));}else if(!userMoved&&(selected<0||(options.project&&selected===0))&&!flight){cutTo(home(),options.project?new THREE.Vector3(...shots[0].target):homeFrame().target);}dirty=true;};
 const observer=new ResizeObserver(resize);cleanups.push(()=>observer.disconnect());observer.observe(host);resize();
 const visibility=new IntersectionObserver(entries=>{visible=entries[0]?.isIntersecting??false;if(!visible)clearMovement();lastFrame=performance.now();dirty=true;frames=0;sampleStart=performance.now();});cleanups.push(()=>visibility.disconnect());visibility.observe(host);
 const tick=(time:number)=>{
  if(disposed||!visible||document.hidden)return;const delta=Math.min((time-lastFrame)/1000,.08);lastFrame=time;
  if(flight){const t=THREE.MathUtils.clamp((time-flight.start)/950,0,1),ease=1-Math.pow(1-t,3);camera.position.lerpVectors(flight.from,flight.to,ease);controls.target.lerpVectors(flight.fromTarget,flight.target,ease);dirty=true;if(t===1)flight=null;}
  if(exploring&&explorer){const has=(a:string,b:string)=>keys.has(a)||keys.has(b);let forward=Number(has('w','arrowup'))-Number(has('s','arrowdown')),right=Number(has('d','arrowright'))-Number(has('a','arrowleft'));for(const value of steps){const [f,r]=value.split(',').map(Number);forward+=f;right+=r;}if(explorer.move(forward,right,delta)){explorer.apply(camera);dirty=true;}}else{controls.update();enforceCamera();}
  if(moving){elapsed+=delta;if(environment)environment.animate(elapsed);else{movingParts.forEach((part,i)=>{part.rotation.y+=delta*(i===0?.2:1.1);});atmosphere?.update(elapsed);}dirty=true;}
  if(dirty){rims.forEach((part,i)=>{const s=i===hovered||i===selected?1.08:1;part.scale.set(s,s,1);});updateFog();if(composer){renderer.info.reset();composer.render();}else renderer.render(scene,camera);try{options.onFrame?.(canvas);}catch{/* Optional recording must never interrupt the portfolio. */}dirty=false;frames++;}
  if(time-sampleStart>=2000){options.onMetrics?.({calls:renderer.info.render.calls,triangles:renderer.info.render.triangles,fps:Math.round(frames*1000/(time-sampleStart))});frames=0;sampleStart=time;}
 };
 renderer.setAnimationLoop(tick);
 return {focus,rotate,zoom,highlight,lighting:setLighting,explore:setExplore,step(forward,right,pressed){const key=Math.sign(forward)+','+Math.sign(right);if(pressed&&exploring){steps.add(key);dirty=true;}else steps.delete(key);},motion(enabled){moving=enabled;if(!enabled){clearMovement();highlight(-1);}if(!enabled&&flight){camera.position.copy(flight.to);controls.target.copy(flight.target);controls.update();flight=null;}dirty=true;},dispose(){
  if(disposed)return;disposed=true;renderer.setAnimationLoop(null);releaseInteractions();
  const geometries=new Set<THREE.BufferGeometry>(),materials=new Set<THREE.Material>(extraMaterials);
  scene.traverse(object=>{if(object instanceof THREE.Mesh||object instanceof THREE.Points||object instanceof THREE.LineSegments){geometries.add(object.geometry);for(const mat of Array.isArray(object.material)?object.material:[object.material])materials.add(mat);}});
  geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());disposeComposition();reflection?.dispose();renderer.dispose();renderer.forceContextLoss();canvas.remove();
 }};
 }catch(error){
  // A partial construction must not leave a hidden canvas/GPU allocation behind.
  renderer.setAnimationLoop(null);releaseInteractions();
  const geometries=new Set<THREE.BufferGeometry>(),materials=new Set<THREE.Material>(),maps=new Set<THREE.Texture>();
  scene.traverse(object=>{if(object instanceof THREE.Mesh||object instanceof THREE.Points||object instanceof THREE.LineSegments){geometries.add(object.geometry);for(const material of Array.isArray(object.material)?object.material:[object.material]){materials.add(material);for(const value of Object.values(material))if(value instanceof THREE.Texture)maps.add(value);}}});
  geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());maps.forEach(t=>t.dispose());disposeComposition();reflection?.dispose();renderer.dispose();renderer.forceContextLoss();renderer.domElement.remove();throw error;
 }
}

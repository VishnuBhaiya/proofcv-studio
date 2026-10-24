// Real createWorld/controller integration with CPU Three.js geometry and fake rendering/DOM.
// This is not a browser screenshot, GPU benchmark, or live project demonstration.
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import ts from 'typescript';
import * as THREE from 'three';

const originals=Object.fromEntries(['document','window','HTMLElement','ResizeObserver','IntersectionObserver','performance'].map(k=>[k,Object.getOwnPropertyDescriptor(globalThis,k)]));
let clock=1000,count=0;
const renderers=[],controls=[],observers=[],composers=[],passes=[],targets=[];
const faults={resize:false};
class TrackedTarget extends EventTarget{
 listeners=new Map();
 addEventListener(type,callback,options){super.addEventListener(type,callback,options);if(!this.listeners.has(type))this.listeners.set(type,new Set());this.listeners.get(type).add(callback);}
 removeEventListener(type,callback,options){super.removeEventListener(type,callback,options);this.listeners.get(type)?.delete(callback);}
 get listenerCount(){return [...this.listeners.values()].reduce((sum,set)=>sum+set.size,0);}
}
class Element extends TrackedTarget{
 style={};children=[];parentNode=null;isConnected=true;clientWidth=1000;clientHeight=550;attributes=new Map();
 setAttribute(k,v){this.attributes.set(k,v);}
 appendChild(child){child.parentNode=this;this.children.push(child);return child;}
 remove(){if(this.parentNode)this.parentNode.children=this.parentNode.children.filter(c=>c!==this);this.parentNode=null;this.isConnected=false;}
 focus(){const previous=document.activeElement;if(previous===this)return;document.activeElement=this;previous?.dispatchEvent(new Event('blur'));}
 blur(){if(document.activeElement===this)document.activeElement=null;this.dispatchEvent(new Event('blur'));}
 setPointerCapture(){}
 getBoundingClientRect(){return {left:0,top:0,width:this.clientWidth,height:this.clientHeight};}
 getContext(){return {fillRect(){},strokeRect(){},fillText(){}};}
}
class FakeDocument extends TrackedTarget{hidden=false;activeElement=null;createElement(){return new Element();}}
const document=new FakeDocument(),window=new TrackedTarget();window.devicePixelRatio=1;
class Observer{
 constructor(callback){this.callback=callback;this.disconnected=false;observers.push(this);}
 observe(target){this.target=target;}
 disconnect(){this.disconnected=true;}
}
class Renderer{
 constructor(){this.domElement=new Element();this.shadowMap={};this.info={autoReset:true,render:{calls:0,triangles:0},reset:()=>{this.info.render.calls=0;this.info.render.triangles=0;}};this.pixelRatio=1;this.disposed=false;this.lost=false;renderers.push(this);}
 setPixelRatio(value){this.pixelRatio=value;}
 getPixelRatio(){return this.pixelRatio;}
 setClearColor(){}
 setSize(w,h){if(faults.resize)throw new Error('TEST_ONLY_RESIZE_FAILURE');this.size=[w,h];}
 setAnimationLoop(callback){this.loop=callback;}
 render(scene,camera){this.scene=scene;this.camera=camera;scene.updateMatrixWorld(true);camera.updateMatrixWorld();if(this.info.autoReset)this.info.reset();this.info.render.calls++;this.info.render.triangles+=123;this.renders=(this.renders||0)+1;}
 dispose(){this.disposed=true;}
 forceContextLoss(){this.lost=true;}
}
class Controls extends THREE.EventDispatcher{
 constructor(camera,canvas){super();this.camera=camera;this.canvas=canvas;this.target=new THREE.Vector3();this.enabled=true;this.disposed=false;controls.push(this);}
 update(){this.camera.lookAt(this.target);this.camera.updateMatrixWorld();}
 dispose(){this.disposed=true;}
}
class Room extends THREE.Scene{dispose(){this.disposed=true;}}
class PMREM{fromScene(){const target={texture:new THREE.Texture(),disposed:false,dispose(){this.disposed=true;}};targets.push(target);return target;}dispose(){}}
class Pass{constructor(scene,camera){this.scene=scene;this.camera=camera;this.disposed=false;passes.push(this);}dispose(){this.disposed=true;}}
class Composer{
 constructor(renderer){this.renderer=renderer;this.passes=[];this.disposed=false;composers.push(this);}
 addPass(pass){this.passes.push(pass);}
 setPixelRatio(value){this.pixelRatio=value;}
 setSize(w,h){this.size=[w,h];}
 render(){const p=this.passes[0];this.renderer.render(p.scene,p.camera);this.renderer.info.render.calls+=2;this.renderer.info.render.triangles+=4;}
 dispose(){this.disposed=true;}
}
const mockKey='__proofcv_island_simulator_test__';
globalThis[mockKey]={Renderer,Controls,Room,PMREM,Pass,Composer};
for(const [key,value] of Object.entries({document,window,HTMLElement:Element,ResizeObserver:Observer,IntersectionObserver:Observer,performance:{now:()=>clock}}))Object.defineProperty(globalThis,key,{value,writable:true,configurable:true});
const data=source=>'data:text/javascript;base64,'+Buffer.from(source).toString('base64');
const mockRef=`globalThis[${JSON.stringify(mockKey)}]`,threeURL=data(`export * from ${JSON.stringify(import.meta.resolve('three'))};export const WebGLRenderer=${mockRef}.Renderer;export const PMREMGenerator=${mockRef}.PMREM;`);
const addons={OrbitControls:'Controls',RoomEnvironment:'Room',EffectComposer:'Composer',RenderPass:'Pass',UnrealBloomPass:'Pass',OutputPass:'Pass'},cache=new Map();
async function moduleURL(name){
 if(cache.has(name))return cache.get(name);
 let output=ts.transpileModule(await readFile(new URL('../src/portfolio/'+name+'.ts',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;
 for(const match of [...output.matchAll(/from ['"]([^'"]+)['"]/g)]){
  const spec=match[1],addon=Object.keys(addons).find(key=>spec.endsWith('/'+key+'.js'));
  const url=spec==='three'?threeURL:addon?data(`export const ${addon}=${mockRef}.${addons[addon]};`):spec.startsWith('./')?await moduleURL(spec.slice(2)):import.meta.resolve(spec);
  output=output.replaceAll(match[0],'from '+JSON.stringify(url));
 }
 const url=data(output);cache.set(name,url);return url;
}
function emit(target,type,properties={}){const event=new Event(type,{cancelable:true});for(const [key,value] of Object.entries(properties))Object.defineProperty(event,key,{value});target.dispatchEvent(event);return event;}
function test(name,run){run();count++;console.log('PASS '+name);}
function frames(renderer,n=1){for(let i=0;i<n;i++){clock+=16;renderer.loop?.(clock);}}
const fixture={id:'simulator-geometry-fixture',title:'Intersection detection',description:'Synthetic test geometry only.',technologies:'Python'};
let current=null;
try{
 const {createWorld,islandHomeFrame}=await import(await moduleURL('worldEngine'));
 const {createIslandAtmosphere,ISLAND_LIGHTING}=await import(await moduleURL('islandAtmosphere'));
 function setup(quality='lite',motion=false){const host=new Element(),trigger=new Element(),changes=[],hoverChanges=[],selections=[];trigger.focus();const engine=createWorld(host,{projects:[fixture],quality,motion,onSelect:index=>selections.push(index),onError(){},onHover:value=>hoverChanges.push(value),onExploreChange:value=>changes.push(value)}),renderer=renderers.at(-1);frames(renderer);current={engine,renderer,host,trigger,changes,hoverChanges,selections,canvas:renderer.domElement};return current;}
 function clean(){current?.engine.dispose();current=null;}
 test('Entering Explore immediately focuses its canvas and switches to eye-level FOV',()=>{const {engine,canvas,renderer,changes}=setup();engine.explore(true);frames(renderer);assert.equal(document.activeElement,canvas);assert.equal(renderer.camera.fov,58);assert.equal(renderer.camera.position.y,2.05);assert.deepEqual(changes,[true]);clean();});
 test('Held WASD moves the real camera and key release stops it',()=>{const {engine,canvas,renderer}=setup();engine.explore(true);frames(renderer);const start=renderer.camera.position.clone();assert.equal(emit(canvas,'keydown',{key:'w'}).defaultPrevented,true);frames(renderer,10);assert.ok(start.distanceTo(renderer.camera.position)>.15);emit(canvas,'keyup',{key:'w'});const released=renderer.camera.position.clone();frames(renderer,20);assert.deepEqual(renderer.camera.position.toArray(),released.toArray());clean();});
 test('Onscreen movement starts and releases without automatic walking',()=>{const {engine,renderer}=setup();engine.explore(true);frames(renderer);const start=renderer.camera.position.clone();engine.step(1,0,true);frames(renderer,5);assert.ok(start.distanceTo(renderer.camera.position)>.05);engine.step(1,0,false);const released=renderer.camera.position.clone();frames(renderer,10);assert.deepEqual(renderer.camera.position.toArray(),released.toArray());clean();});
 test('Canvas blur clears held movement rather than leaving a stuck key',()=>{const {engine,canvas,renderer}=setup();engine.explore(true);emit(canvas,'keydown',{key:'w'});frames(renderer,3);emit(canvas,'blur');const stopped=renderer.camera.position.clone();frames(renderer,10);assert.deepEqual(renderer.camera.position.toArray(),stopped.toArray());clean();});
 test('Window blur clears onscreen movement holds',()=>{const {engine,renderer}=setup();engine.explore(true);engine.step(1,0,true);frames(renderer,3);emit(window,'blur');const stopped=renderer.camera.position.clone();frames(renderer,10);assert.deepEqual(renderer.camera.position.toArray(),stopped.toArray());clean();});
 test('Hidden-page transition clears input before the page resumes',()=>{const {engine,canvas,renderer}=setup();engine.explore(true);emit(canvas,'keydown',{key:'w'});frames(renderer,3);document.hidden=true;emit(document,'visibilitychange');const stopped=renderer.camera.position.clone();frames(renderer,10);document.hidden=false;emit(document,'visibilitychange');frames(renderer,10);assert.deepEqual(renderer.camera.position.toArray(),stopped.toArray());clean();});
 test('Offscreen visibility clears held movement before re-entry',()=>{const {engine,canvas,renderer,host}=setup();engine.explore(true);emit(canvas,'keydown',{key:'w'});frames(renderer,3);const observer=observers.findLast(o=>o.target===host);observer.callback([{isIntersecting:false}]);const stopped=renderer.camera.position.clone();frames(renderer,10);observer.callback([{isIntersecting:true}]);frames(renderer,10);assert.deepEqual(renderer.camera.position.toArray(),stopped.toArray());clean();});
 test('Escape restores orbit framing and returns focus to the entry button',()=>{const {engine,canvas,renderer,trigger,changes}=setup();const orbit=renderer.camera.position.clone();engine.explore(true);frames(renderer);emit(canvas,'keydown',{key:'Escape'});frames(renderer);assert.equal(renderer.camera.fov,32);assert.equal(document.activeElement,trigger);assert.ok(renderer.camera.position.distanceTo(orbit)<1e-9);assert.deepEqual(changes,[true,false]);clean();});
 test('A zero-delta Ctrl-wheel cannot move the explorer',()=>{const {engine,canvas,renderer}=setup();engine.explore(true);frames(renderer);const start=renderer.camera.position.clone();emit(canvas,'wheel',{deltaX:0,deltaY:0,deltaMode:0,ctrlKey:true,shiftKey:false});frames(renderer);assert.deepEqual(renderer.camera.position.toArray(),start.toArray());clean();});
 test('Two-finger vertical scroll walks immediately without changing eye height or pitch',()=>{const {engine,canvas,renderer}=setup();engine.explore(true);frames(renderer);const before=renderer.camera.position.clone(),direction=renderer.camera.getWorldDirection(new THREE.Vector3());const event=emit(canvas,'wheel',{deltaX:0,deltaY:-20,deltaMode:0,ctrlKey:false,shiftKey:false});frames(renderer);assert.equal(event.defaultPrevented,true);assert.ok(Math.abs(before.distanceTo(renderer.camera.position)-.12)<1e-10);assert.equal(renderer.camera.position.y,2.05);assert.ok(renderer.camera.getWorldDirection(new THREE.Vector3()).distanceTo(direction)<1e-12);clean();});
 test('Horizontal two-finger swipe turns rather than moving or tilting the explorer',()=>{const {engine,canvas,renderer}=setup();engine.explore(true);frames(renderer);const before=renderer.camera.position.clone(),direction=renderer.camera.getWorldDirection(new THREE.Vector3());emit(canvas,'wheel',{deltaX:25,deltaY:0,deltaMode:0,ctrlKey:false,shiftKey:false});frames(renderer);const after=renderer.camera.getWorldDirection(new THREE.Vector3());assert.deepEqual(renderer.camera.position.toArray(),before.toArray());assert.ok(direction.distanceTo(after)>.09);assert.ok(Math.abs(direction.y-after.y)<1e-12);clean();});
 test('Shift scroll strafes perpendicular to the gaze without turning',()=>{const {engine,canvas,renderer}=setup();engine.explore(true);frames(renderer);const before=renderer.camera.position.clone(),direction=renderer.camera.getWorldDirection(new THREE.Vector3());emit(canvas,'wheel',{deltaX:0,deltaY:20,deltaMode:0,ctrlKey:false,shiftKey:true});frames(renderer);const offset=renderer.camera.position.clone().sub(before);assert.ok(Math.abs(offset.length()-.12)<1e-10);assert.ok(Math.abs(offset.dot(direction))<1e-12);assert.ok(renderer.camera.getWorldDirection(new THREE.Vector3()).distanceTo(direction)<1e-12);clean();});
 test('Small pinch input remains proportional and stops when the gesture ends',()=>{const {engine,canvas,renderer}=setup('lite',true);engine.explore(true);frames(renderer);const before=renderer.camera.position.clone();emit(canvas,'wheel',{deltaX:0,deltaY:-.001,deltaMode:0,ctrlKey:true,shiftKey:false});frames(renderer);assert.ok(Math.abs(before.distanceTo(renderer.camera.position)-.000012)<1e-10);const stopped=renderer.camera.position.clone();frames(renderer,180);assert.deepEqual(renderer.camera.position.toArray(),stopped.toArray());clean();});
 test('Wheel line/page units are normalized in actual Explore movement',()=>{const {engine,canvas,renderer}=setup();engine.explore(true);frames(renderer);const start=renderer.camera.position.clone();emit(canvas,'wheel',{deltaX:0,deltaY:-1,deltaMode:1,ctrlKey:false,shiftKey:false});frames(renderer);const line=start.distanceTo(renderer.camera.position);engine.focus(-1);frames(renderer);emit(canvas,'wheel',{deltaX:0,deltaY:-16,deltaMode:0,ctrlKey:false,shiftKey:false});frames(renderer);assert.ok(Math.abs(start.distanceTo(renderer.camera.position)-line)<1e-12);engine.focus(-1);frames(renderer);emit(canvas,'wheel',{deltaX:0,deltaY:-16/550,deltaMode:2,ctrlKey:false,shiftKey:false});frames(renderer);assert.ok(Math.abs(start.distanceTo(renderer.camera.position)-line)<1e-12);clean();});
 test('Click-drag freely looks but cannot leave residual orbit or walking motion',()=>{const {engine,canvas,renderer}=setup('lite',true);engine.explore(true);frames(renderer);const start=renderer.camera.position.clone(),direction=renderer.camera.getWorldDirection(new THREE.Vector3());emit(canvas,'pointerdown',{clientX:500,clientY:275,pointerId:1});emit(canvas,'pointermove',{clientX:550,clientY:300,pointerId:1});emit(canvas,'pointerup',{clientX:550,clientY:300,pointerId:1});frames(renderer);assert.ok(direction.distanceTo(renderer.camera.getWorldDirection(new THREE.Vector3()))>.1);const turned=renderer.camera.getWorldDirection(new THREE.Vector3());frames(renderer,180);assert.deepEqual(renderer.camera.position.toArray(),start.toArray());assert.ok(renderer.camera.getWorldDirection(new THREE.Vector3()).distanceTo(turned)<1e-12);clean();});
 test('A drag that backtracks to its starting point never opens a console accidentally',()=>{const {canvas,renderer,selections}=setup();let station;renderer.scene.traverse(o=>{if(o.userData.index===0)station=o;});assert.ok(station);const point=station.localToWorld(new THREE.Vector3(0,1.72,0)).project(renderer.camera),clientX=(point.x+1)*500,clientY=(1-point.y)*275,pointerId=1;emit(canvas,'pointerdown',{clientX,clientY,pointerId});emit(canvas,'pointerup',{clientX,clientY,pointerId});assert.deepEqual(selections,[0],'The test coordinate must hit a real console');selections.length=0;emit(canvas,'pointerdown',{clientX,clientY,pointerId});emit(canvas,'pointermove',{clientX:clientX+30,clientY,pointerId});emit(canvas,'pointermove',{clientX,clientY,pointerId});emit(canvas,'pointerup',{clientX,clientY,pointerId});assert.deepEqual(selections,[]);clean();});
 test('Uncommanded exploration remains still while ambient animation runs',()=>{const {engine,renderer}=setup('lite',true);engine.explore(true);frames(renderer);const start=renderer.camera.position.clone();frames(renderer,180);assert.deepEqual(renderer.camera.position.toArray(),start.toArray());clean();});
 test('Pause freezes atmosphere time and resume uses the retained animation clock',()=>{const {engine,renderer}=setup('lite',true),atmosphere=renderer.scene.getObjectByName('island-atmosphere'),shader=[];atmosphere.traverse(o=>{if(o.material?.uniforms?.uTime)shader.push(o.material);});assert.equal(shader.length,2);frames(renderer,5);engine.motion(false);const paused=shader.map(m=>m.uniforms.uTime.value);frames(renderer,100);assert.deepEqual(shader.map(m=>m.uniforms.uTime.value),paused);engine.motion(true);frames(renderer);shader.forEach((m,i)=>assert.ok(m.uniforms.uTime.value>paused[i]&&m.uniforms.uTime.value-paused[i]<.1));clean();});
 test('Hover callbacks report changed projects only and clear safely',()=>{const {engine,hoverChanges}=setup();engine.highlight(0);engine.highlight(0);engine.highlight(-1);assert.deepEqual(hoverChanges,[0,-1]);clean();});
 test('Detailed renderer resizes composition and releases passes and reflection targets',()=>{const before={composer:composers.length,pass:passes.length,target:targets.length};const {engine,renderer,host}=setup('balanced');const composer=composers.at(-1);assert.deepEqual(composer.size,[host.clientWidth,host.clientHeight]);assert.ok(renderer.info.render.calls>=3);engine.dispose();current=null;assert.ok(composers.slice(before.composer).every(x=>x.disposed));assert.ok(passes.slice(before.pass).every(x=>x.disposed));assert.ok(targets.slice(before.target).every(x=>x.disposed));});
 test('Normal disposal removes loops, DOM listeners, observers and canvas exactly once',()=>{const priorObservers=observers.length,{engine,canvas,renderer,host}=setup();engine.explore(true);engine.dispose();engine.dispose();current=null;assert.equal(renderer.loop,null);assert.equal(renderer.disposed,true);assert.equal(renderer.lost,true);assert.equal(host.children.length,0);assert.equal(canvas.listenerCount,0);assert.equal(window.listenerCount,0);assert.equal(document.listenerCount,0);assert.ok(observers.slice(priorObservers).every(o=>o.disconnected));assert.equal(controls.at(-1).disposed,true);});
 test('A resize failure during construction releases already-installed interactions',()=>{const host=new Element(),priorObservers=observers.length;faults.resize=true;try{assert.throws(()=>createWorld(host,{projects:[fixture],quality:'lite',motion:false,onSelect(){},onError(){}}),/TEST_ONLY_RESIZE_FAILURE/);}finally{faults.resize=false;}const renderer=renderers.at(-1);assert.equal(host.children.length,0);assert.equal(renderer.domElement.listenerCount,0);assert.equal(window.listenerCount,0);assert.equal(document.listenerCount,0);assert.equal(renderer.loop,null);assert.equal(renderer.disposed,true);assert.equal(controls.at(-1).disposed,true);assert.ok(observers.slice(priorObservers).every(o=>o.disconnected));});
 test('Atmosphere has finite, bounded particles in detailed and lightweight quality',()=>{for(const lite of [false,true]){const a=createIslandAtmosphere(lite),points=a.root.children.find(o=>o instanceof THREE.Points),positions=points.geometry.getAttribute('position');assert.equal(positions.count,lite?36:100);assert.ok([...positions.array].every(Number.isFinite));assert.ok([...positions.array].every(value=>Math.abs(value)<30));assert.equal(a.root.userData.excludeFromIslandFraming,true);}});
 test('Lighting presets are genuinely distinct without changing particle geometry',()=>{const a=createIslandAtmosphere(),points=a.root.children.find(o=>o instanceof THREE.Points),positions=[...points.geometry.getAttribute('position').array],colors=[];for(const mode of Object.keys(ISLAND_LIGHTING)){a.lighting(mode);colors.push(points.material.uniforms.uColor.value.getHexString());}assert.equal(new Set(colors).size,3);assert.deepEqual([...points.geometry.getAttribute('position').array],positions);});
 test('Atmosphere remains outside the island silhouette and cannot shrink its home frame',()=>{const {renderer}=setup(),island=renderer.scene.getObjectByName('purple-floating-island'),atmosphere=renderer.scene.getObjectByName('island-atmosphere'),before=islandHomeFrame(island,2);assert.notEqual(atmosphere.parent,island);atmosphere.position.set(1000,1000,1000);renderer.scene.updateMatrixWorld(true);const after=islandHomeFrame(island,2);assert.deepEqual(after.position.toArray(),before.position.toArray());assert.deepEqual(after.target.toArray(),before.target.toArray());clean();});
 console.log(`${count} island simulator integration checks passed (CPU/mock renderer; not visual browser verification).`);
}finally{
 current?.engine.dispose();
 for(const [key,descriptor] of Object.entries(originals)){if(descriptor)Object.defineProperty(globalThis,key,descriptor);else delete globalThis[key];}
 delete globalThis[mockKey];
}

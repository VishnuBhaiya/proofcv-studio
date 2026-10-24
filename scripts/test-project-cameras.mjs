// CPU geometry regressions. No WebGL screenshot, provider, or performance claim.
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import ts from 'typescript';
import * as THREE from 'three';
const cache=new Map();
async function moduleURL(name){
 if(cache.has(name))return cache.get(name);
 let output=ts.transpileModule(await readFile(new URL('../src/portfolio/'+name+'.ts',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;
 for(const match of [...output.matchAll(/from ['"]([^'"]+)['"]/g)]){const spec=match[1],url=spec.startsWith('./')?await moduleURL(spec.slice(2)):import.meta.resolve(spec);output=output.replaceAll(match[0],'from '+JSON.stringify(url));}
 const url='data:text/javascript;base64,'+Buffer.from(output).toString('base64');cache.set(name,url);return url;
}
const {createProjectEnvironment,projectShots,fitProjectOverview,projectCameraGeometry,constrainProjectCamera,projectFogDensity}=await import(await moduleURL('projectEnvironments'));
const {islandHomeFrame}=await import(await moduleURL('worldEngine'));
const {createIsland}=await import(await moduleURL('islandModels'));
const titles=['Intersection object detection','Warehouse safety','SolarVision','Fake News Detection','Dataset Quality Review Toolkit','Responsive website','Computer vision scanner','Research journal'];
const projects=titles.map((title,i)=>({id:'camera-fixture-'+i,title,description:'Synthetic geometry fixture, not a candidate claim.',technologies:''}));
let count=0;function test(name,run){run();count++;console.log('PASS '+name);}
const environments=projects.map(p=>createProjectEnvironment(p));
const geometries=environments.map(e=>projectCameraGeometry(e.root));
test('Continuous ground and distant scenery do not determine the overview',()=>environments.forEach((e,i)=>{const full=new THREE.Box3().setFromObject(e.root),subject=geometries[i].subject;assert.ok(subject.getSize(new THREE.Vector3()).length()<full.getSize(new THREE.Vector3()).length(),e.kind);assert.ok(subject.max.y>2,e.kind+' needs visible project objects');}));
test('Shelving instances preserve the usable warehouse centre aisle',()=>{const i=environments.findIndex(e=>e.kind==='warehouse');const eye=new THREE.Vector3(0,4,0);assert.ok(!geometries[i].solids.some(b=>b.containsPoint(eye)));});
test('All presets have physical clearance from individual scenery meshes',()=>environments.forEach((e,i)=>{for(const s of projectShots(e.kind)){const eye=new THREE.Vector3(...s.position);for(const b of geometries[i].solids)assert.ok(!b.clone().expandByScalar(.25).containsPoint(eye),e.kind+' / '+s.label+' inside solid');}}));
test('Interior camera centre lines are not blocked by foreground racks or walls',()=>environments.forEach(e=>{e.root.updateMatrixWorld(true);for(const s of projectShots(e.kind).slice(0,2)){const eye=new THREE.Vector3(...s.position),target=new THREE.Vector3(...s.target),distance=eye.distanceTo(target),ray=new THREE.Raycaster(eye,target.sub(eye).normalize(),.1,distance*.79);const hit=ray.intersectObject(e.root,true).find(h=>h.object instanceof THREE.Mesh);assert.ok(!hit,e.kind+' / '+s.label+' obstructed at '+hit?.distance+' by '+hit?.object.name);}}));
test('Meaningful subject occupies the overview across laptop proportions',()=>environments.forEach((e,i)=>{const bounds=geometries[i].subject,shot=projectShots(e.kind)[2],target=new THREE.Vector3(...shot.target);for(const aspect of [1.4,2,2.8]){const eye=fitProjectOverview(bounds,aspect,new THREE.Vector3(...shot.position),target),camera=new THREE.PerspectiveCamera(50,aspect,.1,500);camera.position.copy(eye);camera.lookAt(target);camera.updateMatrixWorld();let extent=0;for(const x of [bounds.min.x,bounds.max.x])for(const y of [bounds.min.y,bounds.max.y])for(const z of [bounds.min.z,bounds.max.z]){const p=new THREE.Vector3(x,y,z).project(camera);assert.ok(Math.abs(p.x)<=.87&&Math.abs(p.y)<=.87,e.kind);assert.ok(p.z>=-1&&p.z<=1,e.kind+' clipped');extent=Math.max(extent,Math.abs(p.x),Math.abs(p.y));}assert.ok(extent>.8,e.kind+' framed too far away');}}));
test('Overview fog preserves at least 80 percent of distant subject contrast',()=>environments.forEach((e,i)=>{const subject=geometries[i].subject,shot=projectShots(e.kind)[2],eye=fitProjectOverview(subject,1.4,new THREE.Vector3(...shot.position),new THREE.Vector3(...shot.target)),density=projectFogDensity(e.palette.density,eye,subject),far=eye.distanceTo(subject.getCenter(new THREE.Vector3()))+subject.getSize(new THREE.Vector3()).length()/2;assert.ok(Math.exp(-density*density*far*far)>=.799999,e.kind+' faded out');}));
test('A large camera step cannot tunnel through a thin rack',()=>{const rack=new THREE.Box3(new THREE.Vector3(-2,0,-.08),new THREE.Vector3(2,6,.08)),from=new THREE.Vector3(0,3,5),requested=new THREE.Vector3(0,3,-5),result=constrainProjectCamera(from,requested,[rack]);assert.ok(result.z>.4);assert.ok(result.z<.5);assert.equal(result.x,0);});
test('Safe aisle motion remains unmodified and cannot sink below the floor',()=>{const solids=[new THREE.Box3(new THREE.Vector3(4,0,-5),new THREE.Vector3(7,6,5))],from=new THREE.Vector3(0,3,5),to=new THREE.Vector3(0,2,-4);assert.deepEqual(constrainProjectCamera(from,to,solids).toArray(),to.toArray());assert.ok(constrainProjectCamera(from,new THREE.Vector3(0,-3,5),solids).y>=.65);});
test('Manual orbit and aggressive zoom sweeps remain outside individual solids',()=>environments.forEach((e,i)=>{const geometry=geometries[i],shot=projectShots(e.kind)[0],target=new THREE.Vector3(...shot.target);let eye=new THREE.Vector3(...shot.position);for(let n=0;n<180;n++){const offset=eye.clone().sub(target),spherical=new THREE.Spherical().setFromVector3(offset);spherical.theta+=.06;spherical.phi=THREE.MathUtils.clamp(spherical.phi+Math.sin(n*.3)*.012,.25,1.5);spherical.radius=THREE.MathUtils.clamp(spherical.radius*(n%17===0?.55:1.025),2.5,85);const next=constrainProjectCamera(eye,target.clone().add(new THREE.Vector3().setFromSpherical(spherical)),geometry.solids);assert.ok(next.y>=.649999,e.kind);for(const b of geometry.solids)assert.ok(!b.containsPoint(next),e.kind+' / step '+n);eye=next;}}));
test('Real island surfaces fill the entrance without clipping roof, base or rings',()=>{
 const previous=globalThis.document;globalThis.document={createElement:()=>({width:0,height:0,getContext:()=>({fillRect(){},strokeRect(){},fillText(){}})})};
 try{
  const island=createIsland(projects);island.root.updateMatrixWorld(true);
  for(const aspect of [.8,1.2,1.6,2,2.8,3,3.5]){
   const frame=islandHomeFrame(island.root,aspect),camera=new THREE.PerspectiveCamera(32,aspect,.1,500);camera.position.copy(frame.position);camera.lookAt(frame.target);camera.updateMatrixWorld();
   assert.ok(frame.maxDistance>frame.position.distanceTo(frame.target));let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
   // Independently project every actual geometry vertex, not the helper's bounds/inputs.
   island.root.traverse(o=>{const position=o.geometry?.getAttribute('position');if(!position)return;for(let n=0;n<position.count;n++){const p=new THREE.Vector3().fromBufferAttribute(position,n).applyMatrix4(o.matrixWorld).project(camera);assert.ok(p.z>=-1&&p.z<=1);assert.ok(Math.abs(p.x)<.87&&Math.abs(p.y)<.87,'Island clipped at aspect '+aspect);minX=Math.min(minX,p.x);maxX=Math.max(maxX,p.x);minY=Math.min(minY,p.y);maxY=Math.max(maxY,p.y);}});
   const width=(maxX-minX)/2,height=(maxY-minY)/2;
   assert.ok(Math.max(width,height)>.79,'Island too small at aspect '+aspect);assert.ok(Math.max(width,height)<.86);assert.ok(Math.abs((minX+maxX)/2)<.025&&Math.abs((minY+maxY)/2)<.025,'Island off-centre');
   if(aspect===2||aspect===3)console.log('ISLAND surface framing '+JSON.stringify({aspect,widthPercent:Math.round(width*1000)/10,heightPercent:Math.round(height*1000)/10,distance:Math.round(frame.position.distanceTo(frame.target)*100)/100}));
  }
 }finally{globalThis.document=previous;}
});
console.log(`${count} project camera regressions passed.`);

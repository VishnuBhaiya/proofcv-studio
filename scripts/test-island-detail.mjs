// Geometry-only island regression checks. This does not claim GPU/browser verification.
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
globalThis.document={createElement:()=>({width:0,height:0,getContext:()=>({fillRect(){},strokeRect(){},fillText(){}})})};
const {createIsland}=await import(await moduleURL('islandModels'));
const titles=['Intersection Object Detection','Warehouse Safety','SolarVision','Fake News Detection','Dataset Quality Review','Responsive Website'];
const projects=titles.map((title,i)=>({id:'project-'+i,title,description:'Exact confirmed project text.',technologies:''}));
let count=0;
function test(name,run){run();count++;console.log('PASS '+name);}
for(const lite of [false,true]){
 const island=createIsland(projects,lite),prefix=lite?'Reduced':'Detailed';
 test(prefix+' keeps the original island, workshop and tower identities',()=>{assert.equal(island.root.name,'purple-floating-island');assert.ok(island.root.getObjectByName('original-workshop'));assert.ok(island.root.getObjectByName('original-server-tower'));assert.equal(island.groups.length,6);});
 test(prefix+' remains inside the original framing envelope',()=>{island.root.updateMatrixWorld(true);const bounds=new THREE.Box3(),v=new THREE.Vector3();island.root.traverse(o=>{if(o.isMesh){const points=o.geometry.getAttribute('position');for(let n=0;n<points.count;n++){v.fromBufferAttribute(points,n).applyMatrix4(o.matrixWorld);bounds.expandByPoint(v);}}});console.log('  true surface bounds '+bounds.min.toArray().map(n=>n.toFixed(2))+' → '+bounds.max.toArray().map(n=>n.toFixed(2)));assert.ok(bounds.min.x>=-7.4&&bounds.max.x<=7.4);assert.ok(bounds.min.z>=-7.4&&bounds.max.z<=7.4);assert.ok(bounds.min.y>=-2.7&&bounds.max.y<=5.2);});
 test(prefix+' geometry is finite and stays below 600 drawable objects',()=>{let drawables=0;island.root.traverse(o=>{if(o.isMesh||o.isLineSegments){drawables++;for(const v of o.geometry.getAttribute('position').array)assert.ok(Number.isFinite(v));}});assert.ok(drawables<=600);console.log('  '+drawables+' drawables');});
 test(prefix+' gives each original project console a distinct tactile identity',()=>{const kinds=[];for(let n=0;n<island.groups.length;n++){const g=island.groups[n],marker=g.children.find(o=>o.name.startsWith('destination-marker-'));assert.ok(marker);assert.equal(marker.userData.projectId,projects[n].id);assert.equal(marker.userData.symbolic,true);assert.equal(g.userData.index,n);kinds.push(marker.userData.kind);}assert.equal(new Set(kinds).size,6);});
 test(prefix+' visible workshop glass contains an actual recessed room',()=>{const room=island.root.getObjectByName('original-workshop');assert.ok(room.children.some(o=>o.isMesh&&o.material.transparent&&o.material.opacity===.2));assert.ok(room.children.some(o=>o.isMesh&&o.geometry.type==='ExtrudeGeometry'));assert.ok(island.root.getObjectByName('deck-service-hatch'));});
 test(prefix+' preserves caller-owned profile facts',()=>assert.equal(projects[0].description,'Exact confirmed project text.'));
 // All resources use the engine's existing traversal-based cleanup contract.
 const geometries=new Set(),materials=new Set(island.materials);
 island.root.traverse(o=>{if(o.geometry)geometries.add(o.geometry);if(o.material)for(const m of Array.isArray(o.material)?o.material:[o.material])materials.add(m);});
 for(const g of geometries)g.dispose();for(const m of materials)m.dispose();for(const t of island.textures)t.dispose();
}
console.log(`${count} island detail checks passed.`);

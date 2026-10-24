import * as THREE from 'three';
import type { Project } from './types';
import { coverScene,coverSeed } from './projectVisuals';

/** Original symbolic models. No candidate media, inferred results or remote assets. */
export function createExhibit(project:Project){
 const kind=coverScene(project),seed=coverSeed(project),group=new THREE.Group();
 group.name='exhibit-'+project.id;group.userData={projectId:project.id,kind,symbolic:true};
 const moving:THREE.Object3D[]=[];
 const color={intersection:'#75dccc',warehouse:'#e8bd79',solar:'#82bfff',news:'#d3a6ff',vision:'#8ce4e7',systems:'#a7b5ff',web:'#f2b5c8',notes:'#d7c5a6'}[kind]!;
 const mat=(c:string,metal=.2,rough=.5)=>new THREE.MeshStandardMaterial({color:c,metalness:metal,roughness:rough});
 const ink=mat('#263b49'),pale=mat('#d8e2e1'),metal=mat('#7e969c',.6,.3),accent=mat(color,.4,.32);
 const glow=new THREE.MeshStandardMaterial({color,emissive:color,emissiveIntensity:1.4,toneMapped:false});
 const muted=mat('#475f67'),paper=mat('#f0e7d7');
 function mesh(g:THREE.BufferGeometry,m:THREE.Material,x=0,y=0,z=0,parent:THREE.Object3D=group){const obj=new THREE.Mesh(g,m);obj.position.set(x,y,z);obj.castShadow=true;obj.receiveShadow=true;parent.add(obj);return obj;}
 const box=(w:number,h:number,d:number,m:THREE.Material,x=0,y=0,z=0,parent:THREE.Object3D=group)=>mesh(new THREE.BoxGeometry(w,h,d),m,x,y,z,parent);
 const sphere=(r:number,m:THREE.Material,x=0,y=0,z=0,parent:THREE.Object3D=group)=>mesh(new THREE.SphereGeometry(r,12,8),m,x,y,z,parent);
 const cylinder=(r:number,h:number,m:THREE.Material,x=0,y=0,z=0,parent:THREE.Object3D=group)=>mesh(new THREE.CylinderGeometry(r,r,h,16),m,x,y,z,parent);
 function person(x:number,z:number){sphere(.075,pale,x,.52,z);box(.12,.23,.09,accent,x,.32,z);for(const dx of [-.04,.04])box(.035,.17,.035,ink,x+dx,.12,z);}
 function outline(x:number,y:number,z:number,w:number,h:number,d:number){const lines=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(w,h,d)),new THREE.LineBasicMaterial({color}));lines.position.set(x,y,z);group.add(lines);return lines;}
 if(kind==='intersection'){
  box(2.8,.06,2.1,muted,0,.04,0);box(.8,.025,2.1,ink,0,.09,0);box(2.8,.026,.7,ink,0,.09,0);
  for(let i=0;i<7;i++){box(.14,.012,.025,pale,-1.2+i*.4,.11,0);box(.025,.012,.12,pale,0,.11,-.88+i*.29);}
  for(let i=0;i<5;i++){box(.045,.013,.32,paper,.42+i*.09,.12,.65);box(.32,.013,.045,paper,-.64,.12,-.42-i*.09);}
  function car(x:number,z:number,turn=0){const g=new THREE.Group();g.position.set(x,.12,z);g.rotation.y=turn;group.add(g);box(.26,.15,.5,accent,0,.12,0,g);box(.22,.13,.23,pale,0,.25,-.03,g);for(const dx of [-.15,.15])for(const dz of [-.14,.14]){const wheel=cylinder(.065,.045,ink,dx,.08,dz,g);wheel.rotation.z=Math.PI/2;}}
  car(-.85,.17);car(.18,-.6,Math.PI/2);person(.72,.64);outline(-.85,.35,.17,.4,.6,.64);outline(.72,.4,.64,.3,.75,.3);
  for(const x of [-1.15,1.15]){cylinder(.025,.75,metal,x,.43,-.8);box(.12,.25,.1,ink,x,.85,-.8);sphere(.025,glow,x,.93,-.74);}
 }else if(kind==='warehouse'){
  box(2.8,.06,2.1,pale,0,.04,0);
  for(const x of [-.99,.99]){for(const dx of [-.27,.27])box(.045,1.45,.045,metal,x+dx,.76,-.3);for(let row=0;row<3;row++){box(.64,.04,.7,muted,x,.15+row*.46,-.3);for(let n=0;n<2;n++)box(.23,.27,.29,row%2?paper:accent,x-.15+n*.3,.31+row*.46,-.27);}}
  const zone=box(.78,.012,.9,new THREE.MeshStandardMaterial({color,transparent:true,opacity:.25}),0,.09,.25);zone.name='illustrative-safety-zone';
  outline(0,.12,.25,.82,.05,.94);person(.08,.3);box(.07,1.9,.07,metal,.5,.99,-.85);box(.3,.15,.15,ink,.36,1.9,-.85);sphere(.055,glow,.21,1.9,-.77);
  const beam=mesh(new THREE.ConeGeometry(.5,1.6,4,1,true),new THREE.MeshBasicMaterial({color,transparent:true,opacity:.08,side:THREE.DoubleSide,depthWrite:false}),.16,1.05,-.3);beam.rotation.z=-.22;
 }else if(kind==='solar'){
  box(2.8,.07,2.1,muted,0,.04,0);
  for(let row=0;row<2;row++)for(let col=0;col<3;col++){const x=-.91+col*.91,z=-.48+row*.95;box(.05,.28,.05,metal,x,.2,z);const p=box(.76,.055,.67,ink,x,.42,z);p.rotation.x=-.22;for(let stripe=0;stripe<4;stripe++){const line=box(.012,.012,.64,accent,x-.27+stripe*.18,.46,z);line.rotation.x=-.22;}}
  outline(.01,.6,-.48,.84,.35,.76);
  const drone=new THREE.Group();drone.position.set(.55,1.45,.16);group.add(drone);box(.28,.1,.2,pale,0,0,0,drone);for(const x of [-.25,.25])for(const z of [-.22,.22]){box(.025,.025,.4,metal,x/2,0,z/2,drone);const rotor=cylinder(.13,.015,ink,x,.06,z,drone);moving.push(rotor);}sphere(.04,glow,0,-.08,0,drone);
 }else if(kind==='systems'){
  box(2.8,.1,2,pale,0,.05,0);box(2.5,.012,.04,glow,0,.12,0);
  for(let n=0;n<3;n++){const x=-.9+n*.9;box(.63,.14,.68,metal,x,.2,0);if(n===0){for(let i=0;i<4;i++)box(.37,.03,.42,i%2?pale:accent,x,.33+i*.06,0);}else if(n===1){cylinder(.27,.62,ink,x,.54,0);for(let i=0;i<3;i++){const r=mesh(new THREE.TorusGeometry(.275,.014,5,24),glow,x,.34+i*.19,0);r.rotation.x=Math.PI/2;}}else{box(.04,.63,.04,metal,x,.52,0);box(.6,.45,.06,ink,x,.83,0);for(let i=0;i<3;i++)box(.34-i*.06,.025,.012,glow,x-.05,.93-i*.09,.04);}}
 }else if(kind==='news'){
  box(2.7,.14,1.75,muted,0,.1,0);for(const x of [-1.05,1.05])box(.05,.6,.05,metal,x,-.22,0);
  for(let n=0;n<4;n++){const page=box(.84,.028,.98,paper,-.63,.21+n*.04,.16);page.rotation.y=-.15+n*.05;}
  box(.11,.57,.1,metal,.61,.45,-.25);box(1.05,.74,.08,ink,.61,.93,-.25);box(.86,.55,.018,accent,.61,.93,-.2);for(let n=0;n<3;n++)box(.46-n*.07,.025,.012,ink,.51,1.1-n*.12,-.18);
  const lens=new THREE.Group();lens.position.set(-.4,.8,.1);lens.rotation.x=-.6;group.add(lens);mesh(new THREE.TorusGeometry(.31,.035,8,32),glow,0,0,0,lens);box(.06,.4,.06,metal,.24,-.33,0,lens);
 }else if(kind==='web'){
  box(2.7,.13,1.7,muted,0,.08,0);box(.1,.6,.1,metal,0,.43,0);box(1.8,1.15,.1,ink,0,1.16,0);box(1.65,.95,.015,paper,0,1.18,.061);box(1.65,.12,.018,accent,0,1.61,.075);box(.67,.58,.02,accent,.39,1.14,.075);for(let i=0;i<4;i++)box(.6-i*.08,.025,.025,metal,-.42,1.42-i*.14,.08);box(.75,.035,.3,pale,0,.2,.43);
  const phone=box(.35,.65,.08,ink,1.03,.5,.4);phone.rotation.z=-.1;box(.27,.5,.02,accent,1.03,.5,.45);
 }else if(kind==='vision'){
  box(2.7,.1,1.8,muted,0,.08,0);const object=mesh(new THREE.IcosahedronGeometry(.48,0),accent,0,.69,0);object.rotation.y=(seed%100)/25;moving.push(object);outline(0,.69,0,1.17,1.17,1.17);for(const x of [-.95,.95]){box(.06,.65,.06,metal,x,.4,.1);box(.36,.25,.3,ink,x,.83,.1);cylinder(.1,.07,glow,x,.83,.28).rotation.x=Math.PI/2;}
 }else{
  box(2.6,.1,1.75,muted,0,.08,0);for(let i=0;i<5;i++){const book=box(.24,.65+(i%2)*.16,.58,i%2?paper:accent,-.7+i*.32,.47,-.1);book.rotation.z=(i===4?-.1:0);}box(1.8,.1,.73,pale,0,.18,.09);
 }
 return {group,moving,color,kind,materials:[ink,pale,metal,accent,glow,muted,paper]};
}

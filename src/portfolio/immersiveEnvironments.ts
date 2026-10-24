import * as THREE from 'three';
import type { Project } from './types';
import { coverScene,coverSeed } from './projectVisuals';

export const WORLD_PALETTES:Record<string,{sky:string;fog:string;accent:string;sun:string;density:number}>={
 warehouse:{sky:'#10202a',fog:'#223544',accent:'#f8bc63',sun:'#ffe1ad',density:.021},
 intersection:{sky:'#10172c',fog:'#202b47',accent:'#60eadb',sun:'#cbd9ff',density:.017},
 solar:{sky:'#b1c8cf',fog:'#a8bdbe',accent:'#75dded',sun:'#ffe5ae',density:.011},
 news:{sky:'#171224',fog:'#30253c',accent:'#d5a5ff',sun:'#ffdab8',density:.025},
 systems:{sky:'#081827',fog:'#102c40',accent:'#51dff5',sun:'#b0e2ff',density:.026},
 web:{sky:'#222b3d',fog:'#3b495a',accent:'#8ee2c1',sun:'#f5e5d0',density:.018},
 vision:{sky:'#111b2f',fog:'#25334f',accent:'#9cafff',sun:'#dce4ff',density:.024},
 notes:{sky:'#252034',fog:'#44384a',accent:'#ecbf87',sun:'#ffe6bd',density:.023}
};

/** Full-scale, original set designs. Scenery/animation never represents actual project results. */
export function createImmersiveEnvironment(project:Project,lite=false){
 const kind=coverScene(project),palette=WORLD_PALETTES[kind],seed=coverSeed(project),root=new THREE.Group();
 root.name='project-world-'+project.id;root.userData={projectId:project.id,kind,symbolic:true,fullScale:true};
 const content=new THREE.Group();content.name='environment-content';content.userData={projectId:project.id};root.add(content);
 const materials:THREE.Material[]=[],geometries=new Map<string,THREE.BufferGeometry>(),animations:((t:number)=>void)[]=[];
 const material=(color:string,metalness=.15,roughness=.65)=>{const m=new THREE.MeshStandardMaterial({color,metalness,roughness});materials.push(m);return m;};
 const glow=(color:string,intensity=2)=>{const m=new THREE.MeshStandardMaterial({color,emissive:color,emissiveIntensity:intensity,roughness:.35,toneMapped:false});materials.push(m);return m;};
 const dark=material('#18222e',.45,.4),steel=material('#495c70',.65,.34),pale=material('#bcc8cf',.3,.45),rubber=material('#0a1018',.05,.85),warm=material('#c68d51',.05,.9),white=material('#e6e4db',.1,.65),accent=material(palette.accent,.45,.3),emit=glow(palette.accent),glass=material('#426b84',.72,.17);
 const geo=(key:string,create:()=>THREE.BufferGeometry)=>{let g=geometries.get(key);if(!g){g=create();geometries.set(key,g);}return g;};
 function mesh(g:THREE.BufferGeometry,m:THREE.Material,x=0,y=0,z=0,parent:THREE.Object3D=content){const o=new THREE.Mesh(g,m);o.position.set(x,y,z);o.castShadow=!lite;o.receiveShadow=!lite;parent.add(o);return o;}
 const box=(w:number,h:number,d:number,m:THREE.Material,x=0,y=0,z=0,p:THREE.Object3D=content)=>{const o=mesh(geo('cube',()=>new THREE.BoxGeometry(1,1,1)),m,x,y,z,p);o.scale.set(w,h,d);return o;};
 const cyl=(r:number,h:number,m:THREE.Material,x=0,y=0,z=0,p:THREE.Object3D=content)=>{const o=mesh(geo('cylinder',()=>new THREE.CylinderGeometry(1,1,1,lite?12:24)),m,x,y,z,p);o.scale.set(r,h,r);return o;};
 const ball=(r:number,m:THREE.Material,x=0,y=0,z=0,p:THREE.Object3D=content)=>{const o=mesh(geo('sphere',()=>new THREE.SphereGeometry(1,lite?12:20,12)),m,x,y,z,p);o.scale.setScalar(r);return o;};
 const group=(name:string,x=0,y=0,z=0)=>{const g=new THREE.Group();g.name=name;g.position.set(x,y,z);content.add(g);return g;};
 function batch(name:string,m:THREE.Material,items:number[][]){const o=new THREE.InstancedMesh(geo('cube',()=>new THREE.BoxGeometry(1,1,1)),m,items.length),dummy=new THREE.Object3D();items.forEach(([x,y,z,w,h,d,ry=0],i)=>{dummy.position.set(x,y,z);dummy.rotation.set(0,ry,0);dummy.scale.set(w,h,d);dummy.updateMatrix();o.setMatrixAt(i,dummy.matrix);});o.name=name;o.castShadow=!lite;o.receiveShadow=!lite;o.instanceMatrix.needsUpdate=true;content.add(o);return o;}
 function beam(a:THREE.Vector3,b:THREE.Vector3,width:number,m:THREE.Material,p:THREE.Object3D=content){const o=box(width,a.distanceTo(b),width,m,0,0,0,p);o.position.copy(a).add(b).multiplyScalar(.5);o.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),b.clone().sub(a).normalize());return o;}
 function outline(w:number,h:number,d:number,color:string,x:number,y:number,z:number,p:THREE.Object3D=content){const m=new THREE.LineBasicMaterial({color,transparent:true,opacity:.85,toneMapped:false});materials.push(m);const o=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(w,h,d)),m);o.position.set(x,y,z);p.add(o);return o;}
 function light(x:number,y:number,z:number,color:string,power=45){const o=new THREE.PointLight(color,power,18,2);o.position.set(x,y,z);if(!lite)content.add(o);return o;}
 function monitor(x:number,y:number,z:number,w=2.5,h=1.5,p:THREE.Object3D=content){box(w+.15,h+.15,.18,dark,x,y,z,p);box(w,h,.025,glass,x,y,z+.11,p);box(w*.7,.035,.02,emit,x-w*.06,y+h*.28,z+.135,p);for(let n=0;n<4;n++)box(w*(.3+(n%3)*.13),.025,.02,pale,x-w*.1,y+h*.08-n*.18,z+.135,p);box(.12,.6,.12,steel,x,y-h/2-.3,z,p);box(w*.5,.06,.5,dark,x,y-h/2-.6,z,p);}
 function person(x:number,z:number){const g=group('illustrative-person',x,0,z);ball(.19,warm,0,1.65,0,g);box(.48,.65,.26,accent,0,1.15,0,g);for(const n of [-1,1]){box(.15,.68,.16,dark,n*.14,.5,0,g);box(.16,.58,.17,warm,n*.34,1.12,0,g);box(.2,.12,.32,rubber,n*.14,.1,.06,g);}return g;}
 function plant(x:number,z:number){cyl(.48,.65,warm,x,.35,z);for(let n=0;n<4;n++){const o=ball(.48,material(n%2?'#55796b':'#315b51'),x+Math.sin(n*2)*.25,1+n*.27,z);o.scale.y*=1.5;}}
 function backdrop<T extends THREE.Object3D>(object:T){object.userData.cameraBackdrop=true;return object;}
 function floor(color:string,size=50){const m=material(color,.18,.78);backdrop(box(size,.12,size,m,0,-.08,0)).name='continuous-ground';}
 function detection(g:THREE.Object3D,w:number,h:number,d:number){outline(w,h,d,palette.accent,0,h/2,0,g);}
 // The ID influences layout details without role-order dependence.
 const variation=(seed%5)*.13;
 if(kind==='warehouse'){
  floor('#39464d');const orange=material('#dd843c',.3,.5),blue=material('#254e6f',.45,.38),concrete=material('#58636a',.1,.95);
  backdrop(box(28,10,.3,concrete,0,5,-18));backdrop(box(.3,10,35,concrete,-14,5,-1));backdrop(box(.3,10,35,concrete,14,5,-1));
  const rackSteel:number[][]=[],rackOrange:number[][]=[],crates:number[][]=[],tape:number[][]=[];
  for(const side of [-1,1])for(const z of [-12,-5,2]){
   const x=side*6.5;for(const dx of [-2.1,2.1])for(const dz of [-2.4,2.4])rackSteel.push([x+dx,3.6,z+dz,.17,7.2,.17]);
   for(let level=0;level<3;level++){const y=.6+level*2.2;rackOrange.push([x,y,z,4.5,.16,5]);for(const dx of [-1.15,1.15])for(const dz of [-1.2,1.2])crates.push([x+dx,y+.7,z+dz,1.7,1.25+(level%2)*.2,1.8]);}
  }
  batch('blue-rack-uprights',blue,rackSteel);batch('orange-shelf-beams',orange,rackOrange);batch('stacked-cargo',warm,crates);
  const trusses:number[][]=[];for(const z of [-16,-9,-2,5,12]){trusses.push([0,9,z,27,.22,.24]);for(const x of [-12,12])trusses.push([x,4.5,z,.25,9,.25]);box(8,.1,.24,white,0,8.8,z);box(7.5,.03,.18,emit,0,8.71,z);}
  batch('structural-trusses',steel,trusses);light(0,7,-8,'#d7eeff',140);light(0,6,5,'#ffd28d',95);
  for(let n=0;n<24;n++)for(const x of [-3.15,3.15])tape.push([x,.015,-16+n*1.3,.11,.025,.85]);batch('aisle-safety-markings',accent,tape);
  for(const x of [-2.5,0,2.5]){box(2,3,.08,dark,x,2,-17.8);box(1.8,2.6,.04,steel,x,2,-17.73);}
  monitor(-10,3,-7,3.5,2);const camera=group('safety-camera',-3.8,7,-8);box(.7,.35,1,white,0,0,0,camera);ball(.17,glass,0,0,.53,camera);
  const forklift=group('animated-forklift',-.65,0,3);box(1.5,.7,2.3,orange,0,.8,0,forklift);box(1.45,.6,.8,dark,0,1.4,-.5,forklift);for(const x of [-.65,.65]){box(.09,2.4,.09,dark,x,2,.4,forklift);box(.1,2.8,.12,steel,x,1.5,1.1,forklift);box(.12,.13,1.7,steel,x,.18,1.8,forklift);}box(1.6,.12,1.4,blue,0,3.2,0,forklift);for(const x of [-.78,.78])for(const z of [-.75,.75]){const w=cyl(.37,.2,rubber,x,.4,z,forklift);w.rotation.z=Math.PI/2;}
  const worker=person(2,1);detection(worker,.9,2, .8);outline(5,.025,7,palette.accent,0,.035,-4);
  const scan=box(5,.015,.08,emit,0,.08,-4);animations.push(t=>{forklift.position.z=2+Math.sin(t*.23)*3.2;scan.position.z=-7+(t*.8%6);});
  const cratesDock=group('loading-dock',10,.0,10);for(let n=0;n<3;n++)box(1.5,1.2,1.4,warm,0,.6+n*1.23,0,cratesDock);
 }else if(kind==='intersection'){
  floor('#293143');const asphalt=material('#151d2a',.25,.7),curb=material('#7a899a'),amber=glow('#ffbb68'),window=glow('#83c6dc',.8);
  backdrop(box(8,.04,50,asphalt,0,.01,0));backdrop(box(50,.04,8,asphalt,0,.015,0));
  const windows:number[][]=[],markings:number[][]=[];
  for(const x of [-10,-17,10,17])for(const z of [-10,10]){const h=5+(Math.abs(x)+Math.abs(z)+seed%7)%10;box(5.8,h,6,steel,x,h/2,z);box(6.1,.25,6.3,dark,x,h+.1,z);for(let row=0;row<Math.floor(h/1.1);row++)for(let col=0;col<4;col++)windows.push([x-1.9+col*1.25,.8+row*1.1,z+(z<0?3.02:-3.02),.55,.55,.035]);}
  batch('city-lit-windows',window,windows);for(const x of [-6.3,6.3])for(const z of [-6.3,6.3])box(3.4,.2,3.4,curb,x,.1,z);
  for(let n=-20;n<=20;n+=3)if(Math.abs(n)>5){markings.push([0,.05,n,.08,.015,1.5],[n,.05,0,1.5,.015,.08]);}
  for(const s of [-1,1])for(let n=-3;n<=3;n++){markings.push([n*.8,.05,s*5,.45,.015,2],[s*5,.05,n*.8,2,.015,.45]);}batch('crosswalk-and-lanes',white,markings);
  for(const x of [-5.8,5.8])for(const z of [-5.8,5.8]){cyl(.07,5,steel,x,2.5,z);box(1.6,.08,.12,steel,x-.7,5,z);box(.75,.06,.3,emit,x-1.2,4.95,z);light(x,4.4,z,'#8ecaff',30);box(.4,1.1,.3,dark,x,3.2,z);for(let n=0;n<3;n++)ball(.1,n===1?amber:dark,x,3.5-n*.3,z+.17);}
  function car(name:string,color:string,x:number,z:number,turn=false){const g=group(name,x,0,z);if(turn)g.rotation.y=Math.PI/2;const paint=material(color,.65,.25);box(1.65,.55,3.3,paint,0,.65,0,g);box(1.4,.6,1.7,glass,0,1.18,-.2,g);box(1.5,.1,1.8,paint,0,1.5,-.2,g);for(const a of [-.87,.87])for(const b of [-1.05,1.05]){const w=cyl(.34,.18,rubber,a,.37,b,g);w.rotation.z=Math.PI/2;}for(const a of [-.55,.55])box(.32,.16,.035,white,a,.73,1.68,g);detection(g,2.1,1.85,3.9);return g;}
  const cars=[car('tracked-car-a','#caa278',-2,-7),car('tracked-car-b','#527b98',2,9),car('tracked-car-c','#a96c7f',9,2,true)];
  const pedestrian=person(6.6,3);detection(pedestrian,.85,2.05,.8);animations.push(t=>{cars[0].position.z=((t*1.15+4)%28)-14;cars[1].position.z=14-((t*.9+13)%28);cars[2].position.x=14-((t*.7+5)%28);});
 }else if(kind==='solar'){
  floor('#6f826e',64);const solar=material('#153d63',.7,.24),silver=material('#93b0c3',.7,.3),hills=material('#6a7c70',.05,1);
  const faces:number[][]=[],cells:number[][]=[],legs:number[][]=[];
  for(let row=0;row<5;row++)for(let col=0;col<7;col++){const x=-12+col*4,z=-14+row*5;faces.push([x,1.25,z,3.5,.14,2.8]);legs.push([x-.95,.6,z,.09,1.2,.09],[x+.95,.6,z,.09,1.2,.09]);for(let n=0;n<5;n++)cells.push([x-1.4+n*.7,1.33,z,.018,.02,2.6]);for(const dz of [-.8,.0,.8])cells.push([x,1.33,z+dz,3.3,.02,.015]);}
  batch('photovoltaic-panels',solar,faces);batch('panel-cell-grid',silver,cells);batch('panel-supports',steel,legs);
  for(let n=0;n<7;n++){const o=backdrop(mesh(geo('hill',()=>new THREE.SphereGeometry(1,16,10)),hills,-28+n*9,0,-28));o.scale.set(7,3+(n%3)*2,5);}
  backdrop(box(3,.035,40,warm,0,.025,0));const drone=group('inspection-drone',3,5.5,1);box(.8,.22,.65,white,0,0,0,drone);ball(.15,glass,0,-.25,.2,drone);
  const rotors:THREE.Object3D[]=[];for(const x of [-.8,.8])for(const z of [-.6,.6]){beam(new THREE.Vector3(0,0,0),new THREE.Vector3(x,0,z),.07,steel,drone);cyl(.13,.18,dark,x,.1,z,drone);rotors.push(box(.8,.025,.09,dark,x,.22,z,drone));}
  outline(3.7,.15,3,palette.accent,4,1.4,1);const scan=box(3.6,.025,.06,emit,4,1.4,1);animations.push(t=>{drone.position.set(3+Math.sin(t*.22)*2,5.5+Math.sin(t*.8)*.18,1+Math.cos(t*.22)*2);rotors.forEach(r=>r.rotation.y=t*18);scan.position.z=-.3+(t*.6%2.6);});
  const sun=backdrop(ball(2.4,glow('#ffdc9e',1.3),-22,15,-25));sun.name='illustrative-sun';sun.userData.cameraSolid=false;
 }else if(kind==='news'){
  floor('#48404c');const wood=material('#80604f',.05,.85),paper=material('#e1d6c3',.05,.9),purple=glow('#b88dff',1.1);
  backdrop(box(28,9,.25,dark,0,4.5,-13));for(const x of [-13,13])backdrop(box(.2,9,26,steel,x,4.5,0));
  for(const x of [-9,9]){box(4.8,6.8,1.5,wood,x,3.4,-11);for(let row=0;row<5;row++){box(4.9,.1,1.65,paper,x,.6+row*1.25,-10.9);const books:number[][]=[];for(let n=0;n<12;n++)books.push([x-2+n*.35,1+row*1.25,-10.7,.22,.6+(n%3)*.12,.9]);batch('reference-volumes-'+x+'-'+row,nthMaterial(row),books);}}
  function nthMaterial(n:number){return [warm,accent,steel,paper][n%4];}
  box(9,.25,3.5,wood,0,1.8,0);for(const x of [-3.7,3.7])for(const z of [-1.2,1.2])box(.12,1.8,.12,dark,x,.9,z);
  monitor(0,3.35,-.65,3.5,2);box(1.8,.08,.6,dark,0,1.98,.8);for(let n=0;n<6;n++){const p=box(1.2,.025,1.5,paper,-2.9+n*.12,2.01+n*.035,.15);p.rotation.y=-.25+n*.08;}
  cyl(.25,.5,white,2.2,2.18,.8);box(2.7,.08,.03,purple,0,1.65,1.8);const deskLamp=group('editorial-lamp',3.4,1.95,-.7);cyl(.3,.07,dark,0,0,0,deskLamp);beam(new THREE.Vector3(0,0,0),new THREE.Vector3(.1,1.6,0),.06,steel,deskLamp);const shade=mesh(new THREE.ConeGeometry(.5,.5,20,1,true),warm,-.2,1.6,0,deskLamp);shade.rotation.z=.5;light(2.9,3.4,0,'#ffd09d',35);
  const boards=group('editorial-analysis-wall',0,4,-12.7);for(let n=0;n<3;n++){box(3.4,2.7,.08,glass,-4+n*4,0,0,boards);for(let line=0;line<6;line++)box(2.5-(line%3)*.3,.05,.03,line%2?accent:white,-4+n*4,line*.32-.8,.06,boards);}
  const cursor=box(.04,.25,.025,emit,1,3.4,-.52);animations.push(t=>{cursor.visible=Math.sin(t*2)>-.25;cursor.position.y=3.4-Math.floor(t*.4%4)*.18;});plant(-7,4);plant(8,2);
 }else if(kind==='systems'){
  floor('#1e3040');const server=material('#122333',.7,.32),led=glow('#4bdeea',1.4);const fronts:number[][]=[],indicators:number[][]=[];
  for(const side of [-1,1])for(let row=0;row<4;row++){const x=side*6,z=-12+row*5;box(2.5,6,3.6,server,x,3,z);for(let n=0;n<9;n++){fronts.push([x, .5+n*.62,z+1.84,2.1,.42,.1]);indicators.push([x+.7,.5+n*.62,z+1.91,.12,.06,.03]);}}
  batch('server-bays',steel,fronts);batch('server-status-lights',led,indicators);
  const pipes:number[][]=[];for(let x=-3;x<=3;x++)pipes.push([x,.02,-2,.025,.025,33]);batch('floor-data-traces',emit,pipes);
  for(const z of [-13,-5,3,11]){box(16,.1,.15,steel,0,7.5,z);box(6,.03,.12,led,0,7.4,z);}monitor(0,3,-15,6,3);
  const packets=Array.from({length:lite?5:12},(_,n)=>box(.15,.12,.45,emit,(n%5)-2,.16,-14+n*2));animations.push(t=>packets.forEach((o,n)=>o.position.z=-16+(t*(2+n%3)+n*2)%32));light(0,5,-4,'#66dfff',75);
 }else if(kind==='web'){
  floor('#5c6872');const wall=material('#9dacae',.15,.8),wood=material('#7f7667',.1,.9);backdrop(box(25,8,.25,wall,0,4,-10));backdrop(box(.2,8,23,wall,-12,4,0));
  for(let n=0;n<5;n++){box(3.7,5,.1,glass,-8+n*4,4,-9.8);box(.06,5,.08,white,-6+n*4,4,-9.65);}
  box(10,.22,4,wood,0,1.8,0);for(const x of [-4,4])box(.18,1.8,3,dark,x,.9,0);monitor(-1,3.5,-.6,4.4,2.7);
  const phone=group('responsive-phone',3,2.8,.5);phone.rotation.y=-.25;box(1.05,1.9,.14,dark,0,0,0,phone);box(.92,1.7,.02,accent,0,0,.09,phone);for(let n=0;n<4;n++)box(.65,.08,.02,pale,0,.4-n*.25,.11,phone);
  const tablet=group('responsive-tablet',-4,2.6,.4);tablet.rotation.y=.2;box(1.9,1.35,.12,dark,0,0,0,tablet);box(1.75,1.2,.02,glass,0,0,.08,tablet);plant(8,-4);plant(-8,4);box(5,.03,.1,emit,0,1.6,2.02);light(1,5,1,'#b1ffde',65);
 }else if(kind==='vision'){
  floor('#2a354c');backdrop(box(24,8,.25,dark,0,4,-12));for(const x of [-10,10]){backdrop(box(.16,7,22,steel,x,3.5,-1));box(.03,5,.1,emit,x,3,-2);}
  const gantry=group('perception-gantry',0,0,-1);for(const x of [-5,5])box(.25,6,.25,pale,x,3,0,gantry);box(10,.25,.25,pale,0,6,0,gantry);monitor(-6.5,3,-6,3,2);
  const subject=group('scan-subject',0,1.3,-1);const object=mesh(new THREE.IcosahedronGeometry(1.5,1),accent,0,1,0,subject);cyl(2,.3,dark,0,-.25,0,subject);detection(subject,4.2,3.5,4.2);const scan=box(5,.02,.08,emit,0,2,-1);animations.push(t=>{object.rotation.y=t*.18;scan.position.y=.5+(t*.6%4.5);});light(0,5,-1,'#99adff',80);
 }else{
  floor('#55484b');const wood=material('#765344',.05,.92);backdrop(box(26,9,.3,wood,0,4.5,-12));for(const x of [-10,10])for(const z of [-8,-2,4]){box(2.5,6.5,2,wood,x,3.25,z);for(let row=0;row<5;row++){box(2.6,.08,2.05,accent,x,.5+row*1.2,z);const books:number[][]=[];for(let n=0;n<7;n++)books.push([x-1+n*.3,.9+row*1.2,z+.4,.22,.7,.9]);batch('archive-books-'+x+'-'+z+'-'+row,nth(row),books);}}
  function nth(n:number){return [warm,pale,steel][n%3];}
  box(7,.18,4,wood,0,1.7,0);for(const x of [-2.8,2.8])box(.15,1.7,3,dark,x,.85,0);box(2,.04,1.4,white,0,1.83,0);cyl(.35,.1,accent,2.5,1.9,-.8);light(0,5,0,'#ffcf94',90);
 }
 // Different identities within a category get a small stable framing landmark.
 const landmark=box(.08,1.8,.08,emit,-4.5-variation,.9,8);landmark.name='project-identity-marker';
 return {root,moving:[] as THREE.Object3D[],materials,kind,color:palette.accent,palette,animate:(t:number)=>animations.forEach(fn=>fn(t))};
}

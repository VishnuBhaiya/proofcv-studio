import * as THREE from 'three';
import type { Project } from './types';
import { worldStations,stationLabel } from './worldLayout';
import { coverScene } from './projectVisuals';

/** The original purple island entrance. Project worlds are separate destinations. */
export function createIsland(projects:Project[],lite=false){
 const root=new THREE.Group();root.name='purple-floating-island';
 const groups:THREE.Group[]=[],moving:THREE.Object3D[]=[],rims:THREE.Mesh[]=[],textures:THREE.Texture[]=[];
 const mat=(color:string,metalness=.25,roughness=.45)=>new THREE.MeshStandardMaterial({color,metalness,roughness});
 const dark=mat('#22254b'),wall=mat('#344067'),steel=mat('#8d9fc9',.7,.25),ground=mat('#30355e',.3,.7),stone=mat('#535384',.05,.9),pink=mat('#b557a6',.45,.3);
 const neon=(color:string)=>new THREE.MeshStandardMaterial({color,emissive:color,emissiveIntensity:2.2,toneMapped:false});
 const mint=neon('#63dfff'),violet=neon('#b28bff'),rose=neon('#ff81cf'),warm=neon('#ffe2ac');
 const inset=mat('#121f39',.45,.5),interior=mat('#456078',.25,.7),brass=mat('#bb9e78',.55,.38);
 const screen=new THREE.MeshStandardMaterial({color:'#5eb8ca',emissive:'#3897b6',emissiveIntensity:.75,metalness:.15,roughness:.4});
 const materials:THREE.Material[]=[dark,wall,steel,ground,stone,pink,mint,violet,rose,warm,inset,interior,brass,screen];
 function mesh(g:THREE.BufferGeometry,m:THREE.Material,parent:THREE.Object3D=root,x=0,y=0,z=0){const object=new THREE.Mesh(g,m);object.position.set(x,y,z);object.castShadow=!lite;object.receiveShadow=!lite;parent.add(object);return object;}
 const box=(w:number,h:number,d:number,m:THREE.Material,parent:THREE.Object3D=root,x=0,y=0,z=0)=>mesh(new THREE.BoxGeometry(w,h,d),m,parent,x,y,z);
 // Small real bevels catch the key light without a heavy post-processing effect.
 function bevel(w:number,h:number,d:number,m:THREE.Material,parent:THREE.Object3D=root,x=0,y=0,z=0){const b=Math.min(.035,w/8,h/8,d/8),shape=new THREE.Shape(),left=-w/2+b,bottom=-h/2+b;shape.moveTo(left,bottom);shape.lineTo(-left,bottom);shape.lineTo(-left,-bottom);shape.lineTo(left,-bottom);shape.closePath();const geometry=new THREE.ExtrudeGeometry(shape,{depth:d-b*2,bevelEnabled:true,bevelSize:b,bevelThickness:b,bevelSegments:1,steps:1});geometry.translate(0,0,-d/2+b);return mesh(geometry,m,parent,x,y,z);}
 const cyl=(r:number,b:number,h:number,m:THREE.Material,parent:THREE.Object3D=root,x=0,y=0,z=0,n=12)=>mesh(new THREE.CylinderGeometry(r,b,h,n),m,parent,x,y,z);
 const ring=(r:number,t:number,m:THREE.Material,parent:THREE.Object3D=root,x=0,y=0,z=0)=>mesh(new THREE.TorusGeometry(r,t,8,lite?40:64),m,parent,x,y,z);
 function sign(text:string,parent:THREE.Object3D,x:number,y:number,z:number,w=1.5,h=.37){const canvas=document.createElement('canvas');canvas.width=768;canvas.height=192;const c=canvas.getContext('2d')!;c.fillStyle='#141d3b';c.fillRect(0,0,768,192);c.strokeStyle='#b9e5ff';c.lineWidth=7;c.strokeRect(13,13,742,166);c.fillStyle='#d3e7ff';c.font='600 55px Segoe UI,Arial,sans-serif';c.textAlign='center';c.textBaseline='middle';c.fillText(text,384,100,700);const t=new THREE.CanvasTexture(canvas);t.colorSpace=THREE.SRGBColorSpace;textures.push(t);return mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshBasicMaterial({map:t,toneMapped:false}),parent,x,y,z);}
 cyl(7.3,6.9,.65,ground,root,0,0,0,8).rotation.y=Math.PI/8;
 cyl(6.85,4.7,1.5,dark,root,0,-1.05,0,8).rotation.y=Math.PI/8;
 cyl(4.5,2.8,.8,wall,root,0,-2.15,0,7).rotation.y=.2;
 ring(7.05,.035,violet,root,0,.31,0).rotation.x=-Math.PI/2;
 ring(5.8,.04,mint,root,0,-1.65,0).rotation.x=-Math.PI/2;
 // Visible layers, edge recesses and maintenance panels make the floating base tactile.
 const deck=mesh(new THREE.RingGeometry(6.55,6.67,lite?32:64),steel,root,0,.334,0);deck.rotation.x=-Math.PI/2;
 const innerDeck=mesh(new THREE.RingGeometry(3.48,3.51,48),interior,root,0,.336,0);innerDeck.rotation.x=-Math.PI/2;
 for(let n=0;n<8;n++){const a=n*Math.PI/4+Math.PI/8,g=new THREE.Group();g.position.set(Math.sin(a)*6.18,-.7,Math.cos(a)*6.18);g.rotation.y=a;root.add(g);bevel(1.02,.38,.12,inset,g);for(let vent=0;vent<(lite?2:4);vent++)box(.12,.018,.025,steel,g,-.3+vent*.2,.03,.076);box(.22,.025,.02,n%2?mint:violet,g,0,-.12,.078);}
 const hatch=new THREE.Group();hatch.name='deck-service-hatch';hatch.position.set(2.2,.35,.3);root.add(hatch);cyl(.56,.56,.045,inset,hatch);const hatchRim=ring(.54,.018,steel,hatch,0,.035,0);hatchRim.rotation.x=-Math.PI/2;for(const x of [-.2,.2])box(.12,.025,.12,brass,hatch,x,.04,0);
 const studio=new THREE.Group();studio.name='original-workshop';studio.position.set(-.9,.38,-2.1);root.add(studio);
 bevel(5.6,.2,3.1,steel,studio,0,.13,0);
 // A genuinely recessed room: side/back walls and workstations are visible through the glass.
 box(5.2,2.25,.16,wall,studio,0,1.3,-1.32);for(const x of [-2.52,2.52])box(.16,2.25,2.8,wall,studio,x,1.3,0);
 box(4.9,.07,2.5,interior,studio,0,.28,0);box(4.9,.15,.12,inset,studio,0,2.19,-1.2);
 bevel(5.45,.2,3.1,dark,studio,0,2.52,0);bevel(5.6,.07,3.2,pink,studio,0,2.65,0);
 box(4.8,.48,.12,dark,studio,0,.45,1.46);box(4.8,.28,.12,dark,studio,0,1.94,1.46);
 const glazing=new THREE.MeshStandardMaterial({color:'#73acc3',metalness:.12,roughness:.14,transparent:true,opacity:.2,depthWrite:false});materials.push(glazing);
 for(let n=0;n<4;n++){box(.95,1.05,.018,glazing,studio,-1.8+n*1.2,1.26,1.53);box(.025,1.15,.08,steel,studio,-2.34+n*1.2,1.25,1.59);}
 for(const x of [-1.45,1.45]){bevel(1.25,.09,.67,brass,studio,x,.87,.36);for(const dx of [-.47,.47])box(.055,.55,.055,steel,studio,x+dx,.56,.25);box(.63,.4,.065,inset,studio,x,1.18,.13);box(.53,.3,.015,screen,studio,x,1.18,.17);box(.055,.1,.055,steel,studio,x,.94,.13);box(.4,.025,.17,inset,studio,x,.94,.54);box(1.25,.025,.13,screen,studio,x,2.25,.1);}
 box(.05,1.4,.05,steel,studio,0,1.05,1.55);bevel(.12,.025,.035,brass,studio,.16,1.03,1.62);
 box(5.05,.04,.06,mint,studio,0,.68,1.6);bevel(5.8,.1,1.3,pink,studio,0,1.95,1.6).rotation.x=.12;sign('THE WORKSHOP',studio,0,2.3,1.64,3.9,.62);
 if(!lite){for(const z of [-1,.1,1.12])box(4.95,.035,.035,steel,studio,0,2.7,z);for(const x of [-2.2,2.2]){box(.3,.19,.25,inset,studio,x,2.82,-.6);for(let n=0;n<3;n++)box(.19,.012,.02,steel,studio,x,2.92,-.67+n*.055);}}
 for(const x of [-2.5,2.5]){cyl(.045,.045,1.7,steel,studio,x,.95,2.05);box(.13,.1,.13,rose,studio,x,1.82,2.05);}
 for(let n=0;n<5;n++)box(3.7,.09,.2,steel,studio,0,.1+n*.055,2.8-n*.2);
 const orrery=new THREE.Group();orrery.position.set(0,3.45,-1.8);root.add(orrery);moving.push(orrery);cyl(.4,.65,.45,steel,root,0,2.85,-1.8);
 for(let n=0;n<3;n++)ring(.85+n*.13,.035,n%2?mint:rose,orrery).rotation.set(n*.7,Math.PI/3+n*.4,.3);
 mesh(new THREE.IcosahedronGeometry(.39,1),steel,orrery);
 const dishGroup=new THREE.Group();dishGroup.position.set(-3,3.15,-2.4);root.add(dishGroup);cyl(.045,.045,1.3,steel,dishGroup);const dish=mesh(new THREE.SphereGeometry(.65,16,8,0,Math.PI*2,0,Math.PI/2),steel,dishGroup,0,.55,0);dish.rotation.set(.4,0,-.6);
 const tower=new THREE.Group();tower.name='original-server-tower';tower.position.set(4.1,.4,-2.1);root.add(tower);cyl(1.1,1.3,.2,steel,tower,0,.1,0);bevel(1.4,2.6,1.4,dark,tower,0,1.5,0);
 for(let n=0;n<5;n++){box(1.1,.26,.08,steel,tower,0,.55+n*.43,.75);box(.14,.05,.02,n%2?rose:mint,tower,.33,.56+n*.43,.81);}
 for(const x of [-.72,.72]){box(.04,2.35,.045,steel,tower,x,1.5,.73);if(!lite)for(let n=0;n<6;n++)box(.02,.045,.4,inset,tower,x,.6+n*.32,0);}
 bevel(1.05,.24,.08,inset,tower,0,2.57,.75);for(let n=0;n<3;n++)box(.12,.025,.02,screen,tower,-.28+n*.25,2.57,.8);
 cyl(.035,.035,1.8,steel,tower,0,3.7,0);mesh(new THREE.SphereGeometry(.12,12,8),rose,tower,0,4.6,0);
 const treeA=mat('#41477f',.1,.85),treeB=mat('#5b63a7',.1,.85);materials.push(treeA,treeB);
 for(const [x,z,s] of [[-5.7,-2.6,.8],[-4.9,-4,1],[-3.3,-5.1,.7],[2.7,-5.2,.9],[5.4,-3.5,.7],[6,-.6,.65],[-6,.2,.55]]){const g=new THREE.Group();g.position.set(x,.38,z);g.scale.setScalar(s);root.add(g);cyl(.1,.13,.9,steel,g,0,.45,0);for(let n=0;n<3;n++)mesh(new THREE.ConeGeometry(.65-n*.12,1.1,5),n%2?treeB:treeA,g,0,1+n*.55,0);}
 for(let n=0;n<(lite?10:22);n++){const a=n*2.399963,r=5.6+(n%3)*.23;mesh(new THREE.DodecahedronGeometry(.09+(n%3)*.045),stone,root,Math.cos(a)*r,.48,Math.sin(a)*r);}
 for(const x of [-3.2,3.2])for(const z of [0,2.8]){cyl(.035,.035,.85,steel,root,x,.78,z);mesh(new THREE.SphereGeometry(.12,10,8),warm,root,x,1.24,z);}
 for(let n=0;n<16;n++){const a=n*Math.PI*2/16;box(.17,.025,.08,n%2?mint:violet,root,Math.sin(a)*5,.37,Math.cos(a)*5);}
 const stations=worldStations(projects);
 for(const s of stations){const g=new THREE.Group();g.position.set(...s.position);g.rotation.y=Math.atan2(s.position[0],s.position[2]);const kind=coverScene(s.project);g.userData={index:s.index,projectId:s.project.id,kind,symbolic:true};root.add(g);groups.push(g);cyl(.95,1.03,.19,steel,g,0,.02,0);const halo=ring(.97,.045,s.index%2?rose:mint,g,0,.14,0);halo.rotation.x=-Math.PI/2;rims.push(halo);bevel(1.5,.15,.72,dark,g,0,.83,0);for(const x of [-.57,.57])box(.07,.75,.5,steel,g,x,.42,0);box(.08,.6,.08,steel,g,0,1.16,-.08);bevel(1.65,1.03,.12,dark,g,0,1.72,-.12);sign(String(s.index+1).padStart(2,'0')+' / '+stationLabel(s.project.title,19),g,0,1.98,-.045);box(1.3,.025,.035,s.index%2?rose:mint,g,0,1.47,-.04);for(let n=0;n<3;n++)box(.24,.09+n*.08,.04,s.index%2?violet:mint,g,-.4+n*.4,1.63,-.04);moving.push(mesh(new THREE.OctahedronGeometry(.25),s.index%2?rose:mint,g,.95,1.18,.1));
  // A small tactile icon on each original console identifies the destination.
  // These are wayfinding objects, not miniature replacement worlds or project evidence.
  const marker=new THREE.Group();marker.name='destination-marker-'+kind;marker.position.set(0,.95,.15);marker.userData={kind,projectId:s.project.id,symbolic:true};g.add(marker);
  if(kind==='intersection'){bevel(.66,.035,.32,inset,marker);bevel(.28,.035,.62,inset,marker,0,.01,0);for(const x of [-.22,.22])box(.07,.012,.015,warm,marker,x,.035,0);for(const z of [-.2,.2])box(.015,.012,.07,warm,marker,0,.046,z);}
  else if(kind==='warehouse'){bevel(.6,.05,.34,brass,marker);for(const x of [-.16,.16]){bevel(.24,.2,.23,interior,marker,x,.12,0);box(.035,.205,.24,brass,marker,x,.125,0);}}
  else if(kind==='solar'){const panel=new THREE.Group();panel.rotation.x=-.24;panel.position.y=.13;marker.add(panel);bevel(.66,.045,.37,inset,panel);for(let n=0;n<4;n++)box(.012,.015,.31,screen,panel,-.25+n*.165,.032,0);for(const x of [-.22,.22])box(.025,.11,.025,steel,marker,x,.03,0);}
  else if(kind==='news'){for(let n=0;n<3;n++){const page=bevel(.42,.025,.34,interior,marker,-.1,.035+n*.035,0);page.rotation.y=n*.13;}const lens=ring(.14,.018,brass,marker,.2,.18,.02);lens.rotation.x=-.6;box(.025,.16,.025,steel,marker,.28,.065,.09).rotation.z=-.6;}
  else if(kind==='systems'){for(let n=0;n<3;n++)bevel(.45,.04,.33,n%2?screen:steel,marker,0,.04+n*.075,0);box(.05,.05,.015,mint,marker,.14,.19,.18);}
  else if(kind==='web'){bevel(.48,.3,.055,inset,marker,-.06,.16,0);box(.39,.21,.016,screen,marker,-.06,.18,.035);bevel(.12,.22,.035,steel,marker,.27,.12,.12);box(.08,.16,.01,screen,marker,.27,.13,.143);}
  else if(kind==='vision'){bevel(.4,.2,.24,inset,marker,0,.12,0);cyl(.095,.095,.085,steel,marker,0,.13,.16).rotation.x=Math.PI/2;cyl(.065,.065,.09,screen,marker,0,.13,.17).rotation.x=Math.PI/2;}
  else for(let n=0;n<3;n++){bevel(.09,.23+n*.025,.3,n%2?brass:interior,marker,-.13+n*.13,.12+n*.013,0);}
 }
 return {root,groups,moving,rims,textures,materials,stations};
}

import * as THREE from 'three';
export { createImmersiveEnvironment as createProjectEnvironment,WORLD_PALETTES } from './immersiveEnvironments';

type Shot={label:string;position:[number,number,number];target:[number,number,number]};
/** The entrance is an eye-level composition. Only the last shot is a fitted overview. */
export function projectShots(kind:string):Shot[]{
 const shots:Record<string,Shot[]>={
  warehouse:[
   {label:'Inside the warehouse',position:[.5,3.5,11],target:[0,2.7,-8]},
   {label:'Safety-zone camera',position:[-2,5.8,6],target:[.6,1.3,-5]},
   {label:'Whole environment',position:[14,18,27],target:[0,3.5,-3]}],
  intersection:[
   {label:'City at blue hour',position:[3.2,4.6,13],target:[-1.5,1.4,-2]},
   {label:'Street-level tracking',position:[2.5,2.8,10],target:[-1,1,-3]},
   {label:'Traffic overview',position:[30,27,30],target:[0,2,0]}],
  solar:[
   {label:'Into the solar field',position:[10,4.8,13],target:[0,1.4,-6]},
   {label:'Drone inspection',position:[5,7,7],target:[3,1.3,0]},
   {label:'Field overview',position:[32,25,32],target:[0,2,-4]}],
  news:[
   {label:'The editorial studio',position:[6.2,4.3,7.8],target:[0,2.7,-1]},
   {label:'At the analysis desk',position:[-2.4,3.8,5.4],target:[0,2.9,-.8]},
   {label:'Studio overview',position:[24,20,25],target:[0,2,-2]}],
  systems:[
   {label:'Inside the data centre',position:[0,3.5,11],target:[0,3,-9]},
   {label:'Follow the data',position:[-.8,4.4,5],target:[.4,1,-8]},
   {label:'Systems overview',position:[12,15,24],target:[0,2.8,-3]}],
  web:[
   {label:'The interface studio',position:[7.2,4.5,8],target:[-.5,2.8,-1]},
   {label:'Responsive workspace',position:[-2,4.4,5],target:[1.2,2.7,0]},
   {label:'Studio overview',position:[25,21,28],target:[0,2,-1]}],
  vision:[
   {label:'Inside the vision lab',position:[7.8,4,9.5],target:[0,2.6,-1]},
   {label:'The perception scanner',position:[2.7,3.7,5.3],target:[0,2.3,-1]},
   {label:'Lab overview',position:[25,22,28],target:[0,2,-2]}],
  notes:[
   {label:'The research archive',position:[6,3.7,9],target:[0,2.3,-2]},
   {label:'At the research table',position:[-2,3.3,5],target:[0,1.8,0]},
   {label:'Archive overview',position:[25,21,28],target:[0,2,-2]}]
 };
 return shots[kind]||shots.notes;
}

/** Frame the subject, not the huge continuous floor or distant atmosphere. */
export function projectCameraGeometry(root:THREE.Object3D){
 root.updateMatrixWorld(true);
 const subject=new THREE.Box3(),solids:THREE.Box3[]=[],instance=new THREE.Matrix4(),world=new THREE.Matrix4();
 function inherited(object:THREE.Object3D,key:string,value:unknown){for(let p:THREE.Object3D|null=object;p;p=p.parent)if(p.userData[key]===value)return true;return false;}
 root.traverse(object=>{
  if(!(object instanceof THREE.Mesh))return;
  if(!object.geometry.boundingBox)object.geometry.computeBoundingBox();
  const local=object.geometry.boundingBox!;
  const framing=!inherited(object,'cameraBackdrop',true);
  const solid=object.name!=='continuous-ground'&&!inherited(object,'cameraSolid',false);
  const add=(matrix:THREE.Matrix4)=>{const b=local.clone().applyMatrix4(matrix);if(framing)subject.union(b);if(solid&&b.max.y>.2)solids.push(b);};
  // Instanced shelves/crates must be tested separately: their aggregate AABB fills the empty aisle.
  if(object instanceof THREE.InstancedMesh){for(let n=0;n<object.count;n++){object.getMatrixAt(n,instance);world.multiplyMatrices(object.matrixWorld,instance);add(world);}}
  else add(object.matrixWorld);
 });
 if(subject.isEmpty())subject.set(new THREE.Vector3(-5,0,-5),new THREE.Vector3(5,5,5));
 return {subject,solids};
}

/** Swept camera sphere against static scenery; prevents tunnelling through racks on large gestures. */
export function constrainProjectCamera(from:THREE.Vector3,requested:THREE.Vector3,solids:THREE.Box3[],radius=.32){
 const to=requested.clone();to.y=Math.max(.65,to.y);
 const delta=to.clone().sub(from),length=delta.length();
 if(length<1e-8)return to;
 const ray=new THREE.Ray(from,delta.clone().divideScalar(length)),hit=new THREE.Vector3();let distance=length;
 for(const solid of solids){
  const b=solid.clone().expandByScalar(radius);
  // Camera presets are validated separately. A point already on a padded boundary may move away.
  if(b.containsPoint(from)){if(!b.containsPoint(to))continue;return from.clone();}
  if(ray.intersectBox(b,hit)){const d=from.distanceTo(hit);if(d<=length)distance=Math.min(distance,Math.max(0,d-.025));}
 }
 const safe=ray.at(distance,new THREE.Vector3());safe.y=Math.max(.65,safe.y);return safe;
}

/** Keep the farthest framed subject at least 80% visible through exponential fog. */
export function projectFogDensity(base:number,eye:THREE.Vector3,subject:THREE.Box3){
 const far=eye.distanceTo(subject.getCenter(new THREE.Vector3()))+subject.getSize(new THREE.Vector3()).length()/2;
 return Math.min(base,Math.sqrt(-Math.log(.8))/Math.max(1,far));
}

/** Fit meaningful subject bounds only when a visitor selects the wide overview. */
export function fitProjectOverview(bounds:THREE.Box3,aspect:number,position:THREE.Vector3,target:THREE.Vector3,fov=50){
 const camera=new THREE.PerspectiveCamera(fov,Math.max(.2,aspect),.1,500),direction=position.clone().sub(target).normalize();
 const corners:THREE.Vector3[]=[];for(const x of [bounds.min.x,bounds.max.x])for(const y of [bounds.min.y,bounds.max.y])for(const z of [bounds.min.z,bounds.max.z])corners.push(new THREE.Vector3(x,y,z));
 if(direction.lengthSq()<.1)direction.set(1,1,1).normalize();
 const fits=(distance:number)=>{camera.position.copy(target).addScaledVector(direction,distance);camera.lookAt(target);camera.updateMatrixWorld();return corners.every(corner=>{const p=corner.clone().project(camera);return Math.abs(p.x)<=.86&&Math.abs(p.y)<=.86&&p.z>=-1&&p.z<=1;});};
 let near=.5,far=Math.max(10,bounds.getSize(new THREE.Vector3()).length()*2);
 for(let n=0;n<8&&!fits(far);n++)far*=1.4;
 // Search in both directions: oversized fixed starting poses previously left the model tiny.
 for(let n=0;n<24;n++){const distance=(near+far)/2;if(fits(distance))far=distance;else near=distance;}
 return target.clone().addScaledVector(direction,far);
}

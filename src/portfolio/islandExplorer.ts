import * as THREE from 'three';
import { constrainProjectCamera } from './projectEnvironments';

export const ISLAND_EXPLORER_RADIUS=6.25;
export const ISLAND_EXPLORER_EYE_HEIGHT=2.05;
export const ISLAND_EXPLORER_SPEED=2.1;
const BODY_RADIUS=.28,LOOK_SENSITIVITY=.003,MAX_PITCH=.7;
const SPAWN=new THREE.Vector3(2.2,ISLAND_EXPLORER_EYE_HEIGHT,5.25);

/** Optional, human-controlled ground-level exploration. No pointer lock or automatic walking. */
export function createIslandExplorer(root:THREE.Object3D){
 root.updateMatrixWorld(true);
 const solids:THREE.Box3[]=[],local=new THREE.Matrix4(),world=new THREE.Matrix4();
 function excluded(object:THREE.Object3D){
  for(let ancestor:THREE.Object3D|null=object;ancestor;ancestor=ancestor.parent){
   if(ancestor.userData.cameraSolid===false||ancestor.userData.cameraBackdrop===true||ancestor.userData.explorerSolid===false)return true;
  }
  return false;
 }
 root.traverse(object=>{
  if(!(object instanceof THREE.Mesh)||excluded(object)||object.geometry.type==='TorusGeometry')return;
  object.geometry.computeBoundingBox();const bounds=object.geometry.boundingBox;if(!bounds)return;
  const add=(matrix:THREE.Matrix4)=>{
   const box=bounds.clone().applyMatrix4(matrix);
   // The floating platform, floor markings and decorative rings are not walls.
   if(box.min.y>.45&&box.max.y>=1&&box.min.y<ISLAND_EXPLORER_EYE_HEIGHT+BODY_RADIUS&&box.max.y>ISLAND_EXPLORER_EYE_HEIGHT-BODY_RADIUS)solids.push(box);
  };
  if(object instanceof THREE.InstancedMesh){for(let n=0;n<object.count;n++){object.getMatrixAt(n,local);world.multiplyMatrices(object.matrixWorld,local);add(world);}}
  else add(object.matrixWorld);
 });
 const position=SPAWN.clone();let yaw=0,pitch=-.06;
 const safe=(point:THREE.Vector3)=>point.x*point.x+point.z*point.z<=ISLAND_EXPLORER_RADIUS**2&&!solids.some(box=>box.clone().expandByScalar(BODY_RADIUS+.025).containsPoint(point));
 function spawn(){
  if(safe(SPAWN))return SPAWN.clone();
  // Resolve an unexpected future obstacle at the requested spawn without starting inside it.
  const candidates:THREE.Vector3[]=[];
  for(let x=-6.25;x<=6.25;x+=.25)for(let z=-6.25;z<=6.25;z+=.25){const point=new THREE.Vector3(x,ISLAND_EXPLORER_EYE_HEIGHT,z);if(safe(point))candidates.push(point);}
  candidates.sort((a,b)=>a.distanceToSquared(SPAWN)-b.distanceToSquared(SPAWN));
  if(!candidates.length)throw new Error('This island has no safe exploration starting point. Use the orbit view.');
  return candidates[0];
 }
 function reset(){position.copy(spawn());yaw=Math.atan2(-position.x,position.z+1.5);pitch=-.06;}
 function direction(){return new THREE.Vector3(Math.sin(yaw)*Math.cos(pitch),Math.sin(pitch),-Math.cos(yaw)*Math.cos(pitch));}
 function target(){return position.clone().add(direction());}
 function turn(dx:number,dy:number){
  if(!Number.isFinite(dx)||!Number.isFinite(dy)||(dx===0&&dy===0))return;
  // Keep long sessions numerically stable; look-up/down can never invert the camera.
  yaw=THREE.MathUtils.euclideanModulo(yaw+THREE.MathUtils.clamp(dx,-300,300)*LOOK_SENSITIVITY+Math.PI,Math.PI*2)-Math.PI;
  pitch=THREE.MathUtils.clamp(pitch-THREE.MathUtils.clamp(dy,-300,300)*LOOK_SENSITIVITY,-MAX_PITCH,MAX_PITCH);
 }
 function translate(forward:number,right:number){
  const dx=Math.sin(yaw)*forward+Math.cos(yaw)*right,dz=-Math.cos(yaw)*forward+Math.sin(yaw)*right;
  function bounded(point:THREE.Vector3){const r=Math.hypot(point.x,point.z);if(r>ISLAND_EXPLORER_RADIUS){point.x*=ISLAND_EXPLORER_RADIUS/r;point.z*=ISLAND_EXPLORER_RADIUS/r;}point.y=ISLAND_EXPLORER_EYE_HEIGHT;return point;}
  function sweep(from:THREE.Vector3,to:THREE.Vector3){const result=constrainProjectCamera(from,bounded(to),solids,BODY_RADIUS);result.y=ISLAND_EXPLORER_EYE_HEIGHT;return result;}
  const requested=bounded(position.clone().add(new THREE.Vector3(dx,0,dz)));
  let next=sweep(position,requested);
  if(next.distanceToSquared(requested)>1e-10){
   // Try legal tangential motion when the diagonal gesture hits a wall instead of
   // making the entire touchpad gesture feel stuck. Every leg is swept separately.
   const x=sweep(next,new THREE.Vector3(requested.x,next.y,next.z)),z=sweep(next,new THREE.Vector3(next.x,next.y,requested.z));
   next=x.distanceToSquared(requested)<z.distanceToSquared(requested)?x:z;
  }
  const changed=position.distanceToSquared(next)>0;position.copy(next);return changed;
 }
 function travel(forward:number,right:number){
  if(!Number.isFinite(forward)||!Number.isFinite(right)||(forward===0&&right===0))return false;
  const input=new THREE.Vector2(right,forward);if(input.length()>.28)input.setLength(.28);
  return translate(input.y,input.x);
 }
 function move(forward:number,right:number,delta:number){
  if(!Number.isFinite(forward)||!Number.isFinite(right)||!Number.isFinite(delta)||delta<=0)return false;
  const input=new THREE.Vector2(right,forward);if(input.lengthSq()===0)return false;if(input.lengthSq()>1)input.normalize();
  const step=ISLAND_EXPLORER_SPEED*Math.min(.05,delta);return translate(input.y*step,input.x*step);
 }
 function apply(camera:THREE.PerspectiveCamera){camera.position.copy(position);camera.lookAt(target());camera.updateMatrixWorld();}
 reset();
 return {position,solids,get yaw(){return yaw;},get pitch(){return pitch;},turn,move,travel,direction,target,reset,apply};
}

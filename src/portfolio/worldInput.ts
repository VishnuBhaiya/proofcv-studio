export type WheelInput={deltaX:number;deltaY:number;deltaMode:number;ctrlKey:boolean;shiftKey:boolean};
const clamp=(value:number,min:number,max:number)=>Math.min(max,Math.max(min,value));
function wheelPixels(input:WheelInput,pageHeight:number){
 const height=Number.isFinite(pageHeight)&&pageHeight>0?pageHeight:600;
 const unit=input.deltaMode===1?16:input.deltaMode===2?height:1;
 return {x:clamp(Number.isFinite(input.deltaX)?input.deltaX*unit:0,-90,90),y:clamp(Number.isFinite(input.deltaY)?input.deltaY*unit:0,-90,90)};
}
export function cameraGesture(input:WheelInput,pageHeight=600){
 const {x,y}=wheelPixels(input,pageHeight);
 if(input.ctrlKey)return {azimuth:0,elevation:0,zoom:Math.exp(clamp(y*.008,-.28,.28))};
 return {azimuth:-(input.shiftKey&&x===0?y:x)*.004||0,elevation:input.shiftKey?0:-y*.003||0,zoom:1};
}

/** Explore gestures are direct distances, never an inertial walking velocity. */
export function explorerGesture(input:WheelInput,pageHeight=600){
 const {x,y}=wheelPixels(input,pageHeight);
 if(input.ctrlKey)return {forward:clamp(-y*.012,-.28,.28)||0,right:0,yaw:0};
 // Browsers may remap Shift+vertical wheel into the horizontal delta before delivery.
 if(input.shiftKey)return {forward:0,right:clamp((Math.abs(x)>Math.abs(y)?x:y)*.006,-.28,.28)||0,yaw:0};
 return {forward:clamp(-y*.006,-.28,.28)||0,right:0,yaw:clamp(x*.004,-.32,.32)||0};
}

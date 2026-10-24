import type { Project } from './types';
import type { TourChapter } from './projectTour';

export function sceneRecordingSupported(){return typeof MediaRecorder!=='undefined'&&typeof HTMLCanvasElement!=='undefined'&&'captureStream' in HTMLCanvasElement.prototype;}
export function recordSceneTour(project:Project,name:string,revision:number,chapters:TourChapter[]){
 if(!sceneRecordingSupported())throw Error('This browser cannot record canvas video. You can still watch the guided tour.');
 const output=document.createElement('canvas');output.width=1600;output.height=900;const ctx=output.getContext('2d');if(!ctx)throw Error('Canvas recording is unavailable.');
 const stream=output.captureStream(30),mime=['video/webm;codecs=vp9','video/webm;codecs=vp8','video/webm'].find(s=>MediaRecorder.isTypeSupported(s));
 if(!mime){stream.getTracks().forEach(t=>t.stop());throw Error('WebM recording is not supported by this browser.');}
 const recorder=new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:4500000}),chunks:BlobPart[]=[];
 let discarded=false,finished=false,last=-1000;
 let resolve!:(value:{url:string;bytes:number})=>void,reject!:(error:Error)=>void;
 const result=new Promise<{url:string;bytes:number}>((yes,no)=>{resolve=yes;reject=no;});
 recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
 recorder.onerror=()=>{stream.getTracks().forEach(t=>t.stop());reject(Error('The browser could not finish recording. Please try the live tour instead.'));};
 recorder.onstop=()=>{stream.getTracks().forEach(t=>t.stop());if(discarded){resolve({url:'',bytes:0});return;}const blob=new Blob(chunks,{type:mime});if(!blob.size){reject(Error('No video frames were recorded.'));return;}resolve({url:URL.createObjectURL(blob),bytes:blob.size});};
 function wrapped(text:string,x:number,y:number,width:number,lineHeight:number,maxLines:number){const words=text.replace(/\s+/g,' ').split(' ');let line='',row=0;for(let i=0;i<words.length;i++){const next=(line?line+' ':'')+words[i];if(ctx!.measureText(next).width>width&&line){ctx!.fillText(line,x,y+row*lineHeight);row++;if(row>=maxLines-1){const remainder=words.slice(i).join(' ');let final=remainder;while(ctx!.measureText(final+'…').width>width&&final.length)final=final.slice(0,-1);ctx!.fillText(final+(final!==remainder?'…':''),x,y+row*lineHeight);return;}line=words[i];}else line=next;}if(line)ctx!.fillText(line,x,y+row*lineHeight);}
 return {
  result,
  start(){recorder.start(1000);},
  capture(canvas:HTMLCanvasElement,time:number){
   if(finished||time-last<1/30)return;last=time;
   ctx.fillStyle='#091724';ctx.fillRect(0,0,1600,900);
   const area={x:0,y:110,w:1600,h:520},scale=Math.max(area.w/canvas.width,area.h/canvas.height);
   ctx.save();ctx.beginPath();ctx.rect(area.x,area.y,area.w,area.h);ctx.clip();ctx.drawImage(canvas,(1600-canvas.width*scale)/2,area.y+(area.h-canvas.height*scale)/2,canvas.width*scale,canvas.height*scale);ctx.restore();
   ctx.fillStyle='#a9c9ed';ctx.font='18px Segoe UI, sans-serif';ctx.fillText('DEMO CV  /  ILLUSTRATIVE 3D WALKTHROUGH',40,34);
   ctx.fillStyle='#edf5ff';ctx.font='bold 30px Segoe UI, sans-serif';wrapped(project.title,40,78,1520,32,1);
   const index=Math.min(2,Math.floor(time/12)),chapter=chapters[index];ctx.fillStyle='#b6d9ff';ctx.font='bold 22px Segoe UI, sans-serif';ctx.fillText(String(index+1).padStart(2,'0')+'  '+chapter.title.toUpperCase(),40,677);
   ctx.fillStyle='#e0ebf4';ctx.font='22px Segoe UI, sans-serif';wrapped(chapter.text,40,717,1510,30,4);
   ctx.fillStyle='#88a4ba';ctx.font='16px Segoe UI, sans-serif';ctx.fillText(name+' · confirmed source revision '+revision+' · silent scene walkthrough, not footage of the working project',40,866);
   ctx.fillStyle='#223c51';ctx.fillRect(0,890,1600,10);ctx.fillStyle='#a7b8ff';ctx.fillRect(0,890,1600*Math.min(1,time/36),10);
  },
  stop(){if(finished)return;finished=true;if(recorder.state!=='inactive')recorder.stop();},
  discard(){discarded=true;this.stop();}
 };
}

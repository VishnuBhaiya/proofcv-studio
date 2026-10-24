/** User-initiated browser narration; no model request or voice cloning. */
export function spokenExcerpt(text:string,words=24){
 const parts=text.trim().split(/\s+/).filter(Boolean);
 return parts.length>words?parts.slice(0,words).join(' ').replace(/[,:;–—-]+$/,'')+'…':text.trim();
}

export function createTourVoice(synth:SpeechSynthesis|undefined,Utterance:typeof SpeechSynthesisUtterance|undefined,onError:()=>void){
 let active:SpeechSynthesisUtterance|null=null;
 const supported=!!synth&&!!Utterance;
 function stop(){if(active&&synth){active.onend=null;active.onerror=null;active=null;synth.cancel();}}
 return {
  supported,stop,
  speak(title:string,text:string){
   stop();if(!synth||!Utterance)return;
   try{
    const next=new Utterance(title+'. '+spokenExcerpt(text));
    next.lang='en-AU';next.rate=1.04;next.pitch=1;next.volume=1;
    const voices=synth.getVoices();
    next.voice=voices.find(v=>v.localService&&/^en[-_]AU/i.test(v.lang))||voices.find(v=>v.localService&&/^en/i.test(v.lang))||null;
    next.onend=()=>{if(active===next)active=null;};
    next.onerror=event=>{if(active===next){active=null;if(!['canceled','interrupted'].includes(event.error))onError();}};
    active=next;synth.speak(next);
   }catch{active=null;onError();}
  }
 };
}

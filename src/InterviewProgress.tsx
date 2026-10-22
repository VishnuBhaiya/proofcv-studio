import {useEffect, useRef, useState} from 'react';
export default function InterviewProgress({message}:{message:string}) {
 const [seconds,setSeconds]=useState(0);
 const node=useRef<HTMLDivElement>(null);
 useEffect(()=>{node.current?.scrollIntoView({behavior:'smooth',block:'nearest'});const timer=setInterval(()=>setSeconds(s=>s+1),1000);return ()=>clearInterval(timer);},[]);
 return <div ref={node} aria-live="polite" aria-busy="true">{message && <div className="chat-message user"><strong>You</strong><p>{message}</p></div>}<div className="chat-message assistant"><strong>ProofCV</strong><p>{seconds<15?'Preparing your response…':'Still waiting for Gemini. You do not need to send your message again.'}</p><small>{seconds}s elapsed</small></div></div>;
}

import {useState} from 'react';
export default function DocumentUpload({busy,blocked,upload}:{busy:boolean;blocked:boolean;upload:(data:Record<string,unknown>)=>Promise<void>}) {
 const [file,setFile]=useState<File|null>(null),[error,setError]=useState(''),[reading,setReading]=useState(false);
 async function submit() {
  if(!file || busy || blocked || reading) return;
  setError(''); setReading(true);
  try {
   if(file.size>5*1024*1024 || !file.size) throw new Error('Choose a nonempty file up to 5 MB.');
   const content=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(new Error('Could not read this file.'));reader.readAsDataURL(file);});
   await upload({filename:file.name,content});
  } catch(e) {setError(e instanceof Error?e.message:String(e));}
  finally {setReading(false);}
 }
 return <section className="pe-progress" style={{marginBottom:18}} aria-label="Upload a profile document"><h3>Start with a document</h3><p>Import a marksheet, transcript, CV or certificate. Review the extracted details before adding them.</p><label>Choose a document<input type="file" accept=".pdf,.png,.jpg,.jpeg,.txt" disabled={busy || reading} onChange={e=>{setFile(e.target.files?.[0] || null);setError('');}}/></label><p><small>PDF (up to 20 pages), PNG, JPEG or text · maximum 5 MB. Scans are read by Gemini. WAM/GPA are copied only when stated; subjects suggest skills for you to confirm.</small></p><p><small>Clicking Extract sends this document to your configured Gemini provider. The original file is not saved by ProofCV.</small></p><button type="button" className="button dark" disabled={!file || busy || reading || blocked} onClick={()=>void submit()}>{busy || reading?'Reading document…':'Extract & review details'}</button>{blocked && <p>Save your form edits and finish the current review before uploading.</p>}{error && <p role="alert">{error}</p>}</section>;
}

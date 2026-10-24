// Pure policy/SSR checks. These do not claim browser video decoding or live AI.
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const cache=new Map();
async function moduleURL(name){
 if(cache.has(name))return cache.get(name);
 const input=await readFile(new URL('../src/portfolio/'+name+(name==='MediaEvidence'?'.tsx':'.ts'),import.meta.url),'utf8');
 let output=ts.transpileModule(input,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText.replace(/import ['"][^'"]+\.css['"];?/g,'');
 for(const match of [...output.matchAll(/from ['"]([^'"]+)['"]/g)]){const spec=match[1],url=spec.startsWith('./')?await moduleURL(spec.slice(2)):import.meta.resolve(spec);output=output.replaceAll(match[0],'from '+JSON.stringify(url));}
 const url='data:text/javascript;base64,'+Buffer.from(output).toString('base64');cache.set(name,url);return url;
}
const {mediaPolicy,mediaBadge,formatMediaTime,normaliseChapters,activeChapterIndex}=await import(await moduleURL('mediaPolicy'));
const {default:MediaEvidence}=await import(await moduleURL('MediaEvidence'));
const analysis={caption:'Owner-recorded application walkthrough',alt:'The interface',description:'A walkthrough of the project interface.',hotspots:[],chapters:[{time:0,title:'Introduction',description:'The interface.'},{time:8,title:'Review',description:'The review view.'}],transcript:'Supplied transcript text.',questions:[],warnings:[]};
const asset={id:'media-1',project_id:'solar',name:'recording.mp4',key:'a.mp4',sha256:'a',mime:'video/mp4',width:1920,height:1080,duration:15,url:'media/video.mp4',analysis};
const render=value=>renderToStaticMarkup(React.createElement(MediaEvidence,{asset:value,sources:{}}));
let count=0;function test(label,run){run();count++;console.log('PASS '+label);}
test('A reviewed upload is not labelled independently verified',()=>{assert.equal(mediaPolicy(asset).kind,'reviewed');assert.doesNotMatch(mediaPolicy(asset).explanation,/independently verified/);assert.match(mediaPolicy(asset).explanation,/not independent verification/);});
test('Explicit synthetic filename is classified as illustrative',()=>assert.equal(mediaPolicy({...asset,name:'synthetic-silent-tour.mp4'}).kind,'illustrative'));
test('Explicit synthetic caption survives filenames stripped from exports',()=>assert.equal(mediaPolicy({...asset,name:undefined,analysis:{...analysis,caption:'A synthetic evaluation diagram'}}).kind,'illustrative'));
test('Illustrative warning is retained in classification',()=>assert.equal(mediaPolicy({...asset,analysis:{...analysis,warnings:['Illustrative reference, not project evidence']}}).kind,'illustrative'));
test('Unreviewed media cannot be promoted by an impressive filename',()=>assert.equal(mediaPolicy({...asset,name:'real-working-project.mp4',analysis:undefined}).kind,'unreviewed'));
test('A short real recording is not automatically declared synthetic',()=>assert.equal(mediaPolicy({...asset,duration:6}).kind,'reviewed'));
test('Synthetic clips get a reference badge rather than a video-tour claim',()=>assert.equal(mediaBadge({...asset,name:'synthetic.mp4'}),'Reference clip'));
test('Unreviewed media keeps an unreviewed badge',()=>assert.equal(mediaBadge({...asset,analysis:undefined}),'Unreviewed upload'));
test('Media time is stable for common durations',()=>{assert.equal(formatMediaTime(207.83),'3:27');assert.equal(formatMediaTime(5),'0:05');assert.equal(formatMediaTime(3661),'1:01:01');});
test('Invalid negative or infinite durations cannot leak into labels',()=>[NaN,Infinity,-4].forEach(v=>assert.equal(formatMediaTime(v),'0:00')));
test('Chapters are sorted and duplicate times removed',()=>assert.deepEqual(normaliseChapters([analysis.chapters[1],analysis.chapters[0],{time:8,title:'Duplicate',description:''}],15).map(c=>c.time),[0,8]));
test('Out-of-bounds chapters are excluded without inventing replacements',()=>assert.deepEqual(normaliseChapters([{time:-1,title:'Bad'},{time:15,title:'Past end'},{time:Infinity,title:'Bad'}],15),[]));
test('Empty chapter lists stay empty',()=>assert.deepEqual(normaliseChapters(undefined,15),[]));
test('Only six bounded chapters may be rendered',()=>assert.equal(normaliseChapters(Array.from({length:10},(_,i)=>({time:i,title:'Chapter '+i,description:''})),15).length,6));
test('Active chapter follows playback time',()=>{assert.equal(activeChapterIndex(analysis.chapters,0),0);assert.equal(activeChapterIndex(analysis.chapters,7.99),0);assert.equal(activeChapterIndex(analysis.chapters,8),1);assert.equal(activeChapterIndex(analysis.chapters,NaN),-1);});
test('A genuine reviewed video is a native non-autoplay player',()=>{const html=render(asset);assert.match(html,/<video/);assert.match(html,/controls=""/);assert.match(html,/preload="metadata"/);assert.doesNotMatch(html,/autoplay/);});
test('Chapters are native keyboard-operable buttons with an active state',()=>{const html=render(asset);assert.match(html,/aria-label="Video chapters"/);assert.match(html,/aria-current="step"/);assert.match(html,/type="button"/);assert.match(html,/0:08/);});
test('Media explanation has accessible observation/contribution/limits tabs',()=>{const html=render(asset);assert.match(html,/role="tablist"/);assert.equal((html.match(/role="tab"/g)||[]).length,3);assert.match(html,/role="tabpanel"/);assert.match(html,/aria-selected="true"/);});
test('Explicitly illustrative video starts collapsed without creating a player',()=>{const html=render({...asset,name:'synthetic.mp4'});assert.match(html,/<details/);assert.doesNotMatch(html,/<details[^>]*open/);assert.doesNotMatch(html,/<video/);assert.match(html,/ILLUSTRATIVE REFERENCE/);assert.doesNotMatch(html,/PROJECT VIDEO TOUR/);});
test('Synthetic image also remains an optional collapsed reference',()=>{const html=render({...asset,name:'synthetic-diagram.png',mime:'image/png'});assert.doesNotMatch(html,/<img/);assert.match(html,/not a recording/i);});
test('Unreviewed media does not expose or load its raw media URL',()=>{const html=render({...asset,analysis:undefined});assert.doesNotMatch(html,/media\/video.mp4|<video|<img/);});
test('A supplied transcript is preserved exactly as text, not fabricated captions',()=>{const html=render(asset);assert.match(html,/Supplied transcript text\./);assert.match(html,/Read the reviewed transcript/);assert.doesNotMatch(html,/<track/);});
test('Missing transcript does not invent audible speech or timed captions',()=>{const html=render({...asset,analysis:{...analysis,transcript:''}});assert.match(html,/No speech transcript supplied/);assert.match(html,/not invented speech or timed captions/);});
test('Rendering cannot mutate approved project or media analysis data',()=>{const before=JSON.stringify(asset);render(asset);assert.equal(JSON.stringify(asset),before);});
test('Untrusted caption text is escaped',()=>{const html=render({...asset,analysis:{...analysis,caption:'<script>alert(1)</script>'}});assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>/);});
console.log(`${count} media policy and evidence rendering checks passed.`);

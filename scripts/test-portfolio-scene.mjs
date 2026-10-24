// Initial-render boundary checks, not a substitute for browser interaction tests.
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const source=await readFile(new URL('../src/portfolio/PortfolioScene.tsx',import.meta.url),'utf8');
let output=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
for(const name of ['react/jsx-runtime','react'])output=output.replaceAll(`from "${name}"`,`from ${JSON.stringify(import.meta.resolve(name))}`).replaceAll(`from '${name}'`,`from ${JSON.stringify(import.meta.resolve(name))}`);
const {default:Scene}=await import('data:text/javascript;base64,'+Buffer.from(output).toString('base64'));
let reduced=false,count=0;
globalThis.window={matchMedia:()=>({matches:reduced})};
const projects=[{id:'p0',title:'Confirmed <project>',technologies:'Python, SQL',description:'Confirmed description.'},{id:'p1',title:'Another confirmed project',technologies:'',description:'Text only.'}];
const site={projects,assets:[],person:{name:'Synthetic Test'}};
const render=(p=projects,s=site)=>renderToStaticMarkup(React.createElement(Scene,{site:s,projects:p,onProject:()=>{}}));
function test(name,fn){fn();count++;console.log('PASS '+name);}
test('Uses an accessible project-orbit landmark',()=>assert.match(render(),/aria-label="Interactive project orbit"/));
test('Default animation has a clearly labelled pause control',()=>assert.match(render(),/aria-label="Pause 3D motion" aria-pressed="true"|aria-pressed="true" aria-label="Pause 3D motion"/));
test('Reduced-motion preference starts without animation',()=>{reduced=true;const html=render();assert.match(html,/is-still/);assert.match(html,/aria-label="Enable 3D motion"/);assert.doesNotMatch(html,/is-moving/);reduced=false;});
test('Project titles are escaped, not executed',()=>assert.match(render(),/Confirmed &lt;project&gt;/));
test('Only reviewed public media passed into the projection is displayed',()=>{const html=render();assert.doesNotMatch(html,/<img/);assert.doesNotMatch(html,/https?:/);});
test('Approved project image is used without inventing a portrait',()=>{const html=render(projects,{...site,assets:[{project_id:'p0',mime:'image/png',url:'media/approved.png'}]});assert.match(html,/src="media\/approved.png"/);assert.doesNotMatch(html,/portrait/);});
test('No projects is a safe empty scene with disabled navigation',()=>{const html=render([],{...site,projects:[]});assert.match(html,/00 \/ 00/);assert.doesNotMatch(html,/Open case study/);assert.equal((html.match(/disabled=""/g)||[]).length,2);});
test('A single project disables meaningless next/previous controls',()=>assert.equal((render(projects.slice(0,1)).match(/disabled=""/g)||[]).length,2));
console.log(`${count} portfolio-scene rendering tests passed.`);

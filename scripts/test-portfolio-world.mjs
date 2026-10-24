// Deterministic layout/source-boundary checks. No provider calls or GPU claims.
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import ts from 'typescript';
const input=await readFile(new URL('../src/portfolio/worldLayout.ts',import.meta.url),'utf8');
const compiled=ts.transpileModule(input,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;
const {worldStations,stationIndex,stationLabel,WORLD_LIMIT}=await import('data:text/javascript;base64,'+Buffer.from(compiled).toString('base64'));
const projects=Array.from({length:10},(_,i)=>({id:'confirmed-'+i,title:'Confirmed project '+i,description:'Exact confirmed text.',technologies:'Python'}));
let count=0;
function test(label,run){run();console.log('PASS '+label);count++;}
test('Exhibits use actual project objects, not invented substitutes',()=>assert.equal(worldStations(projects)[0].project,projects[0]));
test('World respects the six-station performance boundary',()=>assert.equal(worldStations(projects).length,WORLD_LIMIT));
test('All project data remains unchanged outside the capped exhibit',()=>{worldStations(projects);assert.equal(projects.length,10);assert.equal(projects[9].id,'confirmed-9');});
test('All station positions are unique',()=>assert.equal(new Set(worldStations(projects).map(s=>s.position.join(','))).size,6));
test('No project safely produces no station',()=>assert.deepEqual(worldStations([]),[]));
test('A one-project profile receives exactly one real exhibit',()=>assert.equal(worldStations(projects.slice(0,1)).length,1));
test('Role ordering changes exhibit ordering without editing the projects',()=>assert.equal(worldStations([projects[2],projects[0]])[0].project.id,projects[2].id));
test('Scene labels are bounded without changing original title',()=>{assert.ok(stationLabel(projects[0].title,12).length<=12);assert.equal(projects[0].title,'Confirmed project 0');});
test('Short labels are not modified',()=>assert.equal(stationLabel('API'),'API'));
test('Cycling selection supports both directions safely',()=>{assert.equal(stationIndex(-1,3),2);assert.equal(stationIndex(3,3),0);assert.equal(stationIndex(0,0),-1);});
const world=await readFile(new URL('../src/portfolio/PortfolioWorld.tsx',import.meta.url),'utf8');
const engine=await readFile(new URL('../src/portfolio/worldEngine.ts',import.meta.url),'utf8');
test('No touchpad enable panel or activation state remains',()=>{assert.doesNotMatch(world,/Enable touchpad controls|pf-world-interaction|setInteractive/);});
test('Canvas wheel input is direct, not gated behind activation',()=>{assert.doesNotMatch(engine,/wheelActive|onInteraction|interact:/);assert.match(engine,/canvas.addEventListener\('wheel',wheel,\{passive:false,capture:true\}\)/);});
test('Wheel capture is not registered on the page or document',()=>{assert.doesNotMatch(engine,/(?:window|document).addEventListener\('wheel'/);});
console.log(`${count} portfolio-world layout tests passed.`);

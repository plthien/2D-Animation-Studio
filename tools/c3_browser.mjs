/**
 * Windows C2 real Chromium journey + G0-comparable viewport screenshots.
 * Exercises real frontend → API → SQLite, then restarts the API against the
 * same disposable database. No local-only mocks or paid calls.
 */
import {chromium} from 'playwright';
import {spawn,spawnSync} from 'node:child_process';
import {mkdirSync,mkdtempSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';

const root=resolve('.');
const disposable=mkdtempSync(join(tmpdir(),'c3-browser-'));
const evidence=join(root,'artifacts','c3');
mkdirSync(evidence,{recursive:true});
const db=join(disposable,'studio.sqlite').replaceAll('\\','/');
const env={...process.env,DATABASE_URL:'sqlite:///'+db,ARTIFACT_ROOT:join(disposable,'artifacts'),
 AUTO_APPLY_MIGRATIONS:'true'};
let api,ui,browser;
const children=[];
function started(file,args){
 const p=spawn(file,args,{cwd:root,env,stdio:'inherit',windowsHide:true});
 children.push(p);
 return p;
}
function kill(p){
 if(!p||!p.pid)return;
 if(process.platform==='win32')spawnSync('taskkill.exe',['/PID',String(p.pid),'/T','/F'],{stdio:'ignore'});
 else p.kill('SIGTERM');
}
async function ready(url,timeoutMs=60000){
 const start=Date.now();
 while(Date.now()-start<timeoutMs){
  try {const res=await fetch(url);if(res.ok)return;}
  catch{}
  await new Promise(r=>setTimeout(r,600));
 }
 throw new Error('Real service not ready: '+url);
}
async function capture(page,label){
 for(const [w,h] of [[1440,900],[1920,1080],[768,900]]){
  await page.setViewportSize({width:w,height:h});
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({path:join(evidence,label+'-'+w+'x'+h+'.png'),fullPage:false,animations:'disabled'});
 }
}
function assert(value,message){if(!value)throw new Error(message);}
async function startApi(){
 api=started('python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000']);
 await ready('http://127.0.0.1:8000/health');
}
try {
 await startApi();
 ui=started('cmd.exe',['/d','/c','npm.cmd run dev -- --host 127.0.0.1'],);
 await ready('http://127.0.0.1:5173');
 browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:900}});
 const errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 await page.goto('http://127.0.0.1:5173',{waitUntil:'networkidle'});
 await page.getByTestId('new-channel-button').click();
 await capture(page,'channel-create-modal');
 const createChannel=page.getByTestId('create-channel-modal');
 await createChannel.locator('input').nth(0).fill('C2 Browser Channel');
 await createChannel.locator('input').nth(1).fill('c3-browser-channel');
 await createChannel.getByRole('button',{name:'Create channel'}).click();
 await page.getByTestId('channel-card-grid').getByText('C2 Browser Channel').waitFor();
 await page.waitForLoadState('networkidle'); // finish DNA query before editing, avoid draft hydration race
 const editor=page.getByTestId('channel-dna-editor');
 await editor.locator('textarea').nth(0).fill('Animation fans');
 await editor.locator('textarea').nth(1).fill('Sketchy flat color 2D figures, intentionally rough');
 await editor.locator('textarea').nth(2).fill('Funny, expressive physical comedy');
 await editor.locator('textarea').nth(3).fill('Friendly casual narrator');
 const saveDNAResponse=page.waitForResponse(r=>r.url().endsWith('/dna')&&r.request().method()==='PUT');
 await page.getByTestId('save-dna').click();
 const dnaResult=await saveDNAResponse;
 assert(dnaResult.status()===201,'DNA draft save failed: '+dnaResult.status()+' '+await dnaResult.text());
 await page.getByTestId('approve-dna').waitFor({state:'visible'});
 await page.waitForFunction(()=>!document.querySelector('[data-testid="approve-dna"]')?.hasAttribute('disabled'));
 await page.getByTestId('approve-dna').click();
 await page.getByText('Approved head').waitFor();
 await capture(page,'channels');
 await page.locator('nav button').filter({hasText:'Projects'}).first().click();
 await page.getByTestId('new-project-button').click();
 await capture(page,'project-create-modal');
 const createProject=page.getByTestId('create-project-modal');
 await createProject.locator('input').nth(0).fill('C2 Browser Pilot');
 await createProject.locator('input').nth(1).fill('c3-browser-pilot');
 await createProject.getByRole('button',{name:'Create project'}).click();
 await page.getByTestId('animation-studio').waitFor();
 for(const label of ['Authoring','Resolver','Generation','Rigging','Director','Motion','Delivery']){
  assert((await page.getByTestId('animation-studio').getByText(label,{exact:true}).count())>=1,
   'Missing animation stage: '+label);
 }

 // C3 genuine UI: external JSON fixture documents are built from live reservations.
 async function author(kind,build){
  await page.locator('[data-testid="c3-authoring"] select').selectOption(kind);
  const promptResponse=page.waitForResponse(r=>r.url().endsWith('/authoring/'+kind+'/prompt')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Create prompt reservation'}).click();
  const pkg=(await (await promptResponse).json()).data;
  const doc={...pkg.reserved_fields,...build(pkg)};
  await page.locator('[data-testid="c3-authoring"] textarea').fill(JSON.stringify(doc));
  const imported=page.waitForResponse(r=>r.url().endsWith('/authoring/'+kind+'/import')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Import immutable draft'}).click();
  const draft=(await (await imported).json()).data;
  assert(draft?.artifact_id,'UI did not import '+kind);
  const approved=page.waitForResponse(r=>r.url().endsWith('/authoring/'+kind+'/'+draft.artifact_id+'/approve'));
  await page.getByRole('button',{name:'Approve selected draft'}).click();
  assert((await (await approved).json()).data?.artifact_id===draft.artifact_id,'Failed UI approval '+kind);
  return {draft,doc};
 }
 const ideas=await author('topic-ideas',pkg=>({
  channel_dna_artifact_id:pkg.dna_metadata.artifact_id,
  channel_dna_hash:pkg.dna_metadata.sha256,
  ideas:[{idea_id:'idea_one',title:'The first animated story',premise:'An actor waves in an imaginary location'}]
 }));
 const script=await author('script',()=>({
  topic_ideas_artifact_id:ideas.draft.artifact_id,selected_idea_id:'idea_one',
  full_text:'Hello!',sections:[{section_id:'section_one',start_char:0,end_char:6,text:'Hello!'}]
 }));
 const world={actors:[{actor_id:'actor_one',x:0,y:0,facing:'right'}],props:[]};
 const shots=await author('shot-plan',()=>({
  script_artifact_id:script.draft.artifact_id,script_sha256:script.draft.sha256,
  actor_ids:['actor_one'],prop_ids:[],location_ids:['location_one'],
  shots:[{shot_id:'shot_one',duration_frames:48,actor_ids:['actor_one'],prop_ids:[],
   location_id:'location_one',utterance:{text:'Hello!',script_start:0,script_end:6},
   initial_world_state:world,final_world_state:world,spatial_anchors:[]}]
 }));
 await page.reload({waitUntil:'networkidle'});
 await page.getByTestId('c3-authoring').waitFor();
 await page.getByText('Readiness: approved').first().waitFor();
 await page.locator('.pipeline-step').nth(1).click();
 console.log('C3 resolver selection DOM', (await page.getByTestId('animation-studio').innerText()).slice(0,1700), 'pageErrors=',errors);
 await page.screenshot({path:join(evidence,'resolver-debug.png'),fullPage:true});
 await page.getByTestId('c3-resolver').waitFor({timeout:15000});
 await page.getByText('actor: actor_one (front)').waitFor();
 await capture(page,'resolver-requirements');
 await page.locator('.pipeline-step').nth(2).click();
 await page.getByTestId('c3-generation').waitFor();
 await page.getByLabel('Asset requirement').selectOption({index:1});
 const imagePath=join(root,'docs','qa','evidence','g0','05-studio-pipeline-1440x900.png');
 await page.getByLabel('Import local image').setInputFiles(imagePath);
 await page.getByText(/Candidate av_/).first().waitFor();
 await page.getByRole('button',{name:'Approve version'}).click();
 await capture(page,'generation-approved-local-image');
 await page.locator('.pipeline-step').nth(1).click();
 const opts=page.getByTestId('c3-resolver').locator('select').first();
 await opts.selectOption({index:1});
 await page.getByRole('button',{name:'Pin version'}).first().click();
 await page.getByText(/1 of [0-9]+ exact asset pins resolved/).waitFor();
 await capture(page,'resolver-pinned-asset');

 await capture(page,'studio');
 await page.locator('nav button').filter({hasText:'Projects'}).first().click();
 await page.getByTestId('project-card-grid').getByText('C2 Browser Pilot').waitFor();
 await capture(page,'projects');
 for(const screen of ['Jobs','Artifacts','Settings']){
  await page.locator('nav button').filter({hasText:screen}).first().click();
  await page.getByRole('heading',{level:2,name:screen==='Settings'?'Animation system':screen==='Artifacts'?'Immutable artifact metadata':'Jobs'}).waitFor();
  await capture(page,screen.toLowerCase());
 }
 await page.locator('nav button').filter({hasText:'Studio'}).first().click();
 await page.getByTestId('animation-studio').waitFor();
 await page.reload({waitUntil:'networkidle'});
 await page.getByTestId('animation-studio').waitFor();
 assert((await page.getByText('C2 Browser Pilot').count())>0,'Project did not survive browser refresh');
 kill(api);
 await new Promise(r=>setTimeout(r,1500));
 await startApi();
 await page.reload({waitUntil:'networkidle'});
 await page.getByTestId('animation-studio').waitFor();
 assert((await page.getByText('C2 Browser Pilot').count())>0,'Project did not survive API restart');
 await capture(page,'studio-after-restart');
 // Verify the actual immutable asset pin and bytes, not just project selection.
 const channelsAfter=(await (await fetch('http://127.0.0.1:8000/api/v1/channels')).json()).data.items;
 const channelAfter=channelsAfter.find(c=>c.name==='C2 Browser Channel');
 assert(channelAfter,'Channel identity missing after backend restart');
 const projectsAfter=(await (await fetch('http://127.0.0.1:8000/api/v1/projects?channel_id='+channelAfter.channel_id)).json()).data.items;
 const projectAfter=projectsAfter.find(p=>p.name==='C2 Browser Pilot');
 assert(projectAfter,'Project identity missing after backend restart');
 const restored=(await (await fetch('http://127.0.0.1:8000/api/v1/projects/'+projectAfter.project_id+'/resolver/resolution')).json()).data;
 assert(restored.resolved_count>=1,'Approved pinned image was not persisted through restart');
 const storedVersion=restored.requirements.find(item=>item.binding)?.binding?.asset_version_id;
 assert(storedVersion,'No exact approved version pin survived restart');
 const imageAfter=await fetch('http://127.0.0.1:8000/api/v1/projects/'+projectAfter.project_id+'/assets/'+storedVersion+'/image');
 assert(imageAfter.ok&&(await imageAfter.arrayBuffer()).byteLength>100,'Approved image bytes not accessible after restart');
 const readyAfter=(await (await fetch('http://127.0.0.1:8000/api/v1/projects/'+projectAfter.project_id+'/workflow')).json()).data;
 assert(readyAfter.stages[3].readiness==='blocked'&&readyAfter.stages[3].owner_phase==='C4','Rigging should remain C4 blocked');
 assert(errors.length===0,'Browser runtime exceptions: '+errors.join('; '));
 console.log('C3 browser: real Channel → DNA → Project → Topic → Script → ShotPlan → Resolver → Local Image → Pin → refresh → API restart PASS');
 console.log('Evidence:',evidence);
} finally {
 if(browser)await browser.close();
 kill(ui);kill(api);
}

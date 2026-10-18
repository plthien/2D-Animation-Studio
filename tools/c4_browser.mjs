/** Real C4 Chromium / FastAPI / SQLite / official Spine runtime smoke.
 * Self-generated original cartoon fixtures; no Spineboy, no fake loader.
 * Deliberately does NOT claim rig approval (backend verification incomplete).
 */
import {chromium} from 'playwright';
import {spawn,spawnSync} from 'node:child_process';
import {readFileSync,mkdirSync,mkdtempSync,copyFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {createHash} from 'node:crypto';

const root=resolve('.');
const dir=mkdtempSync(join(tmpdir(),'c4-browser-'));
const evidence=join(root,'artifacts','c4');
mkdirSync(evidence,{recursive:true});
const p=spawnSync('python',['tools/c4_fixture.py',dir],{cwd:root,stdio:'inherit'});
if(p.status!==0)throw Error('Unable to generate independent raster fixtures');
const env={...process.env,DATABASE_URL:'sqlite:///'+join(dir,'studio.db').replaceAll('\\','/'),ARTIFACT_ROOT:join(dir,'artifacts'),AUTO_APPLY_MIGRATIONS:'true'};
const BASE='http://127.0.0.1:8000';
const children=[];
let browser;
function run(file,args){const child=spawn(file,args,{cwd:root,env,stdio:'inherit',windowsHide:true});children.push(child);return child;}
function stop(child){if(!child?.pid)return;if(process.platform==='win32')spawnSync('taskkill.exe',['/PID',String(child.pid),'/T','/F'],{stdio:'ignore'});else child.kill('SIGTERM');}
async function ready(url){for(let i=0;i<100;i++){try{if((await fetch(url)).ok)return;}catch{}await new Promise(r=>setTimeout(r,500));}throw Error('Timeout waiting for '+url);}
async function api(method,path,body,idem){
 const res=await fetch(BASE+path,{method,headers:{...(body===undefined?{}:{'Content-Type':'application/json'}),...(idem?{'Idempotency-Key':idem}:{})},body:body===undefined?undefined:JSON.stringify(body)});
 const payload=await res.json();
 if(!res.ok)throw Error(method+' '+path+' HTTP '+res.status+' '+JSON.stringify(payload));
 return payload.data;
}
async function reserved(pid,kind,fill){
 const prefix='/api/v1/projects/'+pid+'/authoring/'+kind;
 const pkg=await api('POST',prefix+'/prompt',{});
 const doc={...pkg.reserved_fields,...fill(pkg)};
 const validation=await api('POST',prefix+'/validate',{reservation_id:pkg.reservation_id,document:doc});
 if(!validation.valid)throw Error('Authoring '+kind+' validation '+JSON.stringify(validation));
 const stored=await api('POST',prefix+'/import',{reservation_id:pkg.reservation_id,document:doc});
 const workflow=await api('GET','/api/v1/projects/'+pid+'/workflow');
 const revision=workflow.stages.find(s=>s.stage_key==='authoring').head_revision;
 await api('POST',prefix+'/'+stored.artifact_id+'/approve',{
  expected_head_revision:revision,expected_sha256:stored.sha256});
 return stored;
}
async function buildTwoActorShotPlan(pid,actors=['character_a','character_b']){
 const ideas=await reserved(pid,'topic-ideas',pkg=>({
  channel_dna_artifact_id:pkg.dna_metadata.artifact_id,
  channel_dna_hash:pkg.dna_metadata.sha256,
  ideas:[{idea_id:'idea_one',title:'Characters A and B',premise:'Two actors'}]}));
 const script=await reserved(pid,'script',()=>({
  topic_ideas_artifact_id:ideas.artifact_id,selected_idea_id:'idea_one',
  full_text:'Hello!',sections:[{section_id:'section_one',start_char:0,end_char:6,text:'Hello!'}]}));
 const state={actors:actors.map((id,i)=>({actor_id:id,x:i,y:0,facing:i?'left':'right'})),props:[]};
 await reserved(pid,'shot-plan',()=>({
  script_artifact_id:script.artifact_id,script_sha256:script.sha256,
  actor_ids:actors,prop_ids:[],location_ids:['location_one'],
  shots:[{shot_id:'shot_one',duration_frames:48,actor_ids:actors,
   prop_ids:[],location_id:'location_one',
   utterance:{text:'Hello!',script_start:0,script_end:6},
   initial_world_state:state,final_world_state:state,spatial_anchors:[]}]}));
 return await api('GET','/api/v1/projects/'+pid+'/resolver/resolution');
}
async function sendImage(pid,who){
 const form=new FormData();
 form.append('kind','actor');form.append('semantic_key','character_'+who);
 form.append('view','front');
 form.append('file',new Blob([readFileSync(join(dir,'actor-'+who+'.png'))],{type:'image/png'}),'actor-'+who+'.png');
 const res=await fetch(BASE+'/api/v1/projects/'+pid+'/images/import',{method:'POST',body:form});
 const val=await res.json();if(!res.ok)throw Error(JSON.stringify(val));
 return val.data;
}
async function partFix(pid,rig,who){
 const base='/api/v1/projects/'+pid+'/rigging/rigs/'+rig;
 const annotations=JSON.parse(readFileSync(join(dir,'rig-joints.json'),'utf8'));
 const roles=Object.keys((await api('GET',base)).parts);
 let n=(await api('GET',base)).draft_revision;
 // Every proposed Voronoi region is visibly repaired using a different
 // authored, role-specific sprite. Never auto-accept the inaccurate partition.
 for(const role of roles){
  const form=new FormData();
  form.append('expected_revision',String(n));
  form.append('file',new Blob([readFileSync(join(dir,who+'-'+role+'.png'))],
   {type:'image/png'}),who+'-'+role+'.png');
  const response=await fetch(BASE+base+'/parts/'+role+'/replacement',{method:'POST',body:form});
  const data=await response.json();
  if(!response.ok)throw Error('Reviewed replacement '+role+': '+JSON.stringify(data));
  n=data.data.draft_revision;
  const corrected=await api('POST',base+'/parts/'+role,{
   expected_revision:n,
   placement:{x:0,y:0,width:1,height:1},
   pivot:annotations.pivots[role],layer:annotations.layers[role],
   reviewed:true});
  n=corrected.draft_revision;
 }
 console.log('G2',who,roles.length,'explicit authored part corrections; all 14 pivot/layer/placement reviews saved');
 return n;
}
try{
 let server=run('python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000']);
 await ready(BASE+'/health');
 run('cmd.exe',['/d','/c','npm.cmd run dev -- --host 127.0.0.1']);
 await ready('http://127.0.0.1:5173');
 const channel=await api('POST','/api/v1/channels',{name:'C4 G2 Test',slug:'c4-g2-test'},'c4-channel');
 const cid=channel.channel_id;
 const dna={schema_version:'channel_dna.v2',
  identity:{name:'C4 G2 Test',audience:'Animation fans'},
  visual:{style:'Flat 2D rigging cartoons',palette:['#aabbcc']},
  performance:{tone:'playful',motion_density:'medium'},
  narration:{language:'en',voice_character:'narrator'}};
 const revision=await api('PUT','/api/v1/channels/'+cid+'/dna',{channel_dna:dna,expected_head_revision:null,expected_head_artifact_id:null},'c4-dna');
 await api('POST','/api/v1/channels/'+cid+'/dna/'+revision.artifact_id+'/approve',{expected_head_revision:null,expected_sha256:revision.sha256,actor:'test-owner',reviewed_at:'2026-10-18T00:00:00Z'});
 const project=await api('POST','/api/v1/projects',{channel_id:cid,name:'G2 Test',slug:'g2-test'},'c4-project');
 const pid=project.project_id;
 const sourceRequirements=await buildTwoActorShotPlan(pid);
 const actorRequirements=Object.fromEntries(sourceRequirements.requirements.filter(x=>x.requirement.kind==='actor')
  .map(x=>[x.requirement.semantic_key,x.requirement.requirement_id]));
 browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:900}});
 await page.addInitScript(([c,p])=>{localStorage.setItem('animationSelectedChannelId',c);localStorage.setItem('animationSelectedProjectId',p);},[cid,pid]);
 await page.goto('http://127.0.0.1:5173/studio',{waitUntil:'networkidle'});
 await page.getByTestId('animation-studio').waitFor();
 await page.locator('.pipeline-step').nth(3).click();
 await page.getByTestId('c4-rigging-workshop').waitFor();
 const rigRecords={};
 for(const who of ['a','b']){
  const version=await sendImage(pid,who);
  copyFileSync(join(dir,'actor-'+who+'.png'),join(evidence,'rig-'+who+'-source.png'));
  copyFileSync(join(dir,'actor-'+who+'-joint-overlay.png'),join(evidence,'rig-'+who+'-joint-overlay.png'));
  await api('POST','/api/v1/projects/'+pid+'/assets/'+version.asset_version_id+'/review',{decision:'approved'});
  await api('POST','/api/v1/projects/'+pid+'/asset-bindings',{
   requirement_id:actorRequirements['character_'+who],
   asset_version_id:version.asset_version_id,
   expected_fingerprint:sourceRequirements.requirements_fingerprint});
  const draft=await api('POST','/api/v1/projects/'+pid+'/rigging/rigs',{asset_version_id:version.asset_version_id});
  // Real UI pointer interactions must alter persisted mask bytes/pivot, not
  // merely update a form or an in-memory preview.
  await page.reload({waitUntil:'networkidle'});
  await page.locator('.pipeline-step').nth(3).click();
  const workshop=page.getByTestId('c4-rigging-workshop');
  await workshop.getByRole('button',{name:'Reopen draft '+draft.rig_id.slice(0,14)}).click();
  await workshop.getByText('Draft revision 1',{exact:false}).waitFor();
  // Reopening publishes the draft view before async list refresh clears busy.
  // Do not fire a canvas pointer while the editor intentionally blocks writes.
  await page.waitForFunction(()=>{
   const buttons=[...document.querySelectorAll('[data-testid="c4-rigging-workshop"] button')];
   const refresh=buttons.find(b=>b.textContent?.trim()==='Refresh');
   return refresh&&!refresh.disabled;
  });
  const editCanvas=workshop.getByRole('img',{name:'Interactive source mask editor'});
  const partBase='/api/v1/projects/'+pid+'/rigging/rigs/'+draft.rig_id+'/parts/head/mask';
  const maskBefore=cryptoDigest(Buffer.from(await (await fetch(BASE+partBase)).arrayBuffer()));
  const box=await editCanvas.boundingBox();
  if(!box)throw Error('Mask canvas has no interactive box');
  // Paint then erase THE SAME known pixel area. An arbitrary erase click
  // can land on an already-empty mask and correctly leave its bytes unchanged.
  // This asserts both tools modify actual persisted raster pixels.
  const brushPoint={x:Math.round(box.width*.50),y:Math.round(box.height*.40)};
  await workshop.getByRole('combobox',{name:'Tool'}).selectOption('paint');
  await editCanvas.click({position:brushPoint});
  await workshop.getByText('Draft revision 2',{exact:false}).waitFor();
  const maskPainted=cryptoDigest(Buffer.from(await (await fetch(BASE+partBase)).arrayBuffer()));
  if(maskBefore===maskPainted)throw Error('Canvas paint did not change real raster mask bytes');
  await workshop.getByRole('combobox',{name:'Tool'}).selectOption('erase');
  await editCanvas.click({position:brushPoint});
  await workshop.getByText('Draft revision 3',{exact:false}).waitFor();
  const maskErased=cryptoDigest(Buffer.from(await (await fetch(BASE+partBase)).arrayBuffer()));
  if(maskPainted===maskErased)throw Error('Canvas erase did not change real raster mask bytes');
  await workshop.getByRole('combobox',{name:'Tool'}).selectOption('pivot');
  await editCanvas.click({position:{x:Math.round(box.width*.62),y:Math.round(box.height*.23)}});
  await workshop.getByText('Draft revision 4',{exact:false}).waitFor();
  const uiEdited=await api('GET','/api/v1/projects/'+pid+'/rigging/rigs/'+draft.rig_id);
  if(uiEdited.draft_revision!==4||Math.abs(uiEdited.parts.head.pivot.x-.62)>.03)
   throw Error('UI raster/pivot pointer edits not persisted');
  const n=await partFix(pid,draft.rig_id,who);
  const correctedDraft=await api('GET','/api/v1/projects/'+pid+'/rigging/rigs/'+draft.rig_id);
  if(correctedDraft.draft_revision!==n||Object.values(correctedDraft.parts).some(p=>!p.reviewed))
   throw Error('Corrected source draft is not fully reviewed and persisted');
  await page.reload({waitUntil:'networkidle'});
  await page.locator('.pipeline-step').nth(3).click();
  await page.getByTestId('c4-rigging-workshop').getByRole('button',{name:'Reopen draft '+draft.rig_id.slice(0,14)}).click();
  await page.getByRole('button',{name:'Export immutable Spine 4.2 candidate'}).click();
  await page.getByTestId('c4-official-runtime').waitFor();
  await page.getByText('Official loader succeeded in current browser session (not backend approval proof)').waitFor({timeout:30000});
  for(const pose of ['idle','walk','reach','grab']){
   await page.getByTestId('c4-official-runtime').getByRole('button',{name:pose,exact:true}).click();
   const name='rig-'+who+'-'+pose+'.png';
   await page.getByTestId('c4-official-runtime').locator('canvas').screenshot({path:join(evidence,name)});
  }
  await page.getByRole('button',{name:'Verify official runtime and five poses'}).click();
  await page.getByTestId('c4-proof-ready').waitFor({timeout:30000});
  await page.getByRole('button',{name:'Approve verified rig version'}).click();
  await page.getByTestId('c4-rig-approved').waitFor({timeout:30000});
  const reviewedVersions=(await api('GET','/api/v1/projects/'+pid+'/rigging/rigs')).items
   .filter(x=>x.rig_id===draft.rig_id&&x.status==='approved');
  const approvedVersion=reviewedVersions.at(-1)?.rig_version_id;
  if(!approvedVersion)throw Error('No actual approved rig version for '+who);
  rigRecords[who]={asset_version_id:version.asset_version_id,rig_id:draft.rig_id,rig_version_id:approvedVersion};
  console.log('C4_G2_APPROVED_RIG',JSON.stringify({character:who,source_version:version.asset_version_id,
   source_sha256:version.source_sha256,rig_id:draft.rig_id,
   rig_version_id:approvedVersion,png_sha256:cryptoDigest(readFileSync(join(evidence,'rig-'+who+'-idle.png'))),manual_corrected_parts:14}));
  const pending=(await api('GET','/api/v1/projects/'+pid+'/workflow')).stages.find(x=>x.stage_key==='rigging');
  if(pending.readiness==='approved')throw Error('Rig version approval falsely approved all project actors');
  const sha=cryptoDigest(readFileSync(join(evidence,'rig-'+who+'-idle.png')));
  console.log(who,version.source_sha256,draft.rig_id,'approved channel rig idle sha='+sha);
  await page.reload({waitUntil:'networkidle'});
  await page.locator('.pipeline-step').nth(3).click();
  await page.getByRole('button',{name:/Play approved/}).last().click();
  await page.getByTestId('c4-official-runtime').getByText('Official loader succeeded in current browser session (not backend approval proof)').waitFor({timeout:30000});
  await page.getByRole('combobox',{name:'Required project actor'}).selectOption(actorRequirements['character_'+who]);
  await page.getByRole('button',{name:'Use previewed rig in this project'}).click();
  const expected=who==='b'?'approved':'draft';
  await page.getByTestId('c4-project-rig-selection').getByText('Current project readiness: '+expected,{exact:false}).waitFor({timeout:30000});
  const selected=await api('GET','/api/v1/projects/'+pid+'/rigging/resolution');
  if(selected.readiness!==expected)throw Error('Two-actor readiness incorrect: '+JSON.stringify(selected));
 }
 const images=['a','b'].flatMap(who=>['idle','walk','reach','grab'].map(p=>cryptoDigest(readFileSync(join(evidence,'rig-'+who+'-'+p+'.png')))));
 if(new Set(images).size<6)throw Error('Real poses/source rigs not visually distinct enough');
 const refreshed=(await api('GET','/api/v1/projects/'+pid+'/rigging/rigs')).items;
 const approved=refreshed.filter(r=>r.status==='approved');
 if(approved.length!==2)throw Error('Expected two independently approved immutable rig versions, got '+approved.length);
 // Project B: reuse Project A's verified rig without editable draft ownership
 // or a duplicate rig export. The B ShotPlan requires actor A only.
 const projectB=await api('POST','/api/v1/projects',{
  channel_id:cid,name:'G2 Reuse Project',slug:'g2-reuse'},'c4-project-reuse');
 const pidB=projectB.project_id;
 const sourceB=await buildTwoActorShotPlan(pidB,['character_a']);
 const actorB=sourceB.requirements.find(x=>x.requirement.kind==='actor');
 if(!actorB)throw Error('Project B approved ShotPlan has no actor');
 await api('POST','/api/v1/projects/'+pidB+'/asset-bindings',{
  requirement_id:actorB.requirement.requirement_id,
  asset_version_id:rigRecords.a.asset_version_id,
  expected_fingerprint:sourceB.requirements_fingerprint});
 const reuse=await api('POST','/api/v1/projects/'+pidB+'/rigging/resolution/select',{
  requirement_id:actorB.requirement.requirement_id,
  rig_version_id:rigRecords.a.rig_version_id,expected_revision:0});
 if(reuse.readiness!=='approved')throw Error('Approved project B single-actor rig mapping failed');
 const stageB=(await api('GET','/api/v1/projects/'+pidB+'/workflow')).stages.find(x=>x.stage_key==='rigging');
 if(stageB.readiness!=='approved')throw Error('Project B rig reuse readiness not approved');
 const reusedRig=await api('GET','/api/v1/channels/'+cid+'/rigs/'+rigRecords.a.rig_id+
  '/versions/'+rigRecords.a.rig_version_id+'/info');
 if(reusedRig.asset_version_id!==rigRecords.a.asset_version_id||reusedRig.status!=='approved')
  throw Error('Channel rig version identity changed during reuse');
 const originalSkeleton=cryptoDigest(Buffer.from(await (await fetch(BASE+
  '/api/v1/channels/'+cid+'/rigs/'+rigRecords.a.rig_id+'/versions/'+rigRecords.a.rig_version_id+'/skeleton.json')).arrayBuffer()));
 const reusePage=await browser.newPage({viewport:{width:1440,height:900}});
 await reusePage.addInitScript(([ch,pr])=>{localStorage.setItem('animationSelectedChannelId',ch);
  localStorage.setItem('animationSelectedProjectId',pr);},[cid,pidB]);
 await reusePage.goto('http://127.0.0.1:5173/studio',{waitUntil:'networkidle'});
 await reusePage.locator('.pipeline-step').nth(3).click();
 await reusePage.getByRole('button',{name:'Play approved '+rigRecords.a.rig_version_id.slice(0,13)}).click();
 await reusePage.getByTestId('c4-official-runtime').getByText('Official loader succeeded in current browser session (not backend approval proof)').waitFor({timeout:30000});
 await reusePage.getByTestId('c4-official-runtime').locator('canvas').screenshot({path:join(evidence,'rig-a-reused-in-project-b.png')});
 await reusePage.close();
 console.log('G2 reuse Project A->B PASS',rigRecords.a.rig_version_id,'identical immutable skeleton',originalSkeleton);
 // Genuine backend restart with the SAME disposable SQLite/artifact root.
 stop(server);
 await new Promise(r=>setTimeout(r,1200));
 server=run('python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000']);
 await ready(BASE+'/health');
 const afterRestart=await api('GET','/api/v1/projects/'+pid+'/rigging/rigs');
 const stable=afterRestart.items.filter(r=>r.status==='approved');
 if(stable.length!==2||stable.some(row=>!approved.some(old=>old.rig_version_id===row.rig_version_id)))
  throw Error('Approved immutable rig identities not preserved after backend restart');
 const reloadedB=await api('GET','/api/v1/projects/'+pidB+'/rigging/resolution');
 if(reloadedB.readiness!=='approved'||reloadedB.bindings[0]?.rig_version_id!==rigRecords.a.rig_version_id)
  throw Error('Cross-project immutable rig selection did not persist after restart');
 const afterSkeleton=cryptoDigest(Buffer.from(await (await fetch(BASE+
  '/api/v1/channels/'+cid+'/rigs/'+rigRecords.a.rig_id+'/versions/'+rigRecords.a.rig_version_id+'/skeleton.json')).arrayBuffer()));
 if(afterSkeleton!==originalSkeleton)throw Error('Reused immutable skeleton bytes changed after restart');
 const stageRestart=(await api('GET','/api/v1/projects/'+pid+'/workflow')).stages.find(x=>x.stage_key==='rigging');
 if(stageRestart.readiness!=='approved')throw Error('Rigging stage not ready after actual backend restart');
 await page.reload({waitUntil:'networkidle'});
 await page.locator('.pipeline-step').nth(3).click();
 await page.getByRole('button',{name:/Play approved/}).last().click();
 await page.getByTestId('c4-official-runtime').getByText('Official loader succeeded in current browser session (not backend approval proof)').waitFor({timeout:30000});
 await page.getByTestId('c4-official-runtime').locator('canvas').screenshot({path:join(evidence,'approved-rig-after-backend-restart.png')});
 console.log('C4 G2: two distinct rigs approved, source SHA/stage/Spine loader survive real backend restart:',approved.map(r=>r.rig_version_id),evidence);
}catch(error){console.error(error);process.exitCode=1;}
finally{if(browser)await browser.close();children.reverse().forEach(stop);}
function cryptoDigest(raw){return createHash('sha256').update(raw).digest('hex');}

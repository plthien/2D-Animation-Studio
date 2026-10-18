/**
 * C5 real browser acceptance candidate — actual original raster, approved C4 rig,
 * external Director import, compiled motion and official Spine/Pixi canvas.
 * Any mismatch fails CI; no mocked backend or paid provider.
 */
import {chromium} from 'playwright';
import {spawn,spawnSync} from 'node:child_process';
import {readFileSync,mkdirSync,mkdtempSync,copyFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {createHash} from 'node:crypto';

const root=resolve('.'),dir=mkdtempSync(join(tmpdir(),'c5-browser-'));
const evidence=join(root,'artifacts','c5');mkdirSync(evidence,{recursive:true});
const fixture=spawnSync('python',['tools/c4_fixture.py',dir],{cwd:root,stdio:'inherit'});
if(fixture.status!==0)throw Error('C4 source fixture creation failed');
const env={...process.env,DATABASE_URL:'sqlite:///'+join(dir,'c5.db').replaceAll('\\','/'),
 ARTIFACT_ROOT:join(dir,'artifacts'),AUTO_APPLY_MIGRATIONS:'true'};
const BASE='http://127.0.0.1:8000';let browser,server;const children=[];
function run(bin,args){const child=spawn(bin,args,{cwd:root,env,stdio:'inherit',windowsHide:true});children.push(child);return child;}
function stop(c){if(!c?.pid)return;if(process.platform==='win32')spawnSync('taskkill.exe',['/PID',String(c.pid),'/T','/F'],{stdio:'ignore'});else c.kill('SIGTERM');}
async function ready(url){for(let i=0;i<100;i++){try{if((await fetch(url)).ok)return;}catch{}await new Promise(r=>setTimeout(r,400));}throw Error('Server never became ready');}
async function api(method,path,body,idem){
 const response=await fetch(BASE+path,{method,headers:{...(body===undefined?{}:{'Content-Type':'application/json'}),
 ...(idem?{'Idempotency-Key':idem}:{})},body:body===undefined?undefined:JSON.stringify(body)});
 const payload=await response.json();
 if(!response.ok)throw Error(method+' '+path+' HTTP '+response.status+' '+JSON.stringify(payload));
 return payload.data;
}
async function reserved(pid,kind,fill){
 const prefix='/api/v1/projects/'+pid+'/authoring/'+kind;
 const pkg=await api('POST',prefix+'/prompt',{});
 const doc={...pkg.reserved_fields,...fill(pkg)};
 const validation=await api('POST',prefix+'/validate',{reservation_id:pkg.reservation_id,document:doc});
 if(!validation.valid)throw Error('Invalid '+kind+': '+JSON.stringify(validation));
 const imported=await api('POST',prefix+'/import',{reservation_id:pkg.reservation_id,document:doc});
 const workflow=await api('GET','/api/v1/projects/'+pid+'/workflow');
 await api('POST',prefix+'/'+imported.artifact_id+'/approve',
  {expected_head_revision:workflow.stages.find(x=>x.stage_key==='authoring').head_revision,
   expected_sha256:imported.sha256});
 return imported;
}
async function importPng(pid,kind,key,name,bytes){
 const form=new FormData();
 form.append('kind',kind);form.append('semantic_key',key);
 form.append('view',kind==='actor'?'front':'default');
 form.append('file',new Blob([bytes],{type:'image/png'}),name);
 const response=await fetch(BASE+'/api/v1/projects/'+pid+'/images/import',{method:'POST',body:form});
 const body=await response.json();if(!response.ok)throw Error(JSON.stringify(body));
 const candidate=body.data;
 await api('POST','/api/v1/projects/'+pid+'/assets/'+candidate.asset_version_id+'/review',{decision:'approved'});
 return candidate;
}
async function correctParts(pid,rigId){
 const base='/api/v1/projects/'+pid+'/rigging/rigs/'+rigId;
 const annotations=JSON.parse(readFileSync(join(dir,'rig-joints.json'),'utf8'));
 let revision=(await api('GET',base)).draft_revision;
 const roles=Object.keys((await api('GET',base)).parts);
 for(const role of roles){
  const form=new FormData();
  form.append('expected_revision',String(revision));
  form.append('file',new Blob([readFileSync(join(dir,'a-'+role+'.png'))],{type:'image/png'}),role+'.png');
  const response=await fetch(BASE+base+'/parts/'+role+'/replacement',{method:'POST',body:form});
  const data=await response.json();if(!response.ok)throw Error(JSON.stringify(data));
  revision=data.data.draft_revision;
  revision=(await api('POST',base+'/parts/'+role,{
   expected_revision:revision,placement:{x:0,y:0,width:1,height:1},
   pivot:annotations.pivots[role],layer:annotations.layers[role],reviewed:true})).draft_revision;
 }
 return revision;
}
function checksum(buffer){return createHash('sha256').update(buffer).digest('hex');}
function assert(ok,message){if(!ok)throw Error(message);}
function boneLocation(skeleton,name){
 const nodes=new Map(skeleton.bones.map(b=>[b.name,b]));
 function visit(id){const row=nodes.get(id);if(!row)throw Error('Missing required rig bone '+id);
  const origin=row.parent?visit(row.parent):[0,0];
  return [origin[0]+(row.x||0),origin[1]+(row.y||0)];}
 return visit(name);
}
try{
 server=run('python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000']);
 await ready(BASE+'/health');
 run('cmd.exe',['/d','/c','npm.cmd run dev -- --host 127.0.0.1']);
 await ready('http://127.0.0.1:5173');
 const channel=await api('POST','/api/v1/channels',{name:'C5 Direct Motion',slug:'c5-motion'},'c5-channel');
 const cid=channel.channel_id;
 const dna={schema_version:'channel_dna.v2',identity:{name:'C5 Director',audience:'Audience'},
  visual:{style:'Crude flat animation sprites',palette:['#aabbcc']},
  performance:{tone:'playful',motion_density:'medium'},
  narration:{language:'en',voice_character:'narrator'}};
 const revision=await api('PUT','/api/v1/channels/'+cid+'/dna',
  {channel_dna:dna,expected_head_revision:null,expected_head_artifact_id:null},'c5-dna');
 await api('POST','/api/v1/channels/'+cid+'/dna/'+revision.artifact_id+'/approve',
  {expected_head_revision:null,expected_sha256:revision.sha256,actor:'owner',
   reviewed_at:'2026-10-18T00:00:00Z'});
 const project=await api('POST','/api/v1/projects',
  {channel_id:cid,name:'C5 Action Shot',slug:'c5-action-shot'},'c5-project');
 const pid=project.project_id;
 browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:960}});
 await page.addInitScript(([c,p])=>{localStorage.setItem('animationSelectedChannelId',c);
  localStorage.setItem('animationSelectedProjectId',p);},[cid,pid]);

 // Freeze an actual one-shot source only after reading real joint locations.
 // 240 frames = 10 seconds at 24fps.
 const actorImage=await importPng(pid,'actor','character_a','character-a.png',
   readFileSync(join(dir,'actor-a.png')));
 // The prop is an independently authored, visibly red/yellow small object.
 const propBytes=await page.evaluate(async()=>{
  const canvas=document.createElement('canvas');canvas.width=80;canvas.height=80;
  const c=canvas.getContext('2d');c.clearRect(0,0,80,80);
  c.fillStyle='#e02d2d';c.beginPath();c.arc(40,40,28,0,Math.PI*2);c.fill();
  c.fillStyle='#f9de65';c.fillRect(36,13,8,14);
  return [...new Uint8Array(await (await new Promise(res=>canvas.toBlob(res,'image/png'))).arrayBuffer())];
 });
 const propImage=await importPng(pid,'prop','prop_orb','orb.png',new Uint8Array(propBytes));
 const ideas=await reserved(pid,'topic-ideas',p=>({
  channel_dna_artifact_id:p.dna_metadata.artifact_id,channel_dna_hash:p.dna_metadata.sha256,
  ideas:[{idea_id:'idea_one',title:'Character carries a bright orb',premise:'One actual articulated exchange'}]}));
 const script=await reserved(pid,'script',()=>({
  topic_ideas_artifact_id:ideas.artifact_id,selected_idea_id:'idea_one',
  full_text:'He finds the orb.',sections:[{section_id:'section_one',start_char:0,end_char:17,text:'He finds the orb.'}]}));
 // The exact approved rig is created using the existing C4 review and real renderer.
 const initialActor={actor_id:'character_a',x:0,y:0,facing:'right'};
 const initialProp={prop_id:'prop_orb',x:0,y:0,held_by:null};
 // Start with approximate world locations; after C4 proof the approved frozen rig
 // determines usable IK targets. We must not silently rewrite approved ShotPlan.
 const prep=await reserved(pid,'shot-plan',()=>({
  script_artifact_id:script.artifact_id,script_sha256:script.sha256,
  actor_ids:['character_a'],prop_ids:['prop_orb'],location_ids:['location_one'],
  shots:[{shot_id:'shot_one',duration_frames:240,actor_ids:['character_a'],
   prop_ids:['prop_orb'],location_id:'location_one',utterance:null,
   spatial_anchors:[{anchor_id:'anchor_approach',x:80,y:0},
                    {anchor_id:'anchor_delivery',x:150,y:0},
                    {anchor_id:'anchor_drop',x:175,y:75}],
   initial_world_state:{actors:[initialActor],props:[initialProp]},
   final_world_state:{actors:[{...initialActor,x:150}],
                      props:[{...initialProp,x:175,y:75}]}]}]}));
 const required=await api('GET','/api/v1/projects/'+pid+'/resolver/resolution');
 const actorReq=required.requirements.find(x=>x.requirement.kind==='actor');
 const propReq=required.requirements.find(x=>x.requirement.kind==='prop');
 assert(actorReq&&propReq,'Missing real requirements');
 for(const [req,version] of [[actorReq,actorImage.asset_version_id],[propReq,propImage.asset_version_id]]){
  await api('POST','/api/v1/projects/'+pid+'/asset-bindings',
   {requirement_id:req.requirement.requirement_id,asset_version_id:version,
    expected_fingerprint:required.requirements_fingerprint});
 }
 const start=await api('POST','/api/v1/projects/'+pid+'/rigging/rigs',
  {asset_version_id:actorImage.asset_version_id});
 await correctParts(pid,start.rig_id);
 await page.goto('http://127.0.0.1:5173/studio',{waitUntil:'networkidle'});
 await page.locator('.pipeline-step').nth(3).click();
 await page.getByTestId('c4-rigging-workshop').getByRole('button',
  {name:'Edit draft '+start.rig_id.slice(0,14)}).click();
 await page.getByRole('button',{name:'Export immutable Spine 4.2 candidate'}).click();
 await page.getByText('Official loader succeeded in current browser session (not backend approval proof)').waitFor({timeout:30000});
 await page.getByRole('button',{name:'Verify official runtime and five poses'}).click();
 await page.getByTestId('c4-proof-ready').waitFor({timeout:30000});
 await page.getByRole('button',{name:'Approve verified rig version'}).click();
 await page.getByTestId('c4-rig-approved').waitFor({timeout:30000});
 const versions=(await api('GET','/api/v1/projects/'+pid+'/rigging/rigs')).items
  .filter(r=>r.rig_id===start.rig_id&&r.status==='approved');
 const version=versions.at(-1)?.rig_version_id;
 assert(version,'C4 real rig not approved');
 await page.reload({waitUntil:'networkidle'});
 await page.locator('.pipeline-step').nth(3).click();
 await page.getByRole('button',{name:/Play approved/}).last().click();
 await page.getByTestId('c4-official-runtime').getByText(
  'Official loader succeeded in current browser session (not backend approval proof)').waitFor({timeout:30000});
 await page.getByRole('combobox',{name:'Required project actor'}).selectOption(actorReq.requirement.requirement_id);
 await page.getByRole('button',{name:'Use previewed rig in this project'}).click();
 assert((await api('GET','/api/v1/projects/'+pid+'/rigging/resolution')).readiness==='approved',
  'Project rig selection incomplete');

 // Actual Spine/Pixi proof for extra actions without rewriting approved C4 rig bytes.
 await page.locator('.pipeline-step').nth(4).click();
 await page.getByTestId('c5-director').waitFor();
 await page.getByRole('button',{name:'Verify nine official Spine poses'}).click();
 await page.getByText('Approved immutable C5 capability certificate:',{exact:false}).waitFor({timeout:30000});
 const capability=await api('GET','/api/v1/projects/'+pid+'/motion/capabilities');
 assert(capability.rigs[0]?.certified,'Nine motion capabilities were not certified');
 const directorPkg=await api('POST','/api/v1/projects/'+pid+'/director/prompt',{});
 const actions=[
  ['walk_a','walk_to',0,56,'anchor_approach',null,'none'],
  ['reach_a','reach_for',56,90,'prop_orb','prop_orb','left'],
  ['grab_a','grab',90,104,'prop_orb','prop_orb','left'],
  ['carry_a','carry_to',104,166,'anchor_delivery','prop_orb','left'],
  ['place_a','place_at',166,196,'anchor_drop','prop_orb','left'],
  ['react_a','react',196,216,null,null,'none'],
  ['idle_a','idle',216,240,null,null,'none']
 ].map(([action_id,action,start_frame,end_frame,target_id,prop_id,hand])=>({
  action_id,action,shot_id:'shot_one',actor_id:'character_a',start_frame,end_frame,
  target_id,prop_id,hand}));
 const plan={...directorPkg.reserved_fields,actions};
 const report=await api('POST','/api/v1/projects/'+pid+'/director/validate',
  {reservation_id:directorPkg.reservation_id,document:plan});
 assert(report.valid,'Director JSON rejected: '+JSON.stringify(report));
 const draft=await api('POST','/api/v1/projects/'+pid+'/director/import',
  {reservation_id:directorPkg.reservation_id,document:plan});
 const current=await api('GET','/api/v1/projects/'+pid+'/workflow');
 await api('POST','/api/v1/projects/'+pid+'/director/'+draft.artifact_id+'/approve',{
  expected_head_revision:current.stages.find(x=>x.stage_key==='director').head_revision,
  expected_sha256:draft.sha256});
 const compiled=await api('POST','/api/v1/projects/'+pid+'/motion/compile',{});
 assert(compiled.kind==='compiled_film.v1','Motion failed to publish real compiled film');
 const samples=new Map();
 for(const frame of [0,120,40,239,80,160,120,0,200]){
  const result=await api('GET','/api/v1/projects/'+pid+'/motion/compilations/'+compiled.artifact_id+
   '/shots/shot_one/frames/'+frame);
  if(samples.has(frame))assert(samples.get(frame)===result.fingerprint,'Frame-seek determinism mismatch');
  samples.set(frame,result.fingerprint);
 }
 await page.reload({waitUntil:'networkidle'});
 await page.locator('.pipeline-step').nth(5).click();
 await page.getByTestId('c5-motion').waitFor();
 await page.getByTestId('c5-spine-pixi-viewport').locator('canvas').waitFor({timeout:30000});
 for(const [frame,label] of [[0,'idle'],[40,'walk'],[80,'reach'],[100,'grab'],
  [140,'carry'],[185,'place'],[206,'react'],[239,'rest']]){
  await page.getByRole('slider',{name:'Exact motion frame'}).fill(String(frame));
  await page.getByTestId('c5-spine-pixi-viewport').getByText('Deterministic frame:',{exact:false}).waitFor({timeout:30000});
  await page.getByTestId('c5-spine-pixi-viewport').locator('canvas').screenshot({
   path:join(evidence,'c5-'+label+'-'+frame+'.png')});
 }
 console.log('C5 CHROMIUM PREVIEW proof',compiled.artifact_id,'real official Spine/Pixi PNGs',evidence);
 stop(server);await new Promise(r=>setTimeout(r,1400));
 server=run('python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000']);
 await ready(BASE+'/health');
 const reopened=await api('GET','/api/v1/projects/'+pid+'/motion/compilations/'+compiled.artifact_id);
 assert(reopened.artifact.sha256===compiled.sha256,'Immutable compilation did not survive restart');
 const repeat=await api('GET','/api/v1/projects/'+pid+'/motion/compilations/'+compiled.artifact_id+
  '/shots/shot_one/frames/120');
 assert(repeat.fingerprint===samples.get(120),'Frame 120 not deterministic across restart');
 console.log('C5 ACCEPTANCE fixture completed: real rig, prompt, plan, compile, WebGL frames, restart');
}catch(err){console.error(err);process.exitCode=1;}
finally{if(browser)await browser.close();children.reverse().forEach(stop);}

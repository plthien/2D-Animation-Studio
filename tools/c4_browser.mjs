/** Real C4 Chromium / FastAPI / SQLite / official Spine runtime smoke.
 * Self-generated original cartoon fixtures; no Spineboy, no fake loader.
 * Deliberately does NOT claim rig approval (backend verification incomplete).
 */
import {chromium} from 'playwright';
import {spawn,spawnSync} from 'node:child_process';
import {readFileSync,mkdirSync,mkdtempSync} from 'node:fs';
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
async function sendImage(pid,who){
 const form=new FormData();
 form.append('kind','actor');form.append('semantic_key','character_'+who);
 form.append('view','front');
 form.append('file',new Blob([readFileSync(join(dir,'actor-'+who+'.png'))],{type:'image/png'}),'actor-'+who+'.png');
 const res=await fetch(BASE+'/api/v1/projects/'+pid+'/images/import',{method:'POST',body:form});
 const val=await res.json();if(!res.ok)throw Error(JSON.stringify(val));
 return val.data;
}
async function partFix(pid,rig){
 const base='/api/v1/projects/'+pid+'/rigging/rigs/'+rig;
 let doc=await api('GET',base);
 let n=doc.draft_revision;
 // A real persisted mask change, not an in-memory UI-only overlay.
 const fixed=await api('POST',base+'/parts/head',{expected_revision:n,strokes:[{x:.5,y:.4,radius:.005,mode:'paint'}],pivot:{x:.52,y:.42}});
 n=fixed.draft_revision;
 for(const role of Object.keys(doc.parts)){
  try{n=(await api('POST',base+'/parts/'+role,{expected_revision:n,reviewed:true})).draft_revision;}
  catch(error){
   const form=new FormData();
   form.append('expected_revision',String(n));
   form.append('file',new Blob([readFileSync(join(dir,'replacement.png'))],{type:'image/png'}),role+'.png');
   const res=await fetch(BASE+base+'/parts/'+role+'/replacement',{method:'POST',body:form});
   const out=await res.json();if(!res.ok)throw Error('Replacement '+role+': '+JSON.stringify(out)+' '+String(error));
   n=out.data.draft_revision;
   n=(await api('POST',base+'/parts/'+role,{expected_revision:n,reviewed:true})).draft_revision;
  }
 }
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
 browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:900}});
 await page.addInitScript(([c,p])=>{localStorage.setItem('animationSelectedChannelId',c);localStorage.setItem('animationSelectedProjectId',p);},[cid,pid]);
 await page.goto('http://127.0.0.1:5173/studio',{waitUntil:'networkidle'});
 await page.getByTestId('animation-studio').waitFor();
 await page.locator('.pipeline-step').nth(3).click();
 await page.getByTestId('c4-rigging-workshop').waitFor();
 for(const who of ['a','b']){
  const version=await sendImage(pid,who);
  await api('POST','/api/v1/projects/'+pid+'/assets/'+version.asset_version_id+'/review',{decision:'approved'});
  const draft=await api('POST','/api/v1/projects/'+pid+'/rigging/rigs',{asset_version_id:version.asset_version_id});
  // Real UI pointer interactions must alter persisted mask bytes/pivot, not
  // merely update a form or an in-memory preview.
  await page.reload({waitUntil:'networkidle'});
  await page.locator('.pipeline-step').nth(3).click();
  const workshop=page.getByTestId('c4-rigging-workshop');
  await workshop.getByRole('button',{name:'Reopen draft '+draft.rig_id.slice(0,14)}).click();
  await workshop.getByText('Draft revision 1',{exact:false}).waitFor();
  const editCanvas=workshop.getByRole('img',{name:'Interactive source mask editor'});
  await editCanvas.click({position:{x:110,y:160}});
  await workshop.getByText('Draft revision 2',{exact:false}).waitFor();
  await workshop.getByRole('combobox',{name:'Tool'}).selectOption('pivot');
  await editCanvas.click({position:{x:130,y:115}});
  await workshop.getByText('Draft revision 3',{exact:false}).waitFor();
  const uiEdited=await api('GET','/api/v1/projects/'+pid+'/rigging/rigs/'+draft.rig_id);
  if(uiEdited.draft_revision!==3||uiEdited.parts.head.pivot.x===.5)
   throw Error('UI mask/pivot pointer edits not persisted');
  const n=await partFix(pid,draft.rig_id);
  const exported=await api('POST','/api/v1/projects/'+pid+'/rigging/rigs/'+draft.rig_id+'/export',{expected_revision:n});
  if(exported.loader_verified!==false)throw Error('Unverified loader was reported as verified');
  await page.reload({waitUntil:'networkidle'});
  await page.locator('.pipeline-step').nth(3).click();
  await page.getByTestId('c4-rigging-workshop').getByRole('button',{name:'Reopen draft '+draft.rig_id.slice(0,14)}).click();
  await page.getByRole('button',{name:'Export immutable Spine 4.2 candidate'}).click();
  await page.getByTestId('c4-official-runtime').waitFor();
  await page.getByText('Official loader succeeded in current browser session (not backend approval proof)').waitFor({timeout:30000});
  for(const pose of ['idle','walk','reach','grab']){
   await page.getByTestId('c4-official-runtime').getByRole('button',{name:pose,exact:true}).click();
   const name='rig-'+who+'-'+pose+'.png';
   await page.getByTestId('c4-official-runtime').screenshot({path:join(evidence,name)});
  }
  await page.getByRole('button',{name:'Verify official runtime and five poses'}).click();
  await page.getByTestId('c4-proof-ready').waitFor({timeout:30000});
  await page.getByRole('button',{name:'Approve verified rig version'}).click();
  await page.getByTestId('c4-rig-approved').waitFor({timeout:30000});
  const stage=(await api('GET','/api/v1/projects/'+pid+'/workflow')).stages.find(x=>x.stage_key==='rigging');
  if(!stage||stage.readiness!=='approved')throw Error('Proof accepted without approved C4 readiness: '+JSON.stringify(stage));
  const sha=cryptoDigest(readFileSync(join(evidence,'rig-'+who+'-idle.png')));
  console.log(who,version.source_sha256,draft.rig_id,stage.head_artifact_id,'approved official rig idle sha='+sha);
  await page.reload({waitUntil:'networkidle'});
  await page.locator('.pipeline-step').nth(3).click();
  await page.getByRole('button',{name:/Play approved/}).last().click();
  await page.getByTestId('c4-official-runtime').getByText('Official loader succeeded in current browser session (not backend approval proof)').waitFor({timeout:30000});
 }
 const images=['a','b'].flatMap(who=>['idle','walk','reach','grab'].map(p=>cryptoDigest(readFileSync(join(evidence,'rig-'+who+'-'+p+'.png')))));
 if(new Set(images).size<6)throw Error('Real poses/source rigs not visually distinct enough');
 const refreshed=(await api('GET','/api/v1/projects/'+pid+'/rigging/rigs')).items;
 const approved=refreshed.filter(r=>r.status==='approved');
 if(approved.length!==2)throw Error('Expected two independently approved immutable rig versions, got '+approved.length);
 // Genuine backend restart with the SAME disposable SQLite/artifact root.
 stop(server);
 await new Promise(r=>setTimeout(r,1200));
 server=run('python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000']);
 await ready(BASE+'/health');
 const afterRestart=await api('GET','/api/v1/projects/'+pid+'/rigging/rigs');
 const stable=afterRestart.items.filter(r=>r.status==='approved');
 if(stable.length!==2||stable.some(row=>!approved.some(old=>old.rig_version_id===row.rig_version_id)))
  throw Error('Approved immutable rig identities not preserved after backend restart');
 const stageRestart=(await api('GET','/api/v1/projects/'+pid+'/workflow')).stages.find(x=>x.stage_key==='rigging');
 if(stageRestart.readiness!=='approved')throw Error('Rigging stage not ready after actual backend restart');
 await page.reload({waitUntil:'networkidle'});
 await page.locator('.pipeline-step').nth(3).click();
 await page.getByRole('button',{name:/Play approved/}).last().click();
 await page.getByTestId('c4-official-runtime').getByText('Official loader succeeded in current browser session (not backend approval proof)').waitFor({timeout:30000});
 await page.getByTestId('c4-official-runtime').screenshot({path:join(evidence,'approved-rig-after-backend-restart.png')});
 console.log('C4 G2: two distinct rigs approved, source SHA/stage/Spine loader survive real backend restart:',approved.map(r=>r.rig_version_id),evidence);
}catch(error){console.error(error);process.exitCode=1;}
finally{if(browser)await browser.close();children.reverse().forEach(stop);}
function cryptoDigest(raw){return createHash('sha256').update(raw).digest('hex');}

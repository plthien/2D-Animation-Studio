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
const disposable=mkdtempSync(join(tmpdir(),'c2-browser-'));
const evidence=join(root,'artifacts','c2');
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
  await page.screenshot({path:join(evidence,label+'-'+w+'x'+h+'.png'),fullPage:true,animations:'disabled'});
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
 await createChannel.locator('input').nth(1).fill('c2-browser-channel');
 await createChannel.getByRole('button',{name:'Create channel'}).click();
 await page.getByTestId('channel-card-grid').getByText('C2 Browser Channel').waitFor();
 const editor=page.getByTestId('channel-dna-editor');
 await editor.locator('textarea').nth(0).fill('Animation fans');
 await editor.locator('textarea').nth(1).fill('Sketchy flat color 2D figures, intentionally rough');
 await editor.locator('textarea').nth(2).fill('Funny, expressive physical comedy');
 await editor.locator('textarea').nth(3).fill('Friendly casual narrator');
 await page.getByTestId('save-dna').click();
 await page.waitForFunction(()=>!document.querySelector('[data-testid="approve-dna"]')?.hasAttribute('disabled'));
 await page.getByTestId('approve-dna').click();
 await page.getByText('Approved head').waitFor();
 await capture(page,'channels');
 await page.locator('nav button').filter({hasText:'Projects'}).first().click();
 await page.getByTestId('new-project-button').click();
 const createProject=page.getByTestId('create-project-modal');
 await createProject.locator('input').nth(0).fill('C2 Browser Pilot');
 await createProject.locator('input').nth(1).fill('c2-browser-pilot');
 await createProject.getByRole('button',{name:'Create project'}).click();
 await page.getByTestId('animation-studio').waitFor();
 for(const label of ['Authoring','Resolver','Generation','Rigging','Director','Motion','Delivery']){
  assert((await page.getByTestId('animation-studio').getByText(label,{exact:true}).count())>=1,
   'Missing animation stage: '+label);
 }
 await capture(page,'studio');
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
 assert(errors.length===0,'Browser runtime exceptions: '+errors.join('; '));
 console.log('C2 browser: real Channel → DNA → Project → refresh → API restart PASS');
 console.log('Evidence:',evidence);
} finally {
 if(browser)await browser.close();
 kill(ui);kill(api);
}

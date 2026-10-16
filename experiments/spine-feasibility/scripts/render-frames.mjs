import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {spawn,spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {chromium} from 'playwright';
import {approvedAssetPreflight,sha} from './preflight.mjs';

const root=fileURLToPath(new URL('../',import.meta.url));
const output=path.join(root,'output');
const framesDir=path.join(output,'frames');
const verifyCode=(cmd,args)=> {
  const result=spawnSync(cmd,args,{cwd:root,encoding:'utf8',maxBuffer:1024*1024*5});
  if(result.error || result.status!==0) throw Error('EXTERNAL_PROCESS_FAILURE '+cmd+': '+String(result.error||result.stderr).slice(-2000));
  return result.stdout;
};
const readHeader=(png)=>{
  if(png.subarray(0,8).toString('hex')!=='89504e470d0a1a0a') throw Error('INVALID_PNG_SIGNATURE');
  if(png.readUInt32BE(16)!==1280 || png.readUInt32BE(20)!==720) throw Error('INVALID_FRAME_DIMENSIONS');
};
async function waitForServer() {
  for(let attempt=0;attempt<75;attempt++) {
    try{const r=await fetch('http://127.0.0.1:4271/');if(r.ok)return;}catch{}
    await new Promise(r=>setTimeout(r,350));
  }
  throw Error('VITE_SERVER_START_FAILED');
}
async function capture(page,index) {
  const state=await page.evaluate(f=>window.G1.evaluation(f),index);
  if(!state?.officialRuntimeLoaded || !state?.prop?.world)throw Error('FRAME_NOT_MATERIALIZED: '+index);
  const png=await page.locator('canvas').screenshot({animations:'disabled',caret:'hide'});
  readHeader(png);
  return {png,hash:sha(png),stateHash:sha(Buffer.from(JSON.stringify(state))),state};
}
async function freshPage(browser) {
  const context=await browser.newContext({viewport:{width:1280,height:720},deviceScaleFactor:1,colorScheme:'light'});
  const page=await context.newPage();
  await page.goto('http://127.0.0.1:4271/',{waitUntil:'networkidle'});
  const available=await page.waitForFunction(()=>typeof window.G1?.ready==='boolean',{timeout:25000}).catch(()=>null);
  if(!available) throw Error('REAL_SPINE_INITIALIZATION_TIMEOUT');
  const state=await page.evaluate(()=>({ready:window.G1.ready,error:window.G1.error,identity:window.G1.identity,backend:window.G1.rendererBackend}));
  if(!state.ready)throw Error('REAL_SPINE_INITIALIZATION_FAILED: '+state.error);
  return {context,page,identity:state.identity,backend:state.backend};
}
async function main() {
  const p=approvedAssetPreflight();
  fs.rmSync(output,{force:true,recursive:true});fs.mkdirSync(framesDir,{recursive:true});
  const viteScript=path.join(root,'node_modules','vite','bin','vite.js');
  const server=spawn(process.execPath,[viteScript,'--host','127.0.0.1','--port','4271','--strictPort'],{
    cwd:root,stdio:['ignore','pipe','pipe'],windowsHide:true});
  let log='';for(const stream of [server.stdout,server.stderr])stream.on('data',d=>{log+=d.toString();log=log.slice(-30000);});
  let browser;
  try {
    await waitForServer();
    browser=await chromium.launch({channel:'chrome',headless:true,args:['--use-gl=angle','--use-angle=swiftshader']});
    const first=await freshPage(browser);
    const pngHashes=[],stateHashes=[];
    for(let i=0;i<240;i++){
      const entry=await capture(first.page,i);
      fs.writeFileSync(path.join(framesDir,String(i).padStart(6,'0')+'.png'),entry.png);
      pngHashes.push(entry.hash);stateHashes.push(entry.stateHash);
    }
    if(new Set(pngHashes).size<12)throw Error('BLANK_OR_STATIC_RENDER: insufficient changing frames');
    const second=await freshPage(browser);
    if(second.identity!==first.identity)throw Error('FROZEN_INPUT_IDENTITY_CHANGED');
    const sampled=[143,143,0,239,48,97,195,114,168,72,239];
    for(const i of sampled){
      const entry=await capture(second.page,i);
      if(entry.hash!==pngHashes[i] || entry.stateHash!==stateHashes[i])
        throw Error('PIXEL_OR_STATE_NONDETERMINISTIC frame='+i);
    }
    await second.context.close();await first.context.close();
    const mp4=path.join(output,'g1-spine-feasibility.mp4');
    verifyCode('ffmpeg',['-hide_banner','-loglevel','error','-y','-framerate','24','-start_number','0','-i',
      path.join(framesDir,'%06d.png'),'-frames:v','240','-c:v','libx264','-pix_fmt','yuv420p','-r','24','-movflags','+faststart',mp4]);
    const ffprobe=JSON.parse(verifyCode('ffprobe',['-v','error','-show_streams','-show_format','-of','json',mp4]));
    fs.writeFileSync(path.join(output,'ffprobe.json'),JSON.stringify(ffprobe,null,2));
    const stream=ffprobe.streams?.find(s=>s.codec_type==='video');
    if(!stream || stream.codec_name!=='h264' || stream.width!==1280 || stream.height!==720 ||
      stream.avg_frame_rate!=='24/1' || Math.abs(Number(stream.duration||ffprobe.format.duration)-10)>0.001 ||
      (stream.nb_frames&&Number(stream.nb_frames)!==240))throw Error('MP4_METADATA_INVALID');
    verifyCode('ffmpeg',['-hide_banner','-loglevel','error','-i',mp4,'-f','null','-']);
    const report={gate:'G1_EVIDENCE_CANDIDATE_NEEDS_HUMAN_AND_WINDOWS11',
      frames:240,fps:24,width:1280,height:720,scenario:'g1-shot.json',
      assetHashes:p.sha256,runtime:p.spine_runtime,pixi:p.pixi_version,renderer:first.backend,
      node:process.version,platform:process.platform,osRelease:os.release(),
      browser:browser.version(),fingerprint:first.identity,
      frameSha256:pngHashes,stateSha256:stateHashes,
      sampled:[0,48,97,114,143,168,195,239].map(i=>({index:i,pngSha256:pngHashes[i],stateSha256:stateHashes[i]})),
      mp4Sha256:sha(fs.readFileSync(mp4)),ffprobe};
    fs.writeFileSync(path.join(output,'manifest.json'),JSON.stringify(report,null,2));
    console.log('G1_RENDER_CANDIDATE: 240 frames and MP4 verified, consumer Windows 11 and manual visual review still required');
  } finally {
    await browser?.close();server.kill();
    if(process.exitCode) console.error(log);
  }
}
main().catch(err=>{console.error('G1 BLOCKED:',err.stack||err);process.exitCode=2;});

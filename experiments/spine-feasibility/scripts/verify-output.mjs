import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {sha} from './preflight.mjs';
const root=fileURLToPath(new URL('../',import.meta.url)),out=path.join(root,'output');
try {
  const m=JSON.parse(fs.readFileSync(path.join(out,'manifest.json'),'utf8'));
  if(m.frames!==240||m.fps!==24||m.width!==1280||m.height!==720||m.frameSha256?.length!==240)throw Error('INVALID_G1_MANIFEST');
  for(let i=0;i<240;i++){
    const file=path.join(out,'frames',String(i).padStart(6,'0')+'.png');
    const buf=fs.readFileSync(file);
    if(buf.readUInt32BE(16)!==1280||buf.readUInt32BE(20)!==720||sha(buf)!==m.frameSha256[i])
      throw Error('FRAME_VALIDATION_FAILED '+i);
  }
  if(sha(fs.readFileSync(path.join(out,'g1-spine-feasibility.mp4')))!==m.mp4Sha256)throw Error('MP4_HASH_MISMATCH');
  console.log('PASS 240 real PNG SHA-256 entries and MP4 hash; G1 final approval still requires licensed rig and Windows 11 + visual proof');
}catch(error){console.error('BLOCKED:',error.message);process.exitCode=2;}

import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {validateUsagePolicy} from '../src/licensing.mjs';
const root=fileURLToPath(new URL('../',import.meta.url));
export const sha=(buf)=>crypto.createHash('sha256').update(buf).digest('hex');
export function approvedAssetPreflight() {
  const folder=path.join(root,'public','assets');
  const manifestFile=path.join(folder,'provenance.json');
  if (!fs.existsSync(manifestFile)) throw Error('SPINE_LICENSE_OR_ASSET_BLOCKED: no approved provenance.json; see assets/README.md');
  const p=JSON.parse(fs.readFileSync(manifestFile,'utf8'));
  const scope=process.env.C1_USAGE_SCOPE ?? 'private_local_evaluation';
  validateUsagePolicy(p,scope);
  if(!String(p.spine_data_version).startsWith('4.2.') ||
    p.spine_runtime!=='4.2.120' || p.pixi_version!=='8.16.0') throw Error('SPINE_VERSION_INCOMPATIBLE');
  if(p.license.asset_rights.route==='official_spineboy_example') {
    const notice=path.join(folder,'license.txt');
    if(!fs.existsSync(notice) || sha(fs.readFileSync(notice))!==p.license.asset_rights.notice_sha256)
      throw Error('EXAMPLE_LICENSE_NOTICE_MISSING_OR_TAMPERED');
  }
  for(const kind of ['skeleton','atlas','texture']) {
    const name=p[kind];
    if(typeof name!=='string' || path.basename(name)!==name || !/^[A-Za-z0-9_.-]+$/.test(name)) throw Error('ASSET_FILENAME_UNSAFE: '+kind);
    const filename=path.join(folder,name);
    if(!fs.existsSync(filename))throw Error('APPROVED_ASSET_MISSING: '+filename);
    if(sha(fs.readFileSync(filename))!==p.sha256?.[kind]) throw Error('APPROVED_ASSET_HASH_MISMATCH: '+name);
  }
  if(!p.bones?.leftHand || !p.bones?.root)throw Error('APPROVED_RIG_BONES_MISSING');
  return p;
}
if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  try{const p=approvedAssetPreflight();console.log('PASS LEGALLY_APPROVED_ASSETS spine='+p.spine_data_version);}
  catch(error){console.error('G1 BLOCKED:',error.message);process.exitCode=2;}
}

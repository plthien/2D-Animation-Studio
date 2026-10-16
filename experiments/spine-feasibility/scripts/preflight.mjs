import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../',import.meta.url));
export const sha=(buf)=>crypto.createHash('sha256').update(buf).digest('hex');
export function approvedAssetPreflight() {
  const folder=path.join(root,'public','assets');
  const manifestFile=path.join(folder,'provenance.json');
  if (!fs.existsSync(manifestFile)) throw Error('SPINE_LICENSE_OR_ASSET_BLOCKED: no approved provenance.json; see assets/README.md');
  const p=JSON.parse(fs.readFileSync(manifestFile,'utf8'));
  if(p.license?.operator_spine_license_verified!==true ||
    p.license?.rig_redistribution_verified!==true ||
    !p.license?.rights_evidence || p.license?.license_route==='trial') {
    throw Error('SPINE_LICENSE_UNVERIFIED: neither runtime/editor integration rights nor rig permissions established');
  }
  if(!String(p.spine_data_version).startsWith('4.2.') ||
    p.spine_runtime!=='4.2.120' || p.pixi_version!=='8.16.0') throw Error('SPINE_VERSION_INCOMPATIBLE');
  for(const kind of ['skeleton','atlas','texture']) {
    const name=p[kind];
    if(typeof name!=='string' || path.basename(name)!==name) throw Error('ASSET_FILENAME_UNSAFE: '+kind);
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

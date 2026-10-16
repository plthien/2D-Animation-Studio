// Official Esoteric Software Spineboy 4.2 example: noncommercial runtime evaluation only.
// Never distribute as a commercial product asset or treat this as an operator license.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../',import.meta.url));
const rev='e7dc1435fa4a0083ab431f1b28e083c14a1f5c68';
const base='https://raw.githubusercontent.com/EsotericSoftware/spine-runtimes/'+rev+'/examples/spineboy/';
const files={
  skeleton:'export/spineboy-pro.json',
  atlas:'export/spineboy.atlas',
  texture:'export/spineboy.png',
  notice:'license.txt'
};
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const folder=path.join(root,'public','assets');
async function main(){
  if(process.env.C1_OFFICIAL_SAMPLE_EVAL!=='1')throw Error('EXPLICIT_NONCOMMERCIAL_EVALUATION_OPT_IN_REQUIRED');
  if(!['private_local_evaluation','hosted_ci_evaluation'].includes(process.env.C1_USAGE_SCOPE))
    throw Error('SAMPLE_SCOPE_UNSUPPORTED');
  const bytes={};
  for(const [name,relative] of Object.entries(files)){
    const url=base+relative;
    const resp=await fetch(url,{redirect:'error',signal:AbortSignal.timeout(30000)});
    if(!resp.ok)throw Error('PINNED_OFFICIAL_ASSET_FETCH_FAILED '+name+' '+resp.status);
    bytes[name]=Buffer.from(await resp.arrayBuffer());
  }
  const notice=bytes.notice.toString('utf8');
  if(!notice.includes('Esoteric Software LLC')||
    !notice.includes('may not be used for commercial use')||
    !notice.includes('accompanied'))throw Error('OFFICIAL_NOTICE_UNEXPECTED');
  const skeleton=JSON.parse(bytes.skeleton.toString('utf8'));
  if(skeleton.skeleton?.spine!=='4.2.22')throw Error('OFFICIAL_SPINE_VERSION_CHANGED');
  if(!Array.isArray(skeleton.bones)||skeleton.bones.length<15)throw Error('OFFICIAL_RIG_BONES_MISSING');
  if(!bytes.atlas.toString('utf8').startsWith('spineboy.png'))throw Error('ATLAS_TEXTURE_MISMATCH');
  fs.mkdirSync(folder,{recursive:true});
  for(const [kind,name] of Object.entries({skeleton:'spineboy-pro.json',atlas:'spineboy.atlas',texture:'spineboy.png',notice:'license.txt'}))
    fs.writeFileSync(path.join(folder,name),bytes[kind],{flag:'w'});
  const provenance={
    source:{repository:'EsotericSoftware/spine-runtimes',commit:rev,licenseFile:base+'license.txt'},
    spine_data_version:skeleton.skeleton.spine,spine_runtime:'4.2.120',pixi_version:'8.16.0',
    skeleton:'spineboy-pro.json',atlas:'spineboy.atlas',texture:'spineboy.png',
    scene_scale:0.5,grip_offset:{x:0,y:0},
    bones:{root:'root',head:'head',leftUpperArm:'rear-upper-arm',leftForearm:'rear-bracer',
      leftHand:'gun',rightUpperArm:'front-upper-arm',rightForearm:'front-bracer',
      leftThigh:'front-thigh',rightThigh:'rear-thigh',leftShin:'front-shin',rightShin:'rear-shin'},
    sha256:Object.fromEntries(['skeleton','atlas','texture'].map(name=>[name,sha(bytes[name])])),
    license:{
      usage_scope:process.env.C1_USAGE_SCOPE,
      purpose:'noncommercial_runtime_feasibility_only',
      runtime_rights:{
        route:'official_example_evaluation',
        evidence:'https://github.com/EsotericSoftware/spine-runtimes#licensing',
        product_integration_or_distribution_authorized:false
      },
      asset_rights:{
        route:'official_spineboy_example',noncommercial_only:true,
        evidence:'https://github.com/EsotericSoftware/spine-runtimes/blob/'+rev+'/examples/spineboy/license.txt',
        notice_file:'license.txt',notice_sha256:sha(bytes.notice),
        ci_redistribution_with_notice:process.env.C1_USAGE_SCOPE==='hosted_ci_evaluation',
        product_redistribution_authorized:false
      }
    }
  };
  fs.writeFileSync(path.join(folder,'provenance.json'),JSON.stringify(provenance,null,2)+'\n');
  console.log('PINNED_OFFICIAL_SPINEBOY_EVALUATION_ASSET_READY',JSON.stringify(provenance.sha256));
  console.log('NOTICE_SHA256',provenance.license.asset_rights.notice_sha256);
  console.log('This is noncommercial official example evaluation ONLY, not a Spine product integration license.');
}
main().catch(e=>{console.error('ASSET_ACQUISITION_BLOCKED',e.message);process.exitCode=2;});

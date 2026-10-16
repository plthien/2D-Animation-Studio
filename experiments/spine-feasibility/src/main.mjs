import { Application, Assets, Graphics } from 'pixi.js';
import { Spine } from '@esotericsoftware/spine-pixi-v8';
import { evaluateFrame } from './frame-evaluator.mjs';
import { ensure, finite2, validateScenario, compileSchedule, sealScenario } from './validation.mjs';
import {validateUsagePolicy} from './licensing.mjs';

const safeJson = async (url) => {
  const r = await fetch(url,{cache:'no-store'});
  ensure(r.ok,'ASSET_FETCH_FAILED',url+' HTTP '+r.status);
  return r.json();
};
const checkProvenance = (p) => {
  const scope=import.meta.env.VITE_C1_SCOPE || 'private_local_evaluation';
  validateUsagePolicy(p,scope);
  ensure(p.spine_data_version?.startsWith('4.2.'), 'SPINE_DATA_VERSION_MISMATCH');
  ensure([p.skeleton,p.atlas,p.texture].every(name=>typeof name==='string' && /^[A-Za-z0-9_.-]+$/.test(name) && name!=='..'), 'ASSET_FILENAME_UNSAFE');
  ensure(p.skeleton && p.atlas && p.texture && p.sha256?.skeleton && p.sha256?.atlas && p.sha256?.texture,
    'APPROVED_ASSET_MANIFEST_INCOMPLETE');
  ensure(p.bones && Object.values(p.bones).every(x=>typeof x==='string'&&x), 'RIG_BONE_MAPPING_INCOMPLETE');
};
async function digestBuffer(buffer) {
  const hash = await crypto.subtle.digest('SHA-256',buffer);
  return Array.from(new Uint8Array(hash)).map(x=>x.toString(16).padStart(2,'0')).join('');
}
async function verifyByteHash(url,expected) {
  ensure(/^[0-9a-f]{64}$/.test(expected),'ASSET_HASH_INVALID',url);
  const response=await fetch(url,{cache:'no-store'});
  ensure(response.ok,'ASSET_FILE_MISSING',url);
  ensure(await digestBuffer(await response.arrayBuffer())===expected,'ASSET_HASH_MISMATCH',url);
}
const main=async()=>{
  const ctx=await safeJson('/scenarios/g1-shot.json');
  validateScenario(ctx);
  const schedule=compileSchedule(ctx);
  const p=await safeJson('/assets/provenance.json');checkProvenance(p);
  await Promise.all([
    verifyByteHash('/assets/'+p.skeleton,p.sha256.skeleton),
    verifyByteHash('/assets/'+p.atlas,p.sha256.atlas),
    verifyByteHash('/assets/'+p.texture,p.sha256.texture),
    ...(p.license.asset_rights.route==='official_spineboy_example'?
      [verifyByteHash('/assets/license.txt',p.license.asset_rights.notice_sha256)]:[])
  ]);
  ensure(p.spine_runtime==='4.2.120' && p.pixi_version==='8.16.0','PACKAGE_IDENTITY_MISMATCH');
  const fingerprint=await digestBuffer(new TextEncoder().encode(
    JSON.stringify({ctx,hashes:p.sha256,runtime:p.spine_runtime,pixi:p.pixi_version})));
  sealScenario(ctx,fingerprint);
  const app=new Application();
  await app.init({width:1280,height:720,background:0xd5ddc6,preference:'webgl',resolution:1,autoDensity:false});
  ensure(app.renderer.type !== undefined && app.renderer.canvas,'WEBGL_RENDERER_UNAVAILABLE');
  document.getElementById('stage').appendChild(app.canvas);
  app.ticker.stop();
  Assets.add({alias:'approved_skeleton',src:'/assets/'+p.skeleton});
  Assets.add({alias:'approved_atlas',src:'/assets/'+p.atlas});
  await Assets.load(['approved_skeleton','approved_atlas']);
  const spine=Spine.from({skeleton:'approved_skeleton',atlas:'approved_atlas',autoUpdate:false});
  ensure(spine?.skeleton?.bones?.length>0,'REAL_SPINE_RIG_NOT_LOADED');
  const bones={};
  for (const [key,name] of Object.entries(p.bones)) {
    const bone=spine.skeleton.findBone(name);
    ensure(bone,'REQUIRED_SPINE_BONE_MISSING',name);
    bones[key]=bone;
  }
  const bg=new Graphics().rect(0,575,1280,145).fill(0x9eaa7d);
  const prop=new Graphics().roundRect(-18,-18,36,36,4).fill(0xb4794a).stroke({color:0x4e3b30,width:3});
  app.stage.addChild(bg,spine,prop);
  spine.scale.set(p.scene_scale);
  ensure(Number.isFinite(p.scene_scale)&&p.scene_scale>0,'INVALID_RIG_SCALE');
  const setupPose=()=>{spine.state.clearTracks();spine.skeleton.setToSetupPose();spine.update(0);};
  function render(frameIndex) {
    const evaluated=evaluateFrame(ctx.shot_id,frameIndex,ctx);
    setupPose();
    spine.position.set(evaluated.root.x,evaluated.root.y);
    for(const [key,delta] of Object.entries(evaluated.bones)) {
      ensure(bones[key],'REQUIRED_SPINE_BONE_MISSING',key);
      bones[key].rotation=bones[key].data.rotation+delta;
    }
    spine.update(0);
    app.renderer.render({container:app.stage});
    const handBone=bones.leftHand;
    const handLocal={x:handBone.worldX,y:handBone.worldY};
    spine.skeletonToPixiWorldCoordinates(handLocal);
    const worldProp=evaluated.prop.attachment==='spine_hand_bone'
      ? {x:handLocal.x+p.grip_offset.x,y:handLocal.y+p.grip_offset.y}
      : evaluated.prop.world;
    ensure(finite2(worldProp),'NONFINITE_PROP_WORLD');
    // No synthesized teleport at the two immutable ownership boundaries.
    if (frameIndex === schedule.grab?.end || frameIndex === (schedule.place?.end - 1)) {
      const contactTarget=frameIndex===schedule.grab?.end
        ? ctx.initial_world.prop
        : ctx.spatial_anchors.find(a=>a.id===schedule.place.target);
      const distance=Math.hypot(worldProp.x-contactTarget.x,worldProp.y-contactTarget.y);
      ensure(distance<=20,'PROP_CONTACT_DISCONTINUITY',
        'frame='+frameIndex+' hand=('+Math.round(worldProp.x)+','+Math.round(worldProp.y)+') target=('+Math.round(contactTarget.x)+','+Math.round(contactTarget.y)+') distance='+Math.round(distance)+'px; align rig contact');
    }
    prop.position.set(worldProp.x,worldProp.y);
    app.renderer.render({container:app.stage});
    const materialized={
      ...evaluated,
      prop:{...evaluated.prop,world:{x:worldProp.x,y:worldProp.y}},
      realBones:Object.fromEntries(Object.entries(bones).map(([name,b])=>[name,{x:b.worldX,y:b.worldY,rotation:b.rotation}])),
      officialRuntimeLoaded:true,rigHash:p.sha256.skeleton,rendererBackend:app.renderer.type
    };
    return materialized;
  }
  window.G1={
    ready:true,identity:fingerprint,rendererBackend:app.renderer.type,
    evaluation:(f)=>render(f),
    canvas:()=>app.canvas,
    versions:{spine:p.spine_runtime,pixi:p.pixi_version}
  };
  window.dispatchEvent(new Event('g1-ready'));
  render(0);
};
main().catch(error=>{
  const text=error?.stack??String(error);
  document.getElementById('status').textContent=text;
  window.G1={ready:false,error:text};
});

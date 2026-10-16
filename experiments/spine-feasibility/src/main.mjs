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
  // Both tabletops share the same prop resting height, so carry and release
  // need no hidden Y-axis shift.
  const supports=new Graphics().rect(540,452,80,12).fill(0x71684e)
    .rect(880,452,80,12).fill(0x71684e)
    .rect(552,464,10,112).fill(0x71684e)
    .rect(940,464,10,112).fill(0x71684e);
  const prop=new Graphics().roundRect(-18,-18,36,36,4).fill(0xb4794a).stroke({color:0x4e3b30,width:3});
  // The foreground fist must remain visible over the test prop.
  app.stage.addChild(bg,supports,prop,spine);
  ensure(Number.isFinite(p.scene_scale)&&p.scene_scale>0,'INVALID_RIG_SCALE');
  spine.scale.set(p.scene_scale);
  const setupPose=()=>{
    spine.state.clearTracks();
    spine.skeleton.setToSetupPose();
    spine.update(0);
  };
  const visibleFistSlot=spine.skeleton.findSlot('front-fist');
  ensure(visibleFistSlot && bones.leftHand.data.name==='front-fist',
    'VISIBLE_FRONT_FIST_MAPPING_REQUIRED');
  const gunSlot=spine.skeleton.findSlot('gun');
  if(p.license.asset_rights.route==='official_spineboy_example')
    ensure(gunSlot,'OFFICIAL_SAMPLE_GUN_SLOT_MISSING');
  const handWorld=()=>{
    const hand={x:bones.leftHand.worldX,y:bones.leftHand.worldY};
    spine.skeletonToPixiWorldCoordinates(hand);
    ensure(finite2(hand),'HAND_WORLD_COORDINATE_INVALID');
    return hand;
  };

  // A single, deterministic manual-fitting helper for THIS approved G1 shot:
  // pick two EXISTING Spineboy arm joint rotations against the real front-fist
  // bone. This is not C8 IK, not a generic motion planner, and does not invent
  // animation frames or use previous-frame mutable state.
  const approachX=ctx.initial_world.prop.x+ctx.rig.approach_root_offset_x;
  const contactGoal={
    x:ctx.initial_world.prop.x-p.grip_offset.x,
    y:ctx.initial_world.prop.y-p.grip_offset.y
  };
  const neutralUpper=bones.leftUpperArm.data.rotation;
  const neutralForearm=bones.leftForearm.data.rotation;
  function measureContact(upper,forearm){
    setupPose();
    spine.position.set(approachX,ctx.initial_world.actor.y);
    bones.leftUpperArm.rotation=neutralUpper+upper;
    bones.leftForearm.rotation=neutralForearm+forearm;
    spine.update(0);
    const fist=handWorld();
    return {upper,forearm,error:Math.hypot(fist.x-contactGoal.x,fist.y-contactGoal.y),fist};
  }
  let fit=null;
  for(let upper=-160;upper<=160;upper+=20){
    for(let forearm=-160;forearm<=160;forearm+=20){
      const probe=measureContact(upper,forearm);
      // Keep a compact natural-looking limb configuration when solutions tie.
      const rank=probe.error+0.008*(Math.abs(upper)+Math.abs(forearm));
      if(fit===null || rank<fit.rank)fit={...probe,rank};
    }
  }
  for(const step of [10,5,2,1,0.5,0.25]){
    for(const [da,db] of [[-1,0],[1,0],[0,-1],[0,1],[-1,-1],[1,1]]){
      const a=fit.upper+da*step,b=fit.forearm+db*step;
      if(Math.abs(a)>170 || Math.abs(b)>170)continue;
      const probe=measureContact(a,b);
      const rank=probe.error+0.008*(Math.abs(a)+Math.abs(b));
      if(rank<fit.rank)fit={...probe,rank};
    }
  }
  ensure(fit.error<=6,'VISIBLE_FRONT_FIST_CONTACT_UNREACHABLE',
    'real front-fist error='+fit.error.toFixed(2)+'px at approach root '+approachX+' fist='+JSON.stringify(fit.fist)+' angles='+fit.upper+','+fit.forearm+' neutral='+JSON.stringify(measureContact(0,0).fist));
  const contactPose={upper:fit.upper,forearm:fit.forearm,error:fit.error,approachX};
  const {grab,place,reach,reaction}=schedule;
  ensure(grab&&place&&reach&&reaction,'G1_INTERACTION_ACTIONS_MISSING');
  function render(frameIndex) {
    const evaluated=evaluateFrame(ctx.shot_id,frameIndex,ctx);
    setupPose();
    spine.position.set(evaluated.root.x,evaluated.root.y);
    for(const [key,delta] of Object.entries(evaluated.bones)) {
      ensure(bones[key],'REQUIRED_SPINE_BONE_MISSING',key);
      const applied=key==='leftUpperArm'?contactPose.upper*evaluated.handContactWeight:
        key==='leftForearm'?contactPose.forearm*evaluated.handContactWeight:delta;
      bones[key].rotation=bones[key].data.rotation+applied;
    }
    spine.update(0);
    if(gunSlot)gunSlot.setAttachment(null);
    const fistClosed=frameIndex>=Math.floor((grab.start+grab.end)/2)&&frameIndex<place.end;
    spine.skeleton.setAttachment('front-fist',fistClosed?'front-fist-closed':'front-fist-open');
    spine.update(0);
    const fist=handWorld();
    const worldProp=evaluated.prop.attachment==='spine_hand_bone'
      ? {x:fist.x+p.grip_offset.x,y:fist.y+p.grip_offset.y}
      : evaluated.prop.world;
    ensure(finite2(worldProp),'NONFINITE_PROP_WORLD');
    const contactAt=frameIndex===reach.end-1||frameIndex===grab.end-1||
      frameIndex===grab.end||frameIndex===place.end-1;
    if(contactAt){
      const target=frameIndex<grab.end?ctx.initial_world.prop:
        ctx.spatial_anchors.find(a=>a.id===place.target);
      const error=Math.hypot(fist.x+p.grip_offset.x-target.x,
        fist.y+p.grip_offset.y-target.y);
      // The hand must reach the real prop BEFORE attachment, not merely
      // jump to its current world position on the first carry frame.
      ensure(error<=8,'VISIBLE_HAND_CONTACT_INVALID',
        'frame='+frameIndex+' error='+error.toFixed(2));
    }
    prop.position.set(worldProp.x,worldProp.y);
    app.renderer.render({container:app.stage});
    return {
      ...evaluated,
      prop:{...evaluated.prop,world:{x:worldProp.x,y:worldProp.y}},
      handWorld:{x:fist.x,y:fist.y},
      frontFistClosed:fistClosed,
      contactPose,
      realBones:Object.fromEntries(Object.entries(bones).map(([name,b])=>[
        name,{x:b.worldX,y:b.worldY,rotation:b.rotation}])),
      officialRuntimeLoaded:true,rigHash:p.sha256.skeleton,
      rendererBackend:app.renderer.type
    };
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

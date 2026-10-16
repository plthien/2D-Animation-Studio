export const FPS=24, FRAMES=240;
export function ensure(condition,code,details='') {
  if(!condition){const e=new Error(code+(details?': '+details:''));e.code=code;throw e;}
}
export const finite2=p=>!!p && Number.isFinite(p.x) && Number.isFinite(p.y);
export const overlaps=(a,b)=>a.start<b.end && b.start<a.end;
const locomotion=new Set(['idle','walk_to','carry_to']);
const arms=new Set(['reach_for','grab','place_at','point_at']);
const requiresTarget=new Set(['walk_to','reach_for','grab','carry_to','place_at','point_at']);
const allowedTargets={
  walk_to:new Set(['actor','prop','anchor']),
  reach_for:new Set(['prop']),grab:new Set(['prop']),
  carry_to:new Set(['anchor']),place_at:new Set(['anchor']),
  point_at:new Set(['actor','prop','anchor'])
};
export function scenarioBinding(ctx) {
  // Exact content binding. The separate frozen SHA-256 identity contains this schedule.
  return JSON.stringify({
    shot:ctx.shot_id,fps:ctx.fps,frames:ctx.duration_frames,
    start:ctx.initial_world,anchors:ctx.spatial_anchors,
    rig:ctx.rig,actions:ctx.actions
  });
}
export function sealScenario(ctx, fingerprint) {
  ensure(/^[0-9a-f]{64}$/.test(fingerprint), 'FROZEN_INPUT_FINGERPRINT_MISSING');
  ctx.approvedScenarioBinding=scenarioBinding(ctx);
  ctx.fingerprint=fingerprint;
  return ctx;
}
export function resolveTarget(ctx,action) {
  const id=action.target;
  const matches=[
    ...(ctx.initial_world.actor.id===id?[{type:'actor',entity:ctx.initial_world.actor}]:[]),
    ...(ctx.initial_world.prop.id===id?[{type:'prop',entity:ctx.initial_world.prop}]:[]),
    ...ctx.spatial_anchors.filter(a=>a.id===id).map(entity=>({type:'anchor',entity}))
  ];
  ensure(matches.length===1,'ACTION_TARGET_UNKNOWN_OR_AMBIGUOUS',action.id);
  ensure(allowedTargets[action.kind]?.has(matches[0].type),'ACTION_TARGET_TYPE_INVALID',action.id);
  ensure(finite2(matches[0].entity),'ACTION_TARGET_NONFINITE',action.id);
  if(action.kind==='grab' || action.kind==='reach_for')
    ensure(action.target===ctx.initial_world.prop.id,'PROP_REFERENCE_INVALID',action.id);
  return matches[0];
}
export function compileSchedule(ctx) {
  ensure(ctx && typeof ctx==='object','FROZEN_CONTEXT_MISSING');
  ensure(ctx.fps===FPS && ctx.duration_frames===FRAMES && ctx.width===1280 && ctx.height===720,'G1_TIMING_INVALID');
  ensure(/^shot_[a-z0-9_]+$/.test(ctx.shot_id),'SHOT_ID_INVALID');
  ensure(ctx.initial_world?.actor?.id===ctx.rig?.actor_id && ctx.initial_world?.prop?.id &&
    ctx.initial_world.actor.id!==ctx.initial_world.prop.id,'ENTITY_ID_INVALID');
  ensure(finite2(ctx.initial_world.actor)&&finite2(ctx.initial_world.prop)&&finite2(ctx.initial_world.camera),'INITIAL_WORLD_INVALID');
  ensure(ctx.initial_world.prop.held_by===null,'INITIAL_GRIP_UNSUPPORTED');
  ensure(Array.isArray(ctx.actions)&&Array.isArray(ctx.spatial_anchors),'CHOREOGRAPHY_MISSING');
  ensure(Array.isArray(ctx.rig?.required_capabilities),'RIG_CAPABILITIES_MISSING');
  const entityIds=new Set([ctx.initial_world.actor.id,ctx.initial_world.prop.id]),anchors=new Set();
  for(const a of ctx.spatial_anchors) {
    ensure(typeof a.id==='string'&&a.id&&!entityIds.has(a.id)&&!anchors.has(a.id)&&finite2(a),
      'ANCHOR_ID_COLLISION_OR_INVALID',String(a.id));
    anchors.add(a.id);
  }
  const ids=new Set();
  const ordered=[...ctx.actions].sort((a,b)=>a.start-b.start||a.end-b.end||a.id.localeCompare(b.id));
  for(const a of ordered){
    ensure(typeof a.id==='string'&&a.id&&!ids.has(a.id),'DUPLICATE_ACTION_ID',String(a.id));
    ids.add(a.id);
    ensure(Number.isInteger(a.start)&&Number.isInteger(a.end)&&a.start>=0&&a.start<a.end&&a.end<=FRAMES,
      'ACTION_BOUNDS_INVALID',a.id);
    ensure(ctx.rig.required_capabilities.includes(a.kind),'RIG_CAPABILITY_MISSING',a.id);
    if(requiresTarget.has(a.kind))resolveTarget(ctx,a);
    if(['grab','carry_to','place_at'].includes(a.kind))
      ensure(a.prop===ctx.initial_world.prop.id,'PROP_REFERENCE_INVALID',a.id);
    if(arms.has(a.kind))ensure(['left','right'].includes(a.hand),'HAND_REQUIRED',a.id);
    if(['carry_to'].includes(a.kind))ensure(['left','right'].includes(a.hand),'HAND_REQUIRED',a.id);
    if(['walk_to','idle','react'].includes(a.kind))ensure(a.hand==='none','HAND_CHANNEL_INVALID',a.id);
  }
  for(let i=0;i<ordered.length;i++)for(let j=i+1;j<ordered.length;j++){
    const a=ordered[i],b=ordered[j];if(!overlaps(a,b))continue;
    if(locomotion.has(a.kind)&&locomotion.has(b.kind))
      ensure(false,'MOTION_CHANNEL_CONFLICT',a.id+'/'+b.id);
    if(arms.has(a.kind)&&arms.has(b.kind)&&a.hand===b.hand)
      ensure(false,'ARM_CHANNEL_CONFLICT',a.id+'/'+b.id);
  }
  const grab=ordered.filter(a=>a.kind==='grab');
  const place=ordered.filter(a=>a.kind==='place_at');
  const carries=ordered.filter(a=>a.kind==='carry_to');
  ensure(grab.length<=1&&place.length<=1&&carries.length<=1,'UNSUPPORTED_G1_GRIP_MULTIPLICITY');
  if(grab.length||place.length||carries.length){
    ensure(grab.length===1&&place.length===1,'GRIP_RELEASE_MISSING');
    const g=grab[0],p=place[0],c=carries[0];
    ensure(g.end<=p.start && g.hand===p.hand,'GRIP_RELEASE_ORDER_INVALID');
    if(c) ensure(g.end<=c.start&&c.end<=p.start&&c.hand===g.hand,'CARRY_WITHOUT_GRIP');
    for(const a of ordered) if(arms.has(a.kind)&&a!==g&&a!==p&&a.hand===g.hand&&
        overlaps(a,{start:g.end,end:p.end})){
      ensure(false,a.kind==='grab'?'PROP_ALREADY_OWNED':'OCCUPIED_HAND_CONFLICT',
        a.id+' / '+a.hand+' / ['+Math.max(a.start,g.end)+','+Math.min(a.end,p.end)+')');
    }
  }
  // G1 has at most one locomotion destination per supported leg of the shot.
  const walks=ordered.filter(a=>a.kind==='walk_to');
  ensure(walks.length<=1,'UNSUPPORTED_G1_SCHEDULE','multiple walk_to actions');
  return {ordered,grab:grab[0]??null,place:place[0]??null,carry:carries[0]??null,
    walk:walks[0]??null,reach:ordered.find(a=>a.kind==='reach_for')??null,
    reaction:ordered.find(a=>a.kind==='react')??null};
}
export function validateScenario(ctx){compileSchedule(ctx);return true;}
export function assertFrame(ctx,shotId,index){
  ensure(shotId===ctx.shot_id,'UNKNOWN_SHOT_ID',String(shotId));
  ensure(Number.isInteger(index)&&index>=0&&index<ctx.duration_frames,'FRAME_INDEX_OUT_OF_BOUNDS',String(index));
}

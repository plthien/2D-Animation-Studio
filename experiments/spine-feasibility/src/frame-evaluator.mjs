import {assertFrame,compileSchedule,ensure,finite2,scenarioBinding} from './validation.mjs';
const clamp=t=>Math.max(0,Math.min(1,t));
const lerp=(a,b,t)=>a+(b-a)*clamp(t);
const progress=(frame,action)=>clamp((frame-action.start)/(action.end-action.start));
const round=n=>Math.round(n*1e6)/1e6;
const freeze=v=>{if(v&&typeof v==='object'){Object.values(v).forEach(freeze);Object.freeze(v);}return v;};
const currentAction=(action,f)=>!!action&&action.start<=f&&f<action.end;
export function evaluateFrame(shotId,frameIndex,ctx){
  const s=compileSchedule(ctx);
  assertFrame(ctx,shotId,frameIndex);
  ensure(/^[0-9a-f]{64}$/.test(ctx.fingerprint??''),'FROZEN_INPUT_FINGERPRINT_MISSING');
  ensure(ctx.approvedScenarioBinding===scenarioBinding(ctx),'FROZEN_SCENARIO_IDENTITY_MISMATCH');
  const f=frameIndex,start=ctx.initial_world.actor,prop=ctx.initial_world.prop;
  const lookup=id=>id===start.id?start:id===prop.id?prop:ctx.spatial_anchors.find(a=>a.id===id);
  const walkEnd=s.walk?lookup(s.walk.target).x+(ctx.rig.approach_root_offset_x ?? -40):start.x;
  let x=start.x;
  if(s.walk) x=f<s.walk.start?start.x:f<s.walk.end?lerp(start.x,walkEnd,progress(f,s.walk)):walkEnd;
  const carryEnd=s.carry?lookup(s.carry.target).x+(ctx.rig.release_root_offset_x ?? -60):walkEnd;
  if(s.carry&&f>=s.carry.start) x=f<s.carry.end?lerp(walkEnd,carryEnd,progress(f,s.carry)):carryEnd;
  const activeMove=(currentAction(s.walk,f)||currentAction(s.carry,f));
  const move=activeMove?(s.carry&&currentAction(s.carry,f)?s.carry:s.walk):null;
  const phase=move?2*Math.PI*(f-move.start)/24:0;
  const reachRise=s.reach?progress(f,s.reach):0;
  const reachFall=s.place?1-progress(f,s.place):1;
  const reach=reachRise*reachFall;
  const pointing=s.ordered.find(a=>a.kind==='point_at'&&a.hand==='right'&&currentAction(a,f));
  const owned=!!s.grab&&!!s.place&&f>=s.grab.end&&f<s.place.end;
  const released=!!s.place&&f>=s.place.end;
  const destination=s.place?lookup(s.place.target):null;
  const headReact=s.reaction&&currentAction(s.reaction,f)?9*Math.sin(Math.PI*progress(f,s.reaction)):0;
  const bone={
    leftUpperArm:round(-53*reach),leftForearm:round(-26*reach),
    rightUpperArm:round(pointing?-55:(activeMove?18*Math.sin(phase):0)),
    rightForearm:round(pointing?-18:(activeMove?-12*Math.sin(phase):0)),
    leftThigh:round(activeMove?27*Math.sin(phase):0),
    rightThigh:round(activeMove?-27*Math.sin(phase):0),
    leftShin:round(activeMove?Math.max(0,-36*Math.sin(phase)):0),
    rightShin:round(activeMove?Math.max(0,36*Math.sin(phase)):0),
    head:round(headReact)
  };
  const world=owned?null:released?{x:destination.x,y:destination.y}:{x:prop.x,y:prop.y};
  const state={
    shotId,frameIndex,timeSeconds:round(f/ctx.fps),
    phase:s.ordered.find(a=>currentAction(a,f))?.kind??'static',
    root:{x:round(x),y:round(start.y)},bones:bone,
    prop:{id:prop.id,owner:owned?ctx.initial_world.actor.id+':'+s.grab.hand:null,
      attachment:owned?'spine_hand_bone':'world',world},
    camera:{...ctx.initial_world.camera},background:'flat_matte',
    frozenInputFingerprint:ctx.fingerprint
  };
  ensure(finite2(state.root)&&(!world||finite2(world))&&Object.values(bone).every(Number.isFinite),
    'NONFINITE_FRAME_STATE');
  return freeze(state);
}

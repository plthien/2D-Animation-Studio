import {assertFrame, ensure, finite2, validateScenario} from './validation.mjs';
const mix=(a,b,t)=>a+(b-a)*Math.max(0,Math.min(1,t));
const progress=(f,start,end)=>Math.max(0,Math.min(1,(f-start)/(end-start)));
const round=(n)=>Math.round(n*1000000)/1000000;
const freeze=(v)=>{if (v && typeof v === 'object') {Object.values(v).forEach(freeze);Object.freeze(v);}return v;};
export function evaluateFrame(shotId, frameIndex, frozenContext) {
  validateScenario(frozenContext);
  assertFrame(frozenContext,shotId,frameIndex);
  const ctx=frozenContext, f=frameIndex;
  const staticOnly=ctx.actions.every(a=>a.kind==='idle');
  const start=ctx.initial_world.actor;
  const drop=ctx.spatial_anchors.find(a=>a.id==='anchor_drop');
  let x=start.x;
  if (!staticOnly) {
    const toward=ctx.initial_world.prop.x-40;
    const end=drop.x-60;
    x=f<72?mix(start.x,toward,progress(f,24,72)):f<114?toward:
      f<168?mix(toward,end,progress(f,114,168)):end;
  }
  const walking=!staticOnly && ((f>=24&&f<72)||(f>=114&&f<168));
  const phase=walking ? 2*Math.PI*(f%24)/24 : 0;
  const reach=!staticOnly?progress(f,72,96)*(1-progress(f,168,196)):0;
  const carrying=!staticOnly && f>=114 && f<196;
  const released=!staticOnly && f>=196;
  const grippingHand=carrying?'left':null;
  const y=start.y;
  const delta={
    leftUpperArm:round(-53*reach),
    leftForearm:round(-26*reach),
    rightUpperArm:round(walking?18*Math.sin(phase):0),
    rightForearm:round(walking?-12*Math.sin(phase):0),
    leftThigh:round(walking?27*Math.sin(phase):0),
    rightThigh:round(walking?-27*Math.sin(phase):0),
    leftShin:round(walking?Math.max(0,-36*Math.sin(phase)):0),
    rightShin:round(walking?Math.max(0,36*Math.sin(phase)):0),
    head:round(!staticOnly&&f>=196?9*Math.sin(Math.PI*progress(f,196,240)):0)
  };
  const state={
    shotId,frameIndex,timeSeconds:round(f/ctx.fps),phase:staticOnly?'idle':
      ctx.actions.find(a=>a.start<=f&&f<a.end)?.kind ?? 'unassigned',
    root:{x:round(x),y:round(y)},
    bones:delta,
    prop:{
      id:ctx.initial_world.prop.id,
      owner:grippingHand?'actor_hero:'+grippingHand:null,
      attachment:grippingHand?'spine_hand_bone':'world',
      world:grippingHand?null:(released?{x:drop.x,y:drop.y}:{x:ctx.initial_world.prop.x,y:ctx.initial_world.prop.y})
    },
    camera:{...ctx.initial_world.camera},
    background:'flat_matte',
    frozenInputFingerprint:ctx.fingerprint ?? 'unverified-input-fingerprint'
  };
  ensure(finite2(state.root) && (!state.prop.world || finite2(state.prop.world)) &&
    Object.values(state.bones).every(Number.isFinite),'NONFINITE_FRAME_STATE');
  return freeze(state);
}

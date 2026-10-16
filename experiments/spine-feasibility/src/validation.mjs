export const FPS = 24;
export const FRAMES = 240;
export function ensure(condition, code, details = '') {
  if (!condition) { const err = new Error(code + (details ? ': ' + details : '')); err.code = code; throw err; }
}
export function finite2(p) {
  return p && Number.isFinite(p.x) && Number.isFinite(p.y);
}
export const overlaps = (a, b) => a.start < b.end && b.start < a.end;

export function validateScenario(ctx) {
  ensure(ctx && typeof ctx === 'object', 'FROZEN_CONTEXT_MISSING');
  ensure(ctx.fps === FPS && ctx.duration_frames === FRAMES && ctx.width === 1280 && ctx.height === 720, 'G1_TIMING_INVALID');
  ensure(/^shot_[a-z0-9_]+$/.test(ctx.shot_id), 'SHOT_ID_INVALID');
  ensure(finite2(ctx.initial_world?.actor) && finite2(ctx.initial_world?.prop) && finite2(ctx.initial_world?.camera), 'INITIAL_WORLD_INVALID');
  ensure(ctx.initial_world.prop.held_by === null, 'INITIAL_GRIP_UNSUPPORTED');
  ensure(Array.isArray(ctx.actions) && Array.isArray(ctx.spatial_anchors), 'CHOREOGRAPHY_MISSING');
  const anchors = new Set();
  for (const anchor of ctx.spatial_anchors) {
    ensure(anchor.id && finite2(anchor) && !anchors.has(anchor.id), 'ANCHOR_INVALID', String(anchor.id));
    anchors.add(anchor.id);
  }
  ensure(Array.isArray(ctx.rig?.required_capabilities), 'RIG_CAPABILITIES_MISSING');
  const ids = new Set();
  for (const action of ctx.actions) {
    ensure(action.id && !ids.has(action.id), 'DUPLICATE_ACTION_ID', action.id);
    ids.add(action.id);
    ensure(Number.isInteger(action.start) && Number.isInteger(action.end) &&
      0 <= action.start && action.start < action.end && action.end <= FRAMES, 'ACTION_BOUNDS_INVALID', action.id);
    ensure(ctx.rig.required_capabilities.includes(action.kind), 'RIG_CAPABILITY_MISSING', action.id);
    if (['walk_to','reach_for','grab','carry_to','place_at','point_at'].includes(action.kind)) {
      ensure(anchors.has(action.target), 'ACTION_TARGET_UNKNOWN', action.id);
    }
    if (['grab','carry_to','place_at'].includes(action.kind)) {
      ensure(action.prop === ctx.initial_world.prop.id, 'PROP_REFERENCE_INVALID', action.id);
      ensure(action.hand === 'left' || action.hand === 'right', 'HAND_REQUIRED', action.id);
    }
  }
  const ordered = [...ctx.actions].sort((a,b) => a.start-b.start || a.end-b.end || a.id.localeCompare(b.id));
  const events = [];
  for (const a of ordered) {
    if (a.kind === 'grab') events.push({frame:a.end,type:'grab',action:a});
    if (a.kind === 'carry_to') events.push({frame:a.start,type:'carry',action:a});
    if (a.kind === 'place_at') {
      events.push({frame:a.start,type:'place_start',action:a});
      events.push({frame:a.end,type:'release',action:a});
    }
  }
  const priority={grab:0,carry:1,place_start:2,release:3};
  events.sort((a,b) => a.frame-b.frame || priority[a.type]-priority[b.type] || a.action.id.localeCompare(b.action.id));
  let owner = null;
  for (const e of events) {
    if (e.type === 'grab') {
      ensure(!owner, 'PROP_ALREADY_OWNED', e.action.id);
      owner = e.action.hand;
    } else if (e.type === 'release') {
      ensure(owner === e.action.hand, 'RELEASE_WITHOUT_GRIP', e.action.id);
      owner = null;
    } else {
      ensure(owner === e.action.hand, 'CARRY_WITHOUT_GRIP', e.action.id);
    }
  }
  ensure(owner === null, 'PROP_NOT_RELEASED');
  for (let i = 0; i < ordered.length; i++) for (let j = i+1; j < ordered.length; j++) {
    const a=ordered[i], b=ordered[j];
    if (!overlaps(a,b)) continue;
    // Grip spans between grab completion and release completion, not simply active action intervals.
    if (['walk_to','carry_to','idle'].includes(a.kind) && ['walk_to','carry_to','idle'].includes(b.kind))
      ensure(false,'MOTION_CHANNEL_CONFLICT',a.id+' / '+b.id);
    if (['reach_for','point_at','grab','place_at'].includes(a.kind) &&
        ['reach_for','point_at','grab','place_at'].includes(b.kind) && a.hand === b.hand)
      ensure(false,'ARM_CHANNEL_CONFLICT',a.id+' / '+b.id);
  }
  const grabs=events.filter(e=>e.type==='grab');
  const releases=events.filter(e=>e.type==='release');
  for (const grip of grabs) {
    const release=releases.find(r=>r.frame>=grip.frame);
    ensure(release, 'GRIP_RELEASE_MISSING', grip.action.id);
    for (const action of ordered) {
      if (action.hand !== grip.action.hand || !['reach_for','point_at','grab'].includes(action.kind)) continue;
      if (action.id === grip.action.id) continue;
      if (overlaps(action,{start:grip.frame,end:release.frame}))
        ensure(false,'OCCUPIED_HAND_CONFLICT',action.id+' / '+grip.action.hand+' / ['+Math.max(action.start,grip.frame)+','+Math.min(action.end,release.frame)+')');
    }
  }
  return true;
}
export function assertFrame(ctx, shotId, frameIndex) {
  ensure(shotId === ctx.shot_id, 'UNKNOWN_SHOT_ID', String(shotId));
  ensure(Number.isInteger(frameIndex) && frameIndex >= 0 && frameIndex < ctx.duration_frames, 'FRAME_INDEX_OUT_OF_BOUNDS', String(frameIndex));
}

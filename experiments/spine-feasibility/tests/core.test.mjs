import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {evaluateFrame} from '../src/frame-evaluator.mjs';
import {validateScenario,sealScenario} from '../src/validation.mjs';
const g1=JSON.parse(fs.readFileSync(new URL('../scenarios/g1-shot.json',import.meta.url),'utf8'));
const idle=JSON.parse(fs.readFileSync(new URL('../scenarios/static-shot.json',import.meta.url),'utf8'));
const reseal=(ctx)=>sealScenario(ctx,createHash('sha256').update(JSON.stringify({start:ctx.initial_world,actions:ctx.actions,anchors:ctx.spatial_anchors,rig:ctx.rig})).digest('hex'));
for (const ctx of [g1,idle]) reseal(ctx);
const clone = (x)=>structuredClone(x);
const hash=(x)=>createHash('sha256').update(JSON.stringify(x)).digest('hex');
test('frozen full-shot and static scenarios validate',()=>{assert.equal(validateScenario(g1),true);assert.equal(validateScenario(idle),true);});
test('reject frame bounds, unknown shot, floating frame',()=>{
  for (const f of [-1,240,1.5,NaN]) assert.throws(()=>evaluateFrame('shot_g1',f,g1),/FRAME_INDEX_OUT_OF_BOUNDS/);
  assert.throws(()=>evaluateFrame('other_shot',0,g1),/UNKNOWN_SHOT_ID/);
});
test('arbitrary evaluation order does not change state hash',()=>{
  const sample=[0,48,97,143,239],reference=Object.fromEntries(sample.map(f=>[f,hash(evaluateFrame('shot_g1',f,g1))]));
  for (const f of [239,97,0,143,48,143,143,0,239,48,97]) assert.equal(hash(evaluateFrame('shot_g1',f,g1)),reference[f]);
});
test('root movement and meaningful actual rig-pose targets are explicit',()=>{
  assert.notEqual(evaluateFrame('shot_g1',48,g1).root.x,evaluateFrame('shot_g1',0,g1).root.x);
  assert.notDeepEqual(evaluateFrame('shot_g1',48,g1).bones,evaluateFrame('shot_g1',0,g1).bones);
  assert.equal(evaluateFrame('shot_g1',143,g1).prop.owner,'actor_hero:left');
  assert.equal(evaluateFrame('shot_g1',239,g1).prop.owner,null);
});
test('C1-MOTION-01 occupied hand blocks reach/point and second grab',()=>{
  for (const kind of ['reach_for','point_at','grab']) {
    const modified=clone(g1);
    modified.actions.push({id:'bad_action',kind,start:130,end:145,hand:'left',target:kind==='point_at'?'anchor_drop':'prop_box',...(kind==='grab'?{prop:'prop_box'}:{})});
    assert.throws(()=>validateScenario(modified),/OCCUPIED_HAND_CONFLICT|PROP_ALREADY_OWNED|ARM_CHANNEL_CONFLICT/);
  }
  const opposite=clone(g1);
  opposite.actions.push({id:'right_point',kind:'point_at',start:130,end:145,hand:'right',target:'anchor_drop'});
  assert.equal(validateScenario(opposite),true);
});
test('C1-FIXTURE-02 static root/prop/camera never translate',()=>{
  for (const f of [0,48,143,239]) {
    const s=evaluateFrame('shot_static',f,idle);
    assert.deepEqual(s.root,{x:250,y:575});
    assert.deepEqual(s.prop.world,{x:580,y:570});
    assert.deepEqual(s.camera,{x:0,y:0});
  }
});
test('missing frozen input and impossible target fail closed',()=>{
  const broken=clone(g1);broken.initial_world.actor.x=Infinity;
  assert.throws(()=>evaluateFrame('shot_g1',0,broken),/INITIAL_WORLD_INVALID/);
  const unknown=clone(g1);unknown.actions[1].target='missing';
  assert.throws(()=>validateScenario(unknown),/ACTION_TARGET_UNKNOWN/);
});

test('missing frozen fingerprint explicitly fails',()=>{
 const broken=clone(g1);delete broken.fingerprint;
 assert.throws(()=>evaluateFrame('shot_g1',0,broken),/FROZEN_INPUT_FINGERPRINT_MISSING/);
});

test('compatible occupied-left carry plus right pointing changes right bone only',()=>{
  const opposite=clone(g1);
  opposite.actions.push({id:'right_point',kind:'point_at',start:130,end:145,hand:'right',target:'anchor_drop'});
  assert.equal(validateScenario(opposite),true);
  reseal(opposite);
  const orig=evaluateFrame('shot_g1',143,g1),newState=evaluateFrame('shot_g1',143,opposite);
  assert.notEqual(newState.bones.rightUpperArm,orig.bones.rightUpperArm);
  assert.equal(newState.bones.leftUpperArm,orig.bones.leftUpperArm);
  assert.equal(newState.prop.owner,'actor_hero:left');
});

test('F01 action removal cannot generate phantom walk or carry',()=>{
 const noWalk=clone(g1); noWalk.actions=noWalk.actions.filter(a=>a.kind!=='walk_to');reseal(noWalk);
 assert.equal(validateScenario(noWalk),true);
 assert.equal(evaluateFrame('shot_g1',48,noWalk).root.x,noWalk.initial_world.actor.x);
 const noGrab=clone(g1);noGrab.actions=noGrab.actions.filter(a=>a.kind!=='grab');
 assert.throws(()=>validateScenario(noGrab),/GRIP_RELEASE_MISSING/);
 const noCarry=clone(g1);noCarry.actions=noCarry.actions.filter(a=>a.kind!=='carry_to');reseal(noCarry);
 assert.equal(validateScenario(noCarry),true);
 assert.equal(evaluateFrame('shot_g1',143,noCarry).root.x,evaluateFrame('shot_g1',113,noCarry).root.x);
});
test('F01 changed approved interval shifts motion, release and identity',()=>{
 const delayed=clone(g1);
 delayed.actions.find(a=>a.kind==='walk_to').start=36;
 reseal(delayed);
 assert.equal(evaluateFrame('shot_g1',30,delayed).root.x,250);
 assert.notEqual(evaluateFrame('shot_g1',48,delayed).root.x,evaluateFrame('shot_g1',48,g1).root.x);
 const shifted=clone(g1);
 shifted.actions.find(a=>a.kind==='place_at').end=208;
 shifted.actions.find(a=>a.kind==='react').start=208;
 reseal(shifted);
 assert.equal(validateScenario(shifted),true);
 assert.notEqual(evaluateFrame('shot_g1',202,shifted).prop.owner,null);
 assert.equal(evaluateFrame('shot_g1',208,shifted).prop.owner,null);
 const stale=clone(g1);stale.actions.find(a=>a.kind==='walk_to').end=64;
 assert.throws(()=>evaluateFrame('shot_g1',48,stale),/FROZEN_SCENARIO_IDENTITY_MISMATCH/);
});
test('F02 identity and target categories are isolated',()=>{
 const collision=clone(g1);collision.spatial_anchors.push({id:'prop_box',x:580,y:570});
 assert.throws(()=>validateScenario(collision),/ANCHOR_ID_COLLISION_OR_INVALID/);
 const wrong=clone(g1);wrong.actions.find(a=>a.kind==='grab').target='anchor_drop';
 assert.throws(()=>validateScenario(wrong),/ACTION_TARGET_TYPE_INVALID/);
 const foreign=clone(g1);foreign.actions.find(a=>a.kind==='carry_to').target='ghost_anchor';
 assert.throws(()=>validateScenario(foreign),/ACTION_TARGET_UNKNOWN_OR_AMBIGUOUS/);
 const nan=clone(g1);nan.spatial_anchors[0].x=Infinity;
 assert.throws(()=>validateScenario(nan),/ANCHOR_ID_COLLISION_OR_INVALID/);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {evaluateFrame} from '../src/frame-evaluator.mjs';
import {validateScenario} from '../src/validation.mjs';
const g1=JSON.parse(fs.readFileSync(new URL('../scenarios/g1-shot.json',import.meta.url),'utf8'));
const idle=JSON.parse(fs.readFileSync(new URL('../scenarios/static-shot.json',import.meta.url),'utf8'));
for (const ctx of [g1,idle]) ctx.fingerprint=createHash('sha256').update(JSON.stringify(ctx)).digest('hex');
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
    assert.throws(()=>validateScenario(modified),/OCCUPIED_HAND_CONFLICT|PROP_ALREADY_OWNED/);
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

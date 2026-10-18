"""C5 focused baseline contract/scheduler tests (not full C5 acceptance evidence)."""
import copy
import json
import math

import pytest

from app.animation import director, motion
from app.animation import service as s

def bones():
    return {name:{"name":name,**({"parent":parent} if parent else {}),"x":x,"y":y,"length":l}
      for name,parent,x,y,l in [
        ("root",None,0,0,0),("hip","root",0,80,50),("chest","hip",0,40,30),("head","chest",0,20,20),
        ("left_upper_arm","chest",-20,-5,30),("left_lower_arm","left_upper_arm",-30,0,25),
        ("left_hand","left_lower_arm",-25,0,5),("right_upper_arm","chest",20,-5,30),
        ("right_lower_arm","right_upper_arm",30,0,25),("right_hand","right_lower_arm",25,0,5),
        ("left_upper_leg","hip",-15,-35,50),("left_lower_leg","left_upper_leg",0,-50,50),
        ("left_foot","left_lower_leg",0,-50,10),("right_upper_leg","hip",15,-35,50),
        ("right_lower_leg","right_upper_leg",0,-50,50),("right_foot","right_lower_leg",0,-50,10),
    ]}

def shot():
    return {"shot_id":"shot_001","duration_frames":240,"actor_ids":["actor_one"],
       "prop_ids":["prop_one"],"location_id":"place_one",
       "spatial_anchors":[{"anchor_id":"anchor_near","x":30,"y":0}],
       "initial_world_state":{"actors":[{"actor_id":"actor_one","x":0,"y":0,"facing":"right"}],
        "props":[{"prop_id":"prop_one","x":-70,"y":105,"held_by":None}]},
       "final_world_state":{"actors":[{"actor_id":"actor_one","x":0,"y":0,"facing":"right"}],
        "props":[{"prop_id":"prop_one","x":-70,"y":105,"held_by":None}]}}

def test_ik_analytic_reaches_target():
    shoulder=(0.,0.);target=(32.,15.)
    alpha,beta,joint=motion.two_bone_ik(shoulder,target,24,22)
    end=(joint[0]+22*math.cos(beta),joint[1]+22*math.sin(beta))
    assert math.dist(end,target)<1e-8
    assert math.isfinite(alpha)

def test_ik_unreachable_fails_closed():
    with pytest.raises(s.DomainError) as exc:
        motion.two_bone_ik((0,0),(500,500),24,22)
    assert exc.value.code=="IK_UNREACHABLE"

def test_pure_idle_frame_is_order_independent():
    one=shot()
    plan={"actions":[]}
    expected={}
    for frame in [0,120,40,239,80,160,120,0,200]:
        value=motion.evaluate(one,plan,{"actor_one":bones()},frame)
        expected.setdefault(frame,s.sha(value))
        assert s.sha(value)==expected[frame]
        assert value["actors"]["actor_one"]["x"]==0
        assert value["props"]["prop_one"]["held_by"] is None
    assert motion.evaluate(one,plan,{"actor_one":bones()},0)==motion.evaluate(one,plan,{"actor_one":bones()},0)

def test_opposing_leg_motion_has_distinct_midpoint_pose():
    one=shot()
    plan={"actions":[{"action_id":"walk_first","shot_id":"shot_001","actor_id":"actor_one",
      "action":"walk_to","start_frame":0,"end_frame":180,"hand":"none","target_id":"anchor_near","prop_id":None}]}
    states=[motion.evaluate(one,plan,{"actor_one":bones()},f) for f in (0,20,60,120,179,239)]
    assert states[0]["actors"]["actor_one"]["x"]==0
    assert states[-1]["actors"]["actor_one"]["x"]==30
    assert states[1]["poses"]["actor_one"]["bones"]["left_upper_leg"]!=states[1]["poses"]["actor_one"]["bones"]["right_upper_leg"]
    assert states[1]["actors"]["actor_one"]["x"]!=states[-1]["actors"]["actor_one"]["x"]
    assert states[-1]["props"]["prop_one"]["x"]==-70

def test_schema_rejects_unknown_action_and_float_boundary():
    base={"schema_version":"animation_plan.v1","artifact_id":"ar_test000",
      "channel_id":"ch_test000","project_id":"pr_test000","created_at":"2026-10-18T12:00:00Z",
      "revision":1,"shot_plan_artifact_id":"ar_shot000","rig_profile_artifact_ids":["ar_rig000"],
      "actions":[{"action_id":"action_one","shot_id":"shot_001","actor_id":"actor_one",
       "action":"teleport","start_frame":0.5,"end_frame":20,"hand":"none","target_id":None,"prop_id":None}]}
    errors=list(director.CHECK.iter_errors(base))
    assert len(errors)>=2

def test_frame_out_of_bounds_is_typed_rejection():
    with pytest.raises(s.DomainError) as exc:
        motion.evaluate(shot(),{"actions":[]},{"actor_one":bones()},240)
    assert exc.value.code=="VALIDATION_FAILED"

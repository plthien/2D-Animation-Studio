"""Focused C5 causal world-state rejection without weakening real Spine acceptance."""
import copy

import pytest

from app.animation import motion, motion_world, service as s
from test_motion_core import shot, bones


def action(name, kind, begin=0, end=24, *, prop="prop_one", target=None, hand="left", actor="actor_one"):
    return {"action_id":name, "shot_id":"shot_001","actor_id":actor,
            "action":kind,"start_frame":begin,"end_frame":end,
            "prop_id":prop,"target_id":target,"hand":hand}


@pytest.mark.parametrize("bad", [
    action("carry_alone","carry_to",0,30,target="anchor_near"),
    action("place_alone","place_at",0,30,target="anchor_near"),
    action("grab_alone","grab",0,30,target="prop_one"),
])
def test_owned_prop_actions_require_prior_contact_and_grab(bad):
    with pytest.raises(s.DomainError) as err:
        motion_world.verify_choreography(shot(), {"actions":[bad]}, {"actor_one":bones()})
    assert err.value.code=="GRIP_OWNERSHIP_CONFLICT"


def test_grab_before_completed_reach_is_rejected():
    actions=[
      action("reach_first","reach_for",0,30,target="prop_one"),
      action("grab_too_soon","grab",20,40,target="prop_one"),
    ]
    with pytest.raises(s.DomainError) as err:
        motion_world.verify_choreography(shot(),{"actions":actions},{"actor_one":bones()})
    assert err.value.code=="GRIP_OWNERSHIP_CONFLICT"


def test_two_actors_cannot_claim_one_prop():
    scene=shot()
    scene["actor_ids"].append("actor_two")
    scene["initial_world_state"]["actors"].append(
        {"actor_id":"actor_two","x":15,"y":0,"facing":"left"})
    scene["final_world_state"]["actors"].append(
        {"actor_id":"actor_two","x":15,"y":0,"facing":"left"})
    actions=[
      action("reach_one","reach_for",0,10,target="prop_one"),
      action("grab_one","grab",10,20,target="prop_one"),
      action("reach_two","reach_for",24,34,target="prop_one",actor="actor_two"),
      action("grab_two","grab",34,44,target="prop_one",actor="actor_two"),
    ]
    with pytest.raises(s.DomainError) as err:
        motion_world.verify_choreography(
            scene,{"actions":actions},{"actor_one":bones(),"actor_two":bones()})
    assert err.value.code=="GRIP_OWNERSHIP_CONFLICT"


def test_world_change_without_causing_actions_rejected():
    scene=shot()
    scene["final_world_state"]["actors"][0]["x"]=17
    with pytest.raises(s.DomainError) as err:
        motion_world.verify_choreography(scene,{"actions":[]},{"actor_one":bones()})
    assert err.value.code=="WORLD_STATE_CONFLICT"


def test_reach_extremely_distant_prop_fails_real_arm_ik():
    scene=shot()
    scene["initial_world_state"]["props"][0].update({"x":5000,"y":5000})
    actions=[action("reach_far","reach_for",0,40,target="prop_one")]
    with pytest.raises(s.DomainError) as err:
        motion.evaluate(scene,{"actions":actions},{"actor_one":bones()},32)
    assert err.value.code=="IK_UNREACHABLE"


def test_unknown_spatial_target_cannot_be_inferred_from_text():
    actions=[action("walk_missing","walk_to",0,50,prop=None,target="fictional_target",hand="none")]
    with pytest.raises(s.DomainError) as err:
        motion.evaluate(shot(),{"actions":actions},{"actor_one":bones()},25)
    assert err.value.code=="VALIDATION_FAILED"


def test_frame_evaluation_never_uses_prior_evaluated_state():
    scene=shot()
    actions=[action("walk","walk_to",0,180,prop=None,target="anchor_near",hand="none")]
    expected={f:s.sha(motion.evaluate(scene,{"actions":actions},{"actor_one":bones()},f))
              for f in range(scene["duration_frames"])}
    for f in [0,120,40,239,80,160,120,0,200]:
        assert s.sha(motion.evaluate(scene,{"actions":actions},{"actor_one":bones()},f))==expected[f]

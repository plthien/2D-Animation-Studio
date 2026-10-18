"""C5 deterministic motion frame evaluator; never reads mutable ticker or previous frame.

This is a STRICT-PARTIAL motion implementation. It rejects unsupported C4 rig
capabilities and never treats a placeholder pose as verified nine-action motion.
"""
from __future__ import annotations

import json
import math
from app.animation import service as s, authoring as a, director, rig_proof

FRAME_RATE=24
TOLERANCE=.001

def smooth(t):
    t=min(1.,max(0.,float(t)))
    return t*t*(3.-2.*t)

def lerp(a,b,t):
    return a+(b-a)*t

def _vector(a,b):
    return (b[0]-a[0],b[1]-a[1])

def _length(x,y):
    return math.hypot(x,y)

def _clamp(x,lo,hi):
    return min(hi,max(lo,x))

def two_bone_ik(shoulder,target,upper_length,lower_length,bend=1):
    """Analytic elbow joint, stable branch, unreachable interactions fail closed."""
    dx,dy=_vector(shoulder,target)
    distance=math.hypot(dx,dy)
    if upper_length<=0 or lower_length<=0 or not math.isfinite(distance):
        s.error("IK_UNSUPPORTED","Invalid geometry",422)
    if distance>upper_length+lower_length+TOLERANCE or distance<abs(upper_length-lower_length)-TOLERANCE:
        s.error("IK_UNREACHABLE","Target outside two-bone reach",422,
                distance=round(distance,4),maximum=round(upper_length+lower_length,4))
    distance=_clamp(distance,max(.000001,abs(upper_length-lower_length)),upper_length+lower_length)
    cos_alpha=_clamp((upper_length*upper_length+distance*distance-lower_length*lower_length)/
                     (2*upper_length*distance),-1.,1.)
    alpha=math.atan2(dy,dx)-bend*math.acos(cos_alpha)
    joint=(shoulder[0]+upper_length*math.cos(alpha),shoulder[1]+upper_length*math.sin(alpha))
    beta=math.atan2(target[1]-joint[1],target[0]-joint[0])
    return alpha,beta,joint

def _skeleton(con,rig):
    rv=con.execute("SELECT * FROM rig_versions WHERE rig_version_id=? AND status='approved'",
                   (rig["rig_version_id"],)).fetchone()
    if not rv:s.error("RIG_CAPABILITY_UNSUPPORTED","Approved source rig missing",422)
    _,metadata,docs=rig_proof._candidate_readonly(con,rv["channel_id"],rv["rig_id"],rv["rig_version_id"])
    path=s.bounded_path(metadata["base"]+"/skeleton.json")
    result=json.loads(path.read_bytes())
    if not result.get("skeleton",{}).get("spine","").startswith("4.2."):
        s.error("LINEAGE_MISMATCH","Spine JSON version is not 4.2",422)
    bones={b["name"]:b for b in result["bones"]}
    required=["root","hip","chest","head","left_upper_arm","left_lower_arm","left_hand",
     "right_upper_arm","right_lower_arm","right_hand",
     "left_upper_leg","left_lower_leg","left_foot","right_upper_leg","right_lower_leg","right_foot"]
    if not set(required).issubset(bones):
        s.error("RIG_CAPABILITY_UNSUPPORTED","Missing required mapped bone",422)
    return bones

def _joint_positions(bones,angles):
    """Evaluate Spine Y-up bind hierarchy with local bone rotation deltas."""
    output={}
    for name,b in bones.items():
        parent=b.get("parent")
        if parent:
            if parent not in output:s.error("RIG_CAPABILITY_UNSUPPORTED","Parent bone order unsupported",422)
            p=output[parent]
            heading=p["heading"]
            x,y=b.get("x",0.),b.get("y",0.)
            cx=p["x"]+x*math.cos(heading)-y*math.sin(heading)
            cy=p["y"]+x*math.sin(heading)+y*math.cos(heading)
        else:
            heading=0.
            cx,cy=b.get("x",0.),b.get("y",0.)
        theta=heading+math.radians(b.get("rotation",0.)+angles.get(name,0.))
        output[name]={"x":cx,"y":cy,"heading":theta}
    return output

def _initial_world(shot):
    actors={row["actor_id"]:dict(row) for row in shot["initial_world_state"]["actors"]}
    props={row["prop_id"]:dict(row) for row in shot["initial_world_state"]["props"]}
    return actors,props

def _coordinate(shot,initial_props,actors,target):
    anchors={a["anchor_id"]:(a["x"],a["y"]) for a in shot["spatial_anchors"]}
    if target in anchors:return anchors[target]
    if target in initial_props:return (initial_props[target]["x"],initial_props[target]["y"])
    if target in actors:return (actors[target]["x"],actors[target]["y"])
    s.error("VALIDATION_FAILED","Undeclared target location: "+str(target),422)

def _actions(plan,shot):
    return sorted((row for row in plan["actions"] if row["shot_id"]==shot["shot_id"]),
                  key=lambda x:(x["start_frame"],x["end_frame"],x["action_id"]))

def evaluate(shot,plan,bones_by_actor,frame):
    """Compute a frame from its complete frozen shot input (stateless, deterministic).

    Unsupported interactions raise instead of snapping a prop or falling back to idle.
    """
    if type(frame)!=int or not 0<=frame<shot["duration_frames"]:
        s.error("VALIDATION_FAILED","Frame outside shot's integer range",422)
    initial_actors,initial_props=_initial_world(shot)
    actors={key:dict(value) for key,value in initial_actors.items()}
    props={key:dict(value) for key,value in initial_props.items()}
    actions=_actions(plan,shot)
    for actor in shot["actor_ids"]:
        if actor not in bones_by_actor:
            s.error("RIG_CAPABILITY_UNSUPPORTED","No current rig for actor",422)
    # Resolve actor root movement strictly from completed/in-progress locomotion.
    for actor in shot["actor_ids"]:
        moves=[act for act in actions if act["actor_id"]==actor
               and act["action"] in ("walk_to","carry_to")]
        pos=(actors[actor]["x"],actors[actor]["y"])
        for act in moves:
            dest=_coordinate(shot,initial_props,actors,act["target_id"])
            if frame<act["start_frame"]:break
            ratio=smooth((min(frame,act["end_frame"])-act["start_frame"])/
                         (act["end_frame"]-act["start_frame"]))
            pos=(lerp(pos[0],dest[0],ratio),lerp(pos[1],dest[1],ratio))
            if frame<act["end_frame"]:break
        actors[actor]["x"],actors[actor]["y"]=pos
    poses={}
    hand_positions={}
    for actor in shot["actor_ids"]:
        bones=bones_by_actor[actor]
        angles={}
        relevant=[x for x in actions if x["actor_id"]==actor and
                  x["start_frame"]<=frame<x["end_frame"]]
        walk=next((x for x in relevant if x["action"] in ("walk_to","carry_to")),None)
        if walk:
            progress=(frame-walk["start_frame"])/max(1,walk["end_frame"]-walk["start_frame"])
            # Bounded complementary swing; root is translated separately, not a whole-image pan.
            phase=math.sin(progress*math.tau*3)
            angles.update({"left_upper_leg":21*phase,"right_upper_leg":-21*phase,
                           "left_lower_leg":-12*max(0,phase),
                           "right_lower_leg":-12*max(0,-phase)})
        for action in relevant:
            typ=action["action"]
            ratio=smooth((frame-action["start_frame"])/(action["end_frame"]-action["start_frame"]))
            if typ=="react":
                pulse=math.sin(math.pi*ratio)
                angles["chest"]=12*pulse
                angles["head"]=-9*pulse
                angles["left_upper_arm"]=17*pulse
            elif typ=="look_at":
                target=_coordinate(shot,initial_props,actors,action["target_id"])
                origin=(actors[actor]["x"],actors[actor]["y"])
                angles["head"]=_clamp(math.degrees(math.atan2(target[1]-origin[1],target[0]-origin[0]))*.2,-25,25)*ratio
            elif typ=="point_at":
                sign=1 if action["hand"]=="left" else -1
                angles[f'{action["hand"]}_upper_arm']=-60*sign*ratio
                angles[f'{action["hand"]}_lower_arm']=-15*sign*ratio
            elif typ in ("reach_for","grab","place_at"):
                target=_coordinate(shot,initial_props,actors,
                                   action["prop_id"] if typ!="place_at" else action["target_id"])
                hand=action["hand"]
                upper=f"{hand}_upper_arm"; lower=f"{hand}_lower_arm"
                wrist=f"{hand}_hand"
                # Calculate from actual frozen bind pivots; never fabricate limb lengths.
                bind=_joint_positions(bones,angles)
                shoulder=(bind[upper]["x"]+actors[actor]["x"],bind[upper]["y"]+actors[actor]["y"])
                elbow=(bind[lower]["x"]+actors[actor]["x"],bind[lower]["y"]+actors[actor]["y"])
                hand0=(bind[wrist]["x"]+actors[actor]["x"],bind[wrist]["y"]+actors[actor]["y"])
                L1=_length(*_vector(shoulder,elbow));L2=_length(*_vector(elbow,hand0))
                desired=(lerp(hand0[0],target[0],ratio),
                         lerp(hand0[1],target[1],ratio))
                alpha,beta,_=two_bone_ik(shoulder,desired,L1,L2,bend=1 if hand=="left" else -1)
                # Relative joint direction for Spine local rotations.
                rest_alpha=math.atan2(elbow[1]-shoulder[1],elbow[0]-shoulder[0])
                rest_beta=math.atan2(hand0[1]-elbow[1],hand0[0]-elbow[0])
                angles[upper]=math.degrees(alpha-rest_alpha)
                angles[lower]=math.degrees(beta-rest_beta)-angles[upper]
                if typ=="grab":angles[wrist]=16*ratio
        joint=_joint_positions(bones,angles)
        for hand in ("left","right"):
            wrist=joint[f"{hand}_hand"]
            hand_positions[f"{actor}:{hand}"]={
                "x":actors[actor]["x"]+wrist["x"],"y":actors[actor]["y"]+wrist["y"]}
        poses[actor]={"root":{"x":actors[actor]["x"],"y":actors[actor]["y"]},
                      "bones":{name:round(val,6) for name,val in sorted(angles.items())}}
    # Only explicit grab establishes ownership. A carry requires prior owned hand.
    for prop_id,initial in initial_props.items():
        history=[x for x in actions if x["prop_id"]==prop_id and
                 x["action"] in ("grab","carry_to","place_at")]
        owner=initial["held_by"]
        xy=(initial["x"],initial["y"])
        for action in history:
            if frame<action["start_frame"]:break
            if action["action"]=="grab":
                candidate=f'{action["actor_id"]}:{action["hand"]}'
                if frame>=action["end_frame"]:
                    owner=candidate
                else:
                    # Until confirmed contact, retain the object's original free-world position.
                    continue
            elif action["action"]=="carry_to":
                if owner!=f'{action["actor_id"]}:{action["hand"]}':
                    s.error("GRIP_OWNERSHIP_CONFLICT","Carry without ownership",422)
            elif action["action"]=="place_at":
                if owner!=f'{action["actor_id"]}:{action["hand"]}':
                    s.error("GRIP_OWNERSHIP_CONFLICT","Place without ownership",422)
                if frame>=action["end_frame"]:
                    owner=None
                    xy=_coordinate(shot,initial_props,actors,action["target_id"])
            if owner and owner in hand_positions:
                h=hand_positions[owner]
                xy=(h["x"],h["y"])
        props[prop_id].update({"held_by":owner,"x":round(xy[0],6),"y":round(xy[1],6)})
    for actor in actors:
        actors[actor]["x"]=round(actors[actor]["x"],6)
        actors[actor]["y"]=round(actors[actor]["y"],6)
    return {"shot_id":shot["shot_id"],"frame":frame,
            "actors":actors,"props":props,"poses":poses,"hands":hand_positions}

def rig_bones_by_actor(con,source):
    return {actor:_skeleton(con,rig) for actor,rig in source["rigs"].items()}

def validate_motion(pid,plan):
    with s.reader() as con:
        ctx=director._context(con,pid)
        if any(a["action"] not in ctx[-2]["rigs"][a["actor_id"]]["capabilities"] for a in plan["actions"]):
            s.error("RIG_CAPABILITY_UNSUPPORTED","Motion contains uncertified rig action",422)
        shot_doc=a.verified_doc(ctx[2])
        rigged=rig_bones_by_actor(con,ctx[-2])
    evidence=[]
    for shot in shot_doc["shots"]:
        samples=[]
        for frame in (0,shot["duration_frames"]//2,shot["duration_frames"]-1):
            state=evaluate(shot,plan,rigged,frame)
            samples.append(s.sha(state))
        evidence.append({"shot_id":shot["shot_id"],"frame_count":shot["duration_frames"],
                         "world_state_sha256":s.sha(samples)})
    return evidence

"""C5 stateless articulated world evaluator. Every frame is recomputed from frozen input."""
from __future__ import annotations
import math
from app.animation import service as s
from app.animation import motion as geom

CONTACT_TOLERANCE_PX=1.5
GROUND_TOLERANCE_PX=2.0

def _progress(frame,act):
    return geom.smooth((min(frame,act["end_frame"])-act["start_frame"])/
                       max(1,act["end_frame"]-act["start_frame"]))

def _point(shot,initial_actors,initial_props,target):
    if target is None:s.error("VALIDATION_FAILED","Target missing",422)
    for a in shot["spatial_anchors"]:
        if a["anchor_id"]==target:return (a["x"],a["y"])
    if target in initial_props:
        q=initial_props[target];return(q["x"],q["y"])
    if target in initial_actors:
        q=initial_actors[target];return(q["x"],q["y"])
    s.error("VALIDATION_FAILED","Undeclared spatial target "+str(target),422)

def _root_at(actions,actor,initial,shot,initial_actors,initial_props,frame):
    origin=(initial["x"],initial["y"])
    for a in actions:
        if a["actor_id"]!=actor or a["action"] not in ("walk_to","carry_to"):continue
        if frame<a["start_frame"]:break
        end=_point(shot,initial_actors,initial_props,a["target_id"])
        f=_progress(frame,a)
        origin=(geom.lerp(origin[0],end[0],f),geom.lerp(origin[1],end[1],f))
        if frame<a["end_frame"]:break
    return origin

def _world_joints(bones,angles,root):
    values=geom._joint_positions(bones,angles)
    return {name:(v["x"]+root[0],v["y"]+root[1]) for name,v in values.items()}

def _arm_to(angles,bones,root,hand,target,weight=1):
    shoulder_name=f"{hand}_upper_arm";elbow_name=f"{hand}_lower_arm";wrist_name=f"{hand}_hand"
    joints=_world_joints(bones,angles,root)
    shoulder=joints[shoulder_name];elbow=joints[elbow_name];wrist=joints[wrist_name]
    desired=(geom.lerp(wrist[0],target[0],weight),geom.lerp(wrist[1],target[1],weight))
    length_upper=math.dist(shoulder,elbow)
    length_lower=math.dist(elbow,wrist)
    if length_upper<2 or length_lower<2:
        s.error("RIG_CAPABILITY_UNSUPPORTED","Arm bones have unusable segment length",422)
    try:
        upper_angle,lower_angle,_=geom.two_bone_ik(
            shoulder,desired,length_upper,length_lower,bend=1 if hand=="left" else -1)
    except s.DomainError as exc:
        if exc.code=="IK_UNREACHABLE":
            s.error("IK_UNREACHABLE","Cannot reach approved spatial target",422,
                    target={"x":desired[0],"y":desired[1]},hand=hand)
        raise
    # Spine bone rotation is local; rotate upper relative to the original parent and
    # lower relative to the resulting upper. Bind segments may be arbitrarily oriented.
    from_angle=math.atan2(elbow[1]-shoulder[1],elbow[0]-shoulder[0])
    from_lower=math.atan2(wrist[1]-elbow[1],wrist[0]-elbow[0])
    diff=math.degrees(upper_angle-from_angle)
    delta_lower=math.degrees(lower_angle-from_lower)-diff
    angles[shoulder_name]=angles.get(shoulder_name,0)+diff
    angles[elbow_name]=angles.get(elbow_name,0)+delta_lower

def _gait(angles,bones,root,initial_root,move,frame,shot,actors,props):
    """Per-foot stance pinning and swing trajectories with two-bone ground IK."""
    ratio=(frame-move["start_frame"])/max(1,move["end_frame"]-move["start_frame"])
    ratio=geom._clamp(ratio,0,1)
    full_target=_point(shot,actors,props,move["target_id"])
    distance=math.dist(initial_root,full_target)
    if distance<1e-5 or ratio==0:return
    rest=_world_joints(bones,{},initial_root)
    default_spacing=70.
    stride_count=max(1,math.ceil(distance/default_spacing))
    for side,offset in (("left",0.),("right",.5)):
        phase=ratio*stride_count+offset
        index=math.floor(phase)
        u=phase-index
        base_foot=rest[f"{side}_foot"]
        stride=(full_target[0]-initial_root[0])/stride_count
        planted=base_foot[0]+index*stride
        if u<.55:
            foot_x=planted; foot_y=base_foot[1]
        else:
            q=(u-.55)/.45
            foot_x=geom.lerp(planted,planted+stride,geom.smooth(q))
            foot_y=base_foot[1]+14.*math.sin(math.pi*q)
        upper_name=f"{side}_upper_leg";lower_name=f"{side}_lower_leg";ankle_name=f"{side}_foot"
        joints=_world_joints(bones,angles,root)
        hip=joints[upper_name];knee=joints[lower_name];ankle=joints[ankle_name]
        length_upper=math.dist(hip,knee);length_lower=math.dist(knee,ankle)
        if length_upper<2 or length_lower<2:
            s.error("RIG_CAPABILITY_UNSUPPORTED","Zero-length leg segment",422)
        try:
            a,b,_=geom.two_bone_ik(hip,(foot_x,foot_y),length_upper,length_lower,
                                   bend=-1 if side=="left" else 1)
        except s.DomainError:
            s.error("IK_UNREACHABLE","Stance foot cannot reach the ground",422,side=side)
        from_upper=math.atan2(knee[1]-hip[1],knee[0]-hip[0])
        from_lower=math.atan2(ankle[1]-knee[1],ankle[0]-knee[0])
        du=math.degrees(a-from_upper);dl=math.degrees(b-from_lower)-du
        angles[upper_name]=angles.get(upper_name,0)+du
        angles[lower_name]=angles.get(lower_name,0)+dl
        angles[ankle_name]=angles.get(ankle_name,0)-du-dl

def _grip_history(actions,prop_id,frame):
    grabbed=None;releasing=None;last_release=None
    for action in actions:
        if action.get("prop_id")!=prop_id or action["start_frame"]>frame:continue
        name=action["action"]
        if name=="grab" and frame>=action["end_frame"]:
            grabbed=action;releasing=None
        if name=="place_at":
            if frame>=action["end_frame"]:
                last_release=action;grabbed=None;releasing=None
            elif grabbed is not None:
                releasing=action
    return grabbed,releasing,last_release

def _hold_owner(actions,actor,hand,frame):
    result=None
    for act in actions:
        if act["actor_id"]!=actor or act.get("hand")!=hand or act["start_frame"]>frame:continue
        if act["action"]=="grab" and frame>=act["end_frame"]:
            result=act
        elif act["action"]=="place_at" and frame>=act["end_frame"]:
            result=None
    return result

def _root_move(actions,actor,frame):
    return next((a for a in actions if a["actor_id"]==actor and
                 a["action"] in ("walk_to","carry_to") and
                 a["start_frame"]<=frame<a["end_frame"]),None)

def evaluate(shot,plan,bones_by_actor,frame):
    if type(frame)!=int or not 0<=frame<shot["duration_frames"]:
        s.error("VALIDATION_FAILED","Frame outside current shot",422)
    acts=sorted((dict(a) for a in plan["actions"] if a["shot_id"]==shot["shot_id"]),
                key=lambda a:(a["start_frame"],a["end_frame"],a["action_id"]))
    initial_actors={a["actor_id"]:dict(a) for a in shot["initial_world_state"]["actors"]}
    initial_props={p["prop_id"]:dict(p) for p in shot["initial_world_state"]["props"]}
    roots={actor:_root_at(acts,actor,row,shot,initial_actors,initial_props,frame)
           for actor,row in initial_actors.items()}
    poses={};hands={}
    for actor,arow in initial_actors.items():
        bones=bones_by_actor.get(actor)
        if not bones:s.error("RIG_CAPABILITY_UNSUPPORTED","Actor has no frozen skeleton",422)
        root=roots[actor];angles={}
        move=_root_move(acts,actor,frame)
        if move:
            beginning=_root_at(acts,actor,arow,shot,initial_actors,initial_props,move["start_frame"])
            _gait(angles,bones,root,beginning,move,frame,shot,initial_actors,initial_props)
        current=[act for act in acts if act["actor_id"]==actor and
                 act["start_frame"]<=frame<act["end_frame"]]
        for action in current:
            typ=action["action"]
            u=_progress(frame,action)
            if typ=="look_at":
                target=_point(shot,initial_actors,initial_props,action["target_id"])
                angles["head"]=geom._clamp(math.degrees(math.atan2(target[1]-root[1],target[0]-root[0]))*.22,-25,25)*u
            elif typ=="react":
                pulse=math.sin(math.pi*u)
                angles.update({"chest":18*pulse,"head":-15*pulse,
                               "left_upper_arm":13*pulse})
            elif typ=="point_at":
                side=action["hand"];angles[f"{side}_upper_arm"]=(50 if side=="right" else -50)*u
                angles[f"{side}_lower_arm"]=12*u
        for hand in ("left","right"):
            active=next((act for act in current if act["hand"]==hand
                         and act["action"] in ("reach_for","grab","place_at")),None)
            owner=_hold_owner(acts,actor,hand,frame)
            if active and active["action"]=="reach_for":
                prop=initial_props[active["prop_id"]]
                dest=(prop["x"],prop["y"])
                _arm_to(angles,bones,root,hand,dest,_progress(frame,active))
            elif active and active["action"]=="grab":
                prop=initial_props[active["prop_id"]]
                _arm_to(angles,bones,root,hand,(prop["x"],prop["y"]),1)
                angles[f"{hand}_hand"]=18*_progress(frame,active)
            elif owner is not None or (active and active["action"]=="place_at"):
                grab=owner if owner is not None else next((a for a in reversed(acts)
                  if a["actor_id"]==actor and a["hand"]==hand and a["action"]=="grab"
                  and a["end_frame"]<=frame),None)
                if grab is None:s.error("GRIP_OWNERSHIP_CONFLICT","Hand has no establishing grab",422)
                prop=initial_props[grab["prop_id"]]
                anchor=(prop["x"],prop["y"])
                root_at_grab=_root_at(acts,actor,arow,shot,initial_actors,initial_props,grab["end_frame"])
                local=(anchor[0]-root_at_grab[0],anchor[1]-root_at_grab[1])
                desired=(root[0]+local[0],root[1]+local[1])
                if active and active["action"]=="place_at":
                    end=_point(shot,initial_actors,initial_props,active["target_id"])
                    p=_progress(frame,active)
                    desired=(geom.lerp(desired[0],end[0],p),geom.lerp(desired[1],end[1],p))
                _arm_to(angles,bones,root,hand,desired,1)
                angles[f"{hand}_hand"]=18
        joints=_world_joints(bones,angles,root)
        for hand in ("left","right"):
            hand_x,hand_y=joints[f"{hand}_hand"]
            hands[f"{actor}:{hand}"]={"x":round(hand_x,6),"y":round(hand_y,6)}
        poses[actor]={"root":{"x":round(root[0],6),"y":round(root[1],6)},
                     "bones":{k:round(v,6) for k,v in sorted(angles.items())}}
    props={}
    for prop_id,row in initial_props.items():
        owner,releasing,last_release=_grip_history(acts,prop_id,frame)
        previous_owner=row.get("held_by")
        if owner is not None:
            who=f'{owner["actor_id"]}:{owner["hand"]}'
            if previous_owner is not None and who!=previous_owner:
                s.error("GRIP_OWNERSHIP_CONFLICT","Two actors claim one prop",422)
            pos=hands[who]
            props[prop_id]={"prop_id":prop_id,"x":pos["x"],"y":pos["y"],"held_by":who}
        elif last_release is not None:
            dest=_point(shot,initial_actors,initial_props,last_release["target_id"])
            props[prop_id]={"prop_id":prop_id,"x":round(dest[0],6),"y":round(dest[1],6),"held_by":None}
        else:
            props[prop_id]=dict(row)
    actors={aid:{**row,"x":round(roots[aid][0],6),"y":round(roots[aid][1],6)}
            for aid,row in initial_actors.items()}
    return {"shot_id":shot["shot_id"],"frame":frame,"actors":actors,
            "props":props,"poses":poses,"hands":hands}

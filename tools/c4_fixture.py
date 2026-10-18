"""Original authored G2 character drawings and separately authored semantic cutouts.

The manual correction masks here are *fixture ground truth*, not outputs of an
AI segmenter or a claim of automatic image understanding. All fourteen cutouts
have real individual alpha pixels, anatomical geometry and reviewed pivots.
"""
from pathlib import Path
from PIL import Image, ImageDraw
import json
import sys

ROLES=("head","torso","pelvis","upper_arm_l","lower_arm_l","hand_l",
       "upper_arm_r","lower_arm_r","hand_r","upper_leg_l","lower_leg_l",
       "foot_l","upper_leg_r","lower_leg_r")
PIVOTS={
 "head":(160,111),"torso":(160,120),"pelvis":(160,219),
 "upper_arm_l":(101,139),"lower_arm_l":(62,194),"hand_l":(32,257),
 "upper_arm_r":(219,139),"lower_arm_r":(258,194),"hand_r":(290,257),
 "upper_leg_l":(128,251),"lower_leg_l":(132,318),"foot_l":(128,367),
 "upper_leg_r":(192,251),"lower_leg_r":(199,318),
}
# Two distinct independently authored characters use different silhouettes.
PALETTE={
 "a":{"skin":"#efb378","top":"#2d7dc4","belt":"#b98036","pants":"#527b53","boots":"#334b36"},
 "b":{"skin":"#b9895d","top":"#d74957","belt":"#472d91","pants":"#dfbd77","boots":"#624694"},
}
LAYERS={
 "lower_leg_l":0,"lower_leg_r":1,"upper_leg_l":2,"upper_leg_r":3,
 "upper_arm_l":4,"lower_arm_l":5,"hand_l":6,"upper_arm_r":7,
 "lower_arm_r":8,"hand_r":9,"torso":10,"pelvis":11,"foot_l":12,"head":13,
}

def make_parts(kind):
    color=PALETTE[kind]
    result={}
    for role in ROLES:
        image=Image.new("RGBA",(320,400),(0,0,0,0))
        g=ImageDraw.Draw(image)
        skin=color["skin"]
        if role=="head":
            g.ellipse((110 if kind=="b" else 115,35 if kind=="b" else 26,210,124),fill=skin)
            if kind=="b":
                g.polygon([(113,71),(131,23),(160,37),(191,13),(211,69)],fill="#7f4bda")
            else:
                g.arc((122,46,200,100),190,342,fill="#523c2e",width=8)
            g.ellipse((137,78,142,83),fill="#252735")
            g.ellipse((177,78,182,83),fill="#252735")
        elif role=="torso":
            if kind=="a":
                g.polygon([(105,116),(214,115),(227,226),(93,226)],fill=color["top"])
            else:
                g.polygon([(110,124),(212,124),(239,222),(84,229)],fill=color["top"])
        elif role=="pelvis":
            g.polygon([(100,215),(221,215),(211,263),(107,263)],fill=color["belt"])
        elif role=="upper_arm_l":
            g.polygon([(109,130),(87,127),(55,194),(77,204)],fill=skin)
        elif role=="lower_arm_l":
            g.polygon([(57,185),(78,199),(42,262),(25,254)],fill=skin)
        elif role=="hand_l":
            g.ellipse((17,249,46,280),fill=skin)
            g.ellipse((11,259,26,269),fill=skin)
        elif role=="upper_arm_r":
            g.polygon([(212,130),(232,127),(267,194),(245,204)],fill=skin)
        elif role=="lower_arm_r":
            g.polygon([(244,196),(263,185),(299,254),(281,263)],fill=skin)
        elif role=="hand_r":
            g.ellipse((275,248,307,281),fill=skin)
            g.ellipse((299,259,313,269),fill=skin)
        elif role=="upper_leg_l":
            g.polygon([(110,249),(153,251),(151,327),(117,326)],fill=color["pants"])
        elif role=="lower_leg_l":
            g.polygon([(119,311),(150,312),(144,371),(118,372)],fill=color["pants"])
        elif role=="foot_l":
            g.polygon([(118,359),(143,360),(150,387),(98,390),(96,382)],fill=color["boots"])
        elif role=="upper_leg_r":
            g.polygon([(167,251),(212,249),(218,326),(179,327)],fill=color["pants"])
        elif role=="lower_leg_r":
            g.polygon([(179,312),(214,310),(220,361),(247,380),(243,391),(200,390),(186,373)],fill=color["pants"])
        result[role]=image
    return result

def draw(kind):
    canvas=Image.new("RGBA",(320,400),(0,0,0,0))
    parts=make_parts(kind)
    for role in sorted(ROLES,key=lambda role:LAYERS[role]):
        canvas.alpha_composite(parts[role])
    return canvas

if __name__=="__main__":
    directory=Path(sys.argv[1]);directory.mkdir(parents=True,exist_ok=True)
    for who in ("a","b"):
        parts=make_parts(who)
        for role,img in parts.items():
            img.save(directory/(who+"-"+role+".png"))
        draw(who).save(directory/("actor-"+who+".png"))
    (directory/"rig-joints.json").write_text(json.dumps({
        "pivots":{role:{"x":point[0]/320,"y":point[1]/400} for role,point in PIVOTS.items()},
        "layers":LAYERS
    },indent=2))

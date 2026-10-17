"""Render a ground-truthed G0 versus C2 screenshot comparison pack.

This provides reproducible human-review evidence, NOT false pixel-equivalence
acceptance when product fields/stages legitimately changed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"artifacts/c2"
BASELINE=ROOT/"docs/qa/evidence/g0/manifest.json"
MATCHES={
    "01-channels-dna-editor-1440x900.png":"channels-1440x900.png",
    "02-create-channel-modal-1440x900.png":"channel-create-modal-1440x900.png",
    "03-projects-1440x900.png":"projects-1440x900.png",
    "04-create-project-modal-1440x900.png":"project-create-modal-1440x900.png",
    "05-studio-pipeline-1440x900.png":"studio-1440x900.png",
    "06-settings-1440x900.png":"settings-1440x900.png",
    "07-jobs-1440x900.png":"jobs-1440x900.png",
    "08-artifacts-1440x900.png":"artifacts-1440x900.png",
    "09-studio-wide-1920x1080.png":"studio-1920x1080.png",
    "10-channels-narrow-768x900.png":"channels-768x900.png",
}

def main():
    manifest=json.loads(BASELINE.read_text(encoding="utf-8"))
    rows=[]
    OUTPUT.mkdir(parents=True,exist_ok=True)
    for shot in manifest["screenshots"]:
        original=Path(shot["file"])
        assert original.name in MATCHES, f"Unknown G0 image: {original}"
        original=ROOT/original
        new=OUTPUT/MATCHES[original.name]
        assert original.is_file() and new.is_file(), f"Missing G0/C2 pair: {new}"
        assert hashlib.sha256(original.read_bytes()).hexdigest()==shot["sha256"],"G0 baseline hash changed"
        with Image.open(original) as baseline, Image.open(new) as updated:
            w,h=shot["viewport"]["width"],shot["viewport"]["height"]
            assert baseline.width==updated.width==w, f"Viewport width mismatch: {new}"
            assert baseline.height>=h and updated.height>=h, f"Viewport height mismatch: {new}"
            old=baseline.convert("RGB").crop((0,0,w,h))
            latest=updated.convert("RGB").crop((0,0,w,h))
            scale=min(1.0,720/w)
            framew,frameh=round(w*scale),round(h*scale)
            side=Image.new("RGB",(framew*2,frameh+40),"#0b1020")
            side.paste(old.resize((framew,frameh)),(0,40))
            side.paste(latest.resize((framew,frameh)),(framew,40))
            draw=ImageDraw.Draw(side)
            draw.text((12,12),"G0 baseline (historical YTB)",fill="white")
            draw.text((framew+12,12),"C2 animation-only Cockpit",fill="white")
            target=OUTPUT/("g0-compare-"+original.stem+".png")
            side.save(target,optimize=True)
            rows.append({
                "baseline":shot["file"],"updated":str(new.relative_to(ROOT)),
                "side_by_side":str(target.relative_to(ROOT)),
                "baseline_sha256_verified":True,
                "viewport":shot["viewport"],
                "expected_changes":"Domain fields, stage labels, future-stage disabled states",
                "visual_review_status":"REQUIRES_HUMAN_REVIEW",
            })
    assert len(rows)==10
    report={"baseline_sha":manifest["baseline_commit"],"pairs":rows,
            "verdict":"Automated pairing and baseline integrity PASS; subjective UI parity requires visual review"}
    (OUTPUT/"g0_c2_comparisons.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("G0/C2 proof: 10 verified side-by-side screenshot pairs created; human layout review pending")
if __name__=="__main__":
    main()

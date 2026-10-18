"""Assemble direct official canvas captures into a visual-review contact sheet.

This preserves source pixels and identifies missing evidence; it never grants a
visual PASS. A human must inspect proportions and articulated limb continuity.
"""
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
import sys

def build(folder:Path):
    labels=("source","joint-overlay","idle","walk","reach","grab")
    images=[]
    for who in ("a","b"):
        row=[]
        for label in labels:
            if label=="source":
                path=folder/f"rig-{who}-source.png"
            elif label=="joint-overlay":
                path=folder/f"rig-{who}-joint-overlay.png"
            else:
                path=folder/f"rig-{who}-{label}.png"
            if not path.is_file():
                raise SystemExit("C4_G2_EVIDENCE_MISSING: "+str(path))
            with Image.open(path) as img:
                img.load()
                row.append(img.convert("RGBA").copy())
        images.append(row)
    cw,ch=280,288
    sheet=Image.new("RGB",(cw*len(labels),ch*2),(19,25,39))
    g=ImageDraw.Draw(sheet)
    for yi,who in enumerate(("a","b")):
        for xi,label in enumerate(labels):
            normalized=ImageOps.contain(images[yi][xi],(cw-16,ch-38))
            left=xi*cw+(cw-normalized.width)//2
            top=yi*ch+30
            bg=Image.new("RGBA",(cw,ch-30),(25,31,47,255))
            bg.alpha_composite(normalized,((cw-normalized.width)//2,0))
            sheet.paste(bg.convert("RGB"),(xi*cw,yi*ch+25))
            g.text((xi*cw+8,yi*ch+7),f"Actor {who.upper()}  |  {label}",fill="#f4f6ff")
    output=folder/"c4-g2-direct-canvas-contact-sheet.png"
    sheet.save(output)
    print("C4 G2 contact sheet generated for manual visual inspection:",output)

if __name__=="__main__":
    build(Path(sys.argv[1]) if len(sys.argv)>1 else Path("artifacts/c4"))

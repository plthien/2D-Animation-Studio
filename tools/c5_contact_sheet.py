"""Make contact sheet from real WebGL canvas captures; never replace actual frames."""
from pathlib import Path
from PIL import Image, ImageDraw

folder=Path("artifacts/c5")
names=["idle-0","walk-40","reach-80","grab-100",
       "carry-140","place-185","react-206","rest-239"]
images=[]
for name in names:
    matches=list(folder.glob("c5-"+name+".png"))
    if len(matches)!=1:
        raise SystemExit("Missing directly rendered C5 WebGL screenshot: "+name)
    with Image.open(matches[0]) as raw:
        raw.load()
        if raw.width<500 or raw.height<300:
            raise SystemExit("Expected actual Spine/Pixi canvas dimensions")
        images.append(raw.convert("RGB").copy())
out=Image.new("RGB",(1280,4*425),(24,28,38))
draw=ImageDraw.Draw(out)
for index,(name,frame) in enumerate(zip(names,images)):
    small=frame.resize((620,349),Image.Resampling.LANCZOS)
    x=(index%2)*640+10
    y=(index//2)*425+22
    out.paste(small,(x,y+26))
    draw.text((x+5,y+5),name+" — directly captured WebGL",fill=(239,243,250))
path=folder/"c5-spine-direct-canvas-contact-sheet.png"
out.save(path)
print("C5 contact sheet:",path, "frames:",len(images))

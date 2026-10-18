"""Generate two independently drawn, transparent test characters (no sampled art)."""
from pathlib import Path
from PIL import Image, ImageDraw
import sys

def draw(kind):
    im=Image.new("RGBA",(320,400),(0,0,0,0))
    g=ImageDraw.Draw(im)
    if kind=="a":
        g.ellipse((105,28,214,112),fill="#efb378")
        g.polygon([(90,115),(220,115),(235,230),(80,230)],fill="#2d7dc4")
        g.polygon([(95,218),(218,218),(211,258),(104,258)],fill="#b98036")
        g.polygon([(83,120),(44,134),(18,268),(38,284),(65,175)],fill="#efb378")
        g.polygon([(230,116),(262,138),(305,272),(288,284),(249,178)],fill="#efb378")
        g.polygon([(111,251),(154,251),(149,352),(141,387),(106,389)],fill="#527b53")
        g.polygon([(170,250),(215,250),(214,350),(241,385),(202,389)],fill="#527b53")
    else:
        g.polygon([(143,10),(160,39),(196,16),(218,75),(106,80)],fill="#7f4bda")
        g.ellipse((110,39,215,140),fill="#b9895d")
        g.polygon([(75,135),(239,139),(219,252),(90,245)],fill="#d74957")
        g.polygon([(80,244),(240,244),(215,276),(102,278)],fill="#472d91")
        g.polygon([(77,145),(45,161),(21,249),(49,272),(82,185)],fill="#b9895d")
        g.polygon([(240,146),(276,162),(301,250),(277,276),(244,185)],fill="#b9895d")
        g.polygon([(103,269),(150,269),(154,360),(130,389),(87,382)],fill="#dfbd77")
        g.polygon([(174,267),(216,267),(223,355),(255,377),(218,390)],fill="#dfbd77")
    return im

if __name__=="__main__":
    directory=Path(sys.argv[1]);directory.mkdir(parents=True,exist_ok=True)
    draw("a").save(directory/"actor-a.png")
    draw("b").save(directory/"actor-b.png")
    replacement=Image.new("RGBA",(50,50),(0,0,0,0))
    ImageDraw.Draw(replacement).ellipse((8,8,41,41),fill="#b9895d")
    replacement.save(directory/"replacement.png")

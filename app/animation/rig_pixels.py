"""C4 pixel-based assisted cutout and Spine 4.2 export.

Assisted extraction is deliberately conservative: plausible image pixels are separated,
but anatomy/occlusion is NOT inferred. Every part requires explicit user review.
"""
from __future__ import annotations

import hashlib
import io
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROLES = (
    "head", "torso", "pelvis",
    "upper_arm_l", "lower_arm_l", "hand_l",
    "upper_arm_r", "lower_arm_r", "hand_r",
    "upper_leg_l", "lower_leg_l", "foot_l",
    "upper_leg_r", "lower_leg_r",
)
# D-004: exactly sixteen mandatory bones. neck is schema-allowed, OPTIONAL.
BONES = (
    "root", "hip", "chest", "head",
    "left_upper_arm", "left_lower_arm", "left_hand",
    "right_upper_arm", "right_lower_arm", "right_hand",
    "left_upper_leg", "left_lower_leg", "left_foot",
    "right_upper_leg", "right_lower_leg", "right_foot",
)
# 14 attachments != 16 bones. Deliberately no fabricated foot_r sprite.
PART_BONE = dict(zip(ROLES, (
    "head", "chest", "hip", "left_upper_arm", "left_lower_arm", "left_hand",
    "right_upper_arm", "right_lower_arm", "right_hand",
    "left_upper_leg", "left_lower_leg", "left_foot",
    "right_upper_leg", "right_lower_leg",
)))
PARENTS = {
    "root": None, "hip": "root", "chest": "hip", "head": "chest",
    "left_upper_arm": "chest", "left_lower_arm": "left_upper_arm", "left_hand": "left_lower_arm",
    "right_upper_arm": "chest", "right_lower_arm": "right_upper_arm", "right_hand": "right_lower_arm",
    "left_upper_leg": "hip", "left_lower_leg": "left_upper_leg", "left_foot": "left_lower_leg",
    "right_upper_leg": "hip", "right_lower_leg": "right_upper_leg", "right_foot": "right_lower_leg",
}
# Rough anatomical priors, NOT detected human joints. Mirror identity is screen-relative.
SEEDS = {
    "head": (.50, .10), "torso": (.50, .31), "pelvis": (.50, .52),
    "upper_arm_l": (.30, .31), "lower_arm_l": (.20, .48), "hand_l": (.16, .62),
    "upper_arm_r": (.70, .31), "lower_arm_r": (.80, .48), "hand_r": (.84, .62),
    "upper_leg_l": (.40, .65), "lower_leg_l": (.38, .80), "foot_l": (.35, .97),
    "upper_leg_r": (.60, .65), "lower_leg_r": (.62, .81),
}
PRESETS = {
    "idle": {},
    "walk": {"left_upper_leg": 23, "right_upper_leg": -23,
             "left_lower_leg": -16, "right_lower_leg": 16,
             "left_upper_arm": -15, "right_upper_arm": 15},
    "reach": {"left_upper_arm": -45, "left_lower_arm": -35, "left_hand": 10},
    "grab": {"left_upper_arm": -50, "left_lower_arm": -40, "left_hand": 35},
    "neutral_return": {},
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False)
    return buffer.getvalue()


def load_rgba(raw: bytes) -> Image.Image:
    with Image.open(io.BytesIO(raw)) as image:
        if image.width * image.height > 32_000_000:
            raise ValueError("Image exceeds supported pixel count")
        image.load()
        return image.convert("RGBA")


def foreground(image: Image.Image) -> tuple[Image.Image, bool]:
    """Use authored alpha if present; otherwise remove connected near-corner BG.

    RGB photographs are underdetermined. The uncertain flag stays true, and
    every first-pass role still needs review (even for transparent inputs).
    """
    alpha = image.getchannel("A")
    if alpha.getextrema()[0] < 250:
        return alpha.point(lambda x: 255 if x >= 16 else 0), False
    # Corner flood-fill uses actual pixel similarity, never a rectangular body.
    rgb = image.convert("RGB")
    bg = Image.new("L", rgb.size, 0)
    corners = [(0, 0), (rgb.width-1, 0), (0, rgb.height-1), (rgb.width-1, rgb.height-1)]
    corner_colors = [rgb.getpixel(p) for p in corners]
    if any(sum(abs(a-b) for a, b in zip(corner_colors[0], c)) > 50 for c in corner_colors[1:]):
        return Image.new("L", rgb.size, 0), True
    mark = (1, 2, 3)
    for point in corners:
        ImageDraw.floodfill(rgb, point, mark, thresh=22)
    colors = rgb.getdata()
    bg.putdata([0 if pixel == mark else 255 for pixel in colors])
    return bg, True


def extract(image: Image.Image) -> tuple[dict[str, dict], dict[str, Image.Image]]:
    """Voronoi partition OF detected foreground pixels; all labels unreviewed.

    Computed at <=256px for bounded memory/latency, rasterized back at source
    resolution and intersected with the original foreground alpha.
    """
    fg, uncertain_bg = foreground(image)
    bbox = fg.getbbox()
    if bbox is None:
        # RGB photographs with complicated backgrounds cannot be segmented
        # reliably. Persist explicit empty masks instead of inventing anatomy;
        # the editor then requires all missing roles to be replaced manually.
        masks = {role: Image.new("L", image.size, 0) for role in ROLES}
        parts = {
            role: {"role": role, "layer": layer, "reviewed": False,
                   "provenance": "no_automatic_extraction",
                   "confidence": 0.0, "uncertain": True, "occluded": True,
                   "reason": "FOREGROUND_NOT_RECOVERABLE_MANUAL_REPLACEMENT_REQUIRED",
                   "pivot": {"x": 0.5, "y": 0.5,
                             "coordinate_system": "normalized_top_left"}}
            for layer, role in enumerate(ROLES)
        }
        return parts, masks
    x0, y0, x1, y1 = bbox
    if (x1-x0) * (y1-y0) < 64:
        raise ValueError("Insufficient foreground pixels")
    scale = min(1., 256 / max(image.size))
    w, h = max(1, round(image.width * scale)), max(1, round(image.height * scale))
    tiny = fg.resize((w, h), Image.Resampling.NEAREST)
    seeds = {
        name: ((x0 + fx * (x1-x0)) * w / image.width,
               (y0 + fy * (y1-y0)) * h / image.height)
        for name, (fx, fy) in SEEDS.items()
    }
    assigned = {role: Image.new("L", (w, h), 0) for role in ROLES}
    inp = tiny.load()
    out = {name: mask.load() for name, mask in assigned.items()}
    for yy in range(h):
        for xx in range(w):
            if inp[xx, yy] < 16:
                continue
            winner = min(ROLES, key=lambda key: (
                ((xx-seeds[key][0]) / max(1, (x1-x0)*w/image.width))**2 * 2.2
                + ((yy-seeds[key][1]) / max(1, (y1-y0)*h/image.height))**2
            ))
            out[winner][xx, yy] = 255
    masks = {role: ImageChops.multiply(mask.resize(image.size, Image.Resampling.NEAREST), fg)
             for role, mask in assigned.items()}
    parts = {}
    for layer, role in enumerate(ROLES):
        m = masks[role]
        bounds = m.getbbox()
        parts[role] = {
            "role": role, "layer": layer, "reviewed": False,
            "provenance": "assisted_pixel_partition",
            "confidence": 0.20 if uncertain_bg else 0.35,
            "uncertain": True,
            "occluded": bounds is None,
            "reason": ("NO_FOREGROUND_REGION" if bounds is None else
                       "RGB_BACKGROUND_UNCERTAIN" if uncertain_bg else
                       "ANATOMY_UNVERIFIED"),
            "pivot": {"x": 0.5, "y": 0.5, "coordinate_system": "normalized_top_left"},
        }
    return parts, masks


def sprite(image: Image.Image, mask: Image.Image) -> Image.Image:
    if mask.mode != "L" or mask.size != image.size:
        raise ValueError("Mask must be L image with exact source dimensions")
    output = image.copy().convert("RGBA")
    output.putalpha(ImageChops.multiply(image.getchannel("A"), mask))
    return output


def apply_strokes(mask: Image.Image, strokes: list[dict]) -> Image.Image:
    if len(strokes) > 2048:
        raise ValueError("Too many strokes")
    out = mask.copy().convert("L")
    brush = ImageDraw.Draw(out)
    for stroke in strokes:
        x, y, radius, mode = stroke["x"], stroke["y"], stroke["radius"], stroke["mode"]
        if (not all(isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v <= 1
                    for v in (x, y, radius)) or radius <= 0 or mode not in ("paint", "erase")):
            raise ValueError("Invalid normalized brush stroke")
        cx, cy, rr = x * out.width, y * out.height, radius * max(out.size)
        brush.ellipse((cx-rr, cy-rr, cx+rr, cy+rr), fill=255 if mode == "paint" else 0)
    return out


def bounds_for_sprite(raw: bytes) -> tuple[int, int, int, int]:
    with Image.open(io.BytesIO(raw)) as im:
        im.load()
        if im.mode != "RGBA":
            raise ValueError("Sprite must be RGBA PNG")
        box = im.getchannel("A").getbbox()
        if box is None:
            raise ValueError("Empty transparent sprite")
        return box


def spine_package(part_pngs: dict[str, bytes], parts: dict[str, dict]) -> tuple[bytes, bytes, bytes]:
    """Generate real Spine 4.2 JSON, Spine text atlas and a non-overlapping atlas page."""
    if set(part_pngs) != set(ROLES) or set(parts) != set(ROLES):
        raise ValueError("All fourteen semantic sprites are required")
    cropped = {}
    for role in ROLES:
        raw = part_pngs[role]
        with Image.open(io.BytesIO(raw)) as im:
            im.load()
            if im.mode != "RGBA":
                raise ValueError(role + ": sprite must be RGBA")
            box = im.getchannel("A").getbbox()
            if box is None:
                raise ValueError(role + ": blank sprite")
            cropped[role] = (im.crop(box).copy(), box, im.size)
    page_width = 2048
    x, y, row_height = 2, 2, 0
    regions = {}
    for role in ROLES:
        crop, box, original_size = cropped[role]
        if crop.width > page_width-4 or crop.height > 4092:
            raise ValueError(role + ": sprite too large for atlas")
        if x + crop.width + 2 > page_width:
            x, y, row_height = 2, y + row_height + 2, 0
        if y + crop.height + 2 > 4096:
            raise ValueError("Atlas exceeds maximum page; reduce source image resolution")
        regions[role] = (x, y, crop.width, crop.height)
        x += crop.width + 2
        row_height = max(row_height, crop.height)
    height = max(8, 2 ** math.ceil(math.log2(y + row_height + 2)))
    page = Image.new("RGBA", (page_width, height), (0, 0, 0, 0))
    atlas_lines = ["page.png", f"size: {page_width},{height}",
                   "filter: Linear,Linear", "pma: false", "repeat: none"]
    for role in ROLES:
        crop, _, _ = cropped[role]
        px, py, width, h = regions[role]
        page.alpha_composite(crop, (px, py))
        atlas_lines += [role, f"bounds: {px},{py},{width},{h}",
                        f"offsets: 0,0,{width},{h}"]
    atlas_bytes = ("\n".join(atlas_lines) + "\n").encode("utf-8")
    # World points are source pixel coordinates (top-left); convert to Y-up Spine.
    joints = {}
    for role in ROLES:
        crop, (x0, y0, x1, y1), _ = cropped[role]
        p = parts[role]["pivot"]
        if not (0 <= p["x"] <= 1 and 0 <= p["y"] <= 1):
            raise ValueError(role + ": pivot outside [0,1]")
        joints[PART_BONE[role]] = (x0 + (x1-x0)*p["x"],
                                  y0 + (y1-y0)*p["y"])
    hip = joints["hip"]
    full_h = max(info[2][1] for info in cropped.values())
    joints["root"] = (hip[0], full_h)
    joints["right_foot"] = (
        joints["right_lower_leg"][0],
        max(joints["right_lower_leg"][1], full_h*.95),
    )
    children = {role: [] for role in BONES}
    for bone, parent in PARENTS.items():
        if parent:
            children[parent].append(bone)
    bones = []
    for role in BONES:
        parent = PARENTS[role]
        px, py = joints[parent] if parent else joints[role]
        cx, cy = joints[role]
        length = 0.
        if children[role]:
            length = math.dist((cx, cy), joints[children[role][0]])
        entry = {
            "name": role, "x": round(cx-px, 3), "y": round(py-cy, 3),
            "length": round(length, 3),
        }
        if parent:
            entry["parent"] = parent
        bones.append(entry)
    # Region x/y are offsets from actual parent bone pivot, not from source origin.
    slots, attachments = [], {}
    for role in sorted(ROLES, key=lambda key: parts[key]["layer"]):
        _, (x0, y0, x1, y1), _ = cropped[role]
        width, h = x1-x0, y1-y0
        cx, cy = (x0+x1)/2, (y0+y1)/2
        bone = PART_BONE[role]
        bx, by = joints[bone]
        slots.append({"name": role, "bone": bone, "attachment": role})
        attachments[role] = {
            role: {"type": "region", "path": role,
                   "x": round(cx-bx, 3), "y": round(by-cy, 3),
                   "width": width, "height": h}
        }
    import json
    skeleton = {
        "skeleton": {"hash": digest(atlas_bytes)[:16], "spine": "4.2.0",
                     "x": 0, "y": 0, "width": max(i[2][0] for i in cropped.values()),
                     "height": full_h, "images": ""},
        "bones": bones, "slots": slots,
        "skins": [{"name": "default", "attachments": attachments}],
        "animations": {},
    }
    skeleton_bytes = json.dumps(skeleton, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return skeleton_bytes, atlas_bytes, png_bytes(page)

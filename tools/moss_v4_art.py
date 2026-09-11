"""Pocket Moss v4 generator: every pose is composed from one shared head/ear/body/tail model.

The JSON under assets/pocket_moss/v4 is the hash-bound source of truth; this script produced it.
Edit here, then regenerate into a NEW version directory (never rewrite a live, hash-bound root):
    python3 tools/moss_v4_art.py assets/pocket_moss/v5
"""
import json, sys
from pathlib import Path

PAL = {
    ".": (0, 0, 0), "b": (150, 70, 35), "s": (200, 100, 35), "h": (245, 155, 65),
    "l": (255, 200, 120), "c": (255, 240, 205), "e": (0, 0, 0), "p": (255, 85, 150),
    "k": (0, 190, 190), "g": (255, 215, 40), "z": (120, 175, 255),
}

HEAD = [  # y = 1..8, ears drawn separately
    ".....hhhhhh.....",
    "...hllllhhhhs...",
    "....hlllhhhs....",
    "....hhhhhhhs....",
    "....hhhhhhhs....",
    "....hhcccchs....",
    "....hcceeccs....",
    "....shcppchs....",
]
EAR_L = [(2, 3), (3, 3), (1, 4), (2, 4), (3, 4), (1, 5), (2, 5), (3, 5), (1, 6), (2, 6), (3, 6), (2, 7), (3, 7)]
EAR_R = [(15 - x, y) for x, y in EAR_L]
EYES = {
    "open": [(5, 4, "e"), (10, 4, "e")],
    "closed": [(5, 4, "e"), (6, 4, "e"), (9, 4, "e"), (10, 4, "e")],
    "left": [(4, 4, "e"), (9, 4, "e")],
    "right": [(6, 4, "e"), (11, 4, "e")],
    "happy": [(4, 5, "e"), (5, 4, "e"), (6, 5, "e"), (9, 5, "e"), (10, 4, "e"), (11, 5, "e")],
    "wink": [(5, 4, "e"), (9, 4, "e"), (10, 4, "e")],
}
MOUTH = {
    "tongue": [],
    "closed": [(7, 8, "c"), (8, 8, "c")],
    "long": [(7, 9, "p"), (8, 9, "p")],
    "yawn": [(6, 8, "e"), (7, 8, "p"), (8, 8, "p"), (9, 8, "e"), (7, 7, "e"), (8, 7, "e")],
}
BLUSH = [(4, 6, "p"), (11, 6, "p")]

BODY = {  # y = 9..14
    "sit": [
        "....skkggkks....",
        "....hhcccchs....",
        "...hhhcccchss...",
        "..hhhhhcchhsss..",
        "..hhhhsccshhss..",
        "...cc.cc.cc.cc..",
    ],
    "squash": [
        "................",
        "....skkggkks....",
        "...hhhcccchss...",
        "..hhhhhcchhsss..",
        ".hhhhhsccshhsss.",
        "..cc..cc.cc..cc.",
    ],
    "hop": [
        "....skkggkks....",
        "....hhcccchs....",
        "...hhhcccchss...",
        "...hhhhcchhss...",
        "....cc....cc....",
        "................",
    ],
    "loaf": [
        "................",
        "................",
        ".hhh........sss.",
        ".hhhhhhcchhssss.",
        "..hccch..hcccs..",
        "................",
    ],
}
TAIL = {
    "up": [(14, 10, "h"), (14, 11, "h"), (14, 12, "h")],
    "right": [(14, 12, "h"), (15 - 1, 11, "s"), (13, 11, "h")],
    "left_hi": [(13, 9, "h"), (13, 10, "h"), (14, 11, "h"), (14, 12, "h")],
    "low": [(14, 13, "h"), (14, 12, "s")],
    "none": [],
}

HEART_S = [".p.p.", ".ppp.", "..p.."]
HEART_B = ["pp.pp", "ppppp", ".ppp.", "..p.."]
SPARKLE = ["p...p", ".....", "..p..", "p...p"]
Z_SMALL = ["zzz", "..z", ".z.", "zzz"]
Z_BIG = ["zzzz", "..z.", ".z..", "zzzz"]


def canvas():
    return [["."] * 16 for _ in range(16)]


def put(g, x, y, k):
    if 0 <= x < 16 and 0 <= y < 16 and k != ".":
        g[y][x] = k


def blit(g, rows, ox, oy):
    for y, row in enumerate(rows):
        for x, k in enumerate(row):
            put(g, x + ox, y + oy, k)


def dog(body="sit", tail="up", eyes="open", mouth="tongue", hx=0, hy=0, bx=0, by=0,
        ear_l=(0, 0), ear_r=(0, 0), blush=False, overlays=(), squash_head=False):
    g = canvas()
    blit(g, BODY[body], bx, 9 + by)
    for x, y, k in TAIL[tail]:
        put(g, x + bx, y + by, k)
    head = [r for r in HEAD]
    if squash_head:  # drop the forehead highlight row: head reads 1px flatter
        head = head[:1] + head[2:]
    top = 1 + hy + (1 if squash_head else 0)
    blit(g, head, hx, top)
    fy = hy - (0 if not squash_head else 0)
    for (x, y) in EAR_L:
        put(g, x + hx + ear_l[0], y + hy + ear_l[1], "b")
    for (x, y) in EAR_R:
        put(g, x + hx + ear_r[0], y + hy + ear_r[1], "b")
    for x, y, k in EYES[eyes] + MOUTH[mouth] + (BLUSH if blush else []):
        put(g, x + hx, y + fy, k)
    for rows, ox, oy in overlays:
        blit(g, rows, ox, oy)
    return ["".join(r) for r in g]


SPRITES = {
    "idle": dog(),
    "blink": dog(eyes="closed"),
    "perk": dog(ear_l=(0, -1), ear_r=(0, -1), mouth="closed"),
    "look_left": dog(hx=-1, eyes="left", ear_r=(0, -1), tail="right"),
    "look_right": dog(hx=1, eyes="right", ear_l=(0, -1), tail="left_hi"),
    "dance_crouch": dog(body="squash", hy=1, eyes="happy", ear_l=(0, 1), ear_r=(0, 1), tail="low", by=0),
    "dance_left": dog(bx=0, hx=-1, ear_r=(1, -1), tail="left_hi", eyes="happy"),
    "dance_right": dog(bx=0, hx=1, ear_l=(-1, -1), tail="right", eyes="happy"),
    "dance_hop": dog(body="hop", hy=-1, by=-1, ear_l=(0, -1), ear_r=(0, -1), tail="left_hi"),
    "dance_land": dog(body="squash", hy=1, ear_l=(0, 1), ear_r=(0, 1), eyes="closed", tail="low"),
    "wag_high": dog(eyes="happy", tail="left_hi", ear_l=(0, -1), ear_r=(0, -1)),
    "wag_low": dog(eyes="happy", tail="right"),
    "pet_lean": dog(hx=-1, hy=1, eyes="closed", ear_l=(0, 1), ear_r=(0, -1), mouth="closed"),
    "pet_squish": dog(hy=1, squash_head=True, eyes="closed", blush=True, ear_l=(-1, 0), ear_r=(1, 0), mouth="closed"),
    "kiss_lean": dog(hx=-1, hy=1, eyes="happy", mouth="long", overlays=[(HEART_S, 10, 1)]),
    "kiss_big": dog(eyes="happy", overlays=[(HEART_B, 10, 0)], tail="left_hi"),
    "kiss_pop": dog(eyes="wink", overlays=[(SPARKLE, 10, 0)], tail="right"),
    "loaf": dog(body="loaf", hy=3, tail="none", mouth="closed"),
    "loaf_blink": dog(body="loaf", hy=3, tail="none", mouth="closed", eyes="closed"),
    "sleep_a": dog(body="loaf", hy=3, tail="none", mouth="closed", eyes="closed", ear_l=(0, 1), ear_r=(0, 1),
                   overlays=[(Z_SMALL, 12, 2)]),
    "sleep_b": dog(body="loaf", hy=3, tail="none", mouth="closed", eyes="closed", ear_l=(0, 1), ear_r=(0, 1),
                   overlays=[(Z_BIG, 11, 0)]),
    "yawn": dog(body="loaf", hy=3, tail="none", eyes="closed", mouth="yawn", ear_l=(0, -1), ear_r=(0, -1)),
}

ANIMS = {
    "look": [("idle", 4, "idle"), ("blink", 2, "blink"), ("idle", 5, "idle"), ("look_left", 8, "look"),
             ("look_right", 8, "look"), ("idle", 4, "settle")],
    "idle-look": [("idle", 20, "idle"), ("blink", 2, "blink"), ("idle", 10, "idle"), ("look_left", 5, "look"),
                  ("idle", 20, "settle")],
    "loaf": [("perk", 3, "notice"), ("loaf", 12, "rest"), ("loaf_blink", 2, "rest"), ("loaf", 12, "rest"),
             ("idle", 4, "settle")],
    "sleep-wake": [("loaf", 5, "settle"), ("sleep_a", 12, "sleep"), ("sleep_b", 12, "sleep"),
                   ("sleep_a", 12, "sleep"), ("yawn", 6, "wake"), ("blink", 2, "wake"), ("idle", 5, "settle")],
    "pet": [("perk", 3, "notice"), ("pet_lean", 4, "lean"), ("pet_squish", 7, "squish"),
            ("wag_high", 3, "wag_high"), ("wag_low", 3, "wag_low"), ("wag_high", 3, "wag_high"),
            ("wag_low", 3, "wag_low"), ("idle", 5, "settle")],
    "dance": [("dance_crouch", 3, "anticipate"), ("dance_left", 3, "step_left"), ("dance_right", 3, "step_right"),
              ("dance_left", 3, "step_left"), ("dance_right", 3, "step_right"), ("dance_crouch", 2, "anticipate"),
              ("dance_hop", 4, "hop"), ("dance_land", 3, "land"), ("wag_high", 3, "wag_high"),
              ("wag_low", 3, "wag_low"), ("wag_high", 3, "wag_high"), ("idle", 4, "settle")],
    "kisses": [("perk", 3, "notice"), ("kiss_lean", 5, "kiss_small"), ("kiss_big", 7, "kiss_big"),
               ("kiss_pop", 4, "pop"), ("wag_high", 3, "happy"), ("wag_low", 3, "happy"), ("idle", 4, "settle")],
}


def write(out: Path, version="v4"):
    (out / "sprites").mkdir(parents=True, exist_ok=True)
    (out / "animations").mkdir(parents=True, exist_ok=True)
    for name, rows in SPRITES.items():
        assert len(rows) == 16 and all(len(r) == 16 for r in rows), name
        used = sorted({k for r in rows for k in r} | {"."})
        doc = {"schema": "openditoo.pixel-sprite.v1", "id": f"moss.{version}.{name}", "width": 16, "height": 16,
               "palette": {k: list(PAL[k]) for k in used}, "rows": rows,
               "meta": {"anchor": [8, 14], "mirroring": None, "tags": ["moss", version, name]}}
        (out / "sprites" / f"{name}.json").write_text(json.dumps(doc, indent=2) + "\n")
    for name, seq in ANIMS.items():
        doc = {"schema": "openditoo.pixel-animation.v1", "id": f"moss.{version}.{name}", "canvas": [16, 16],
               "loop": name == "idle-look",
               "sequence": [{"sprite": f"../sprites/{s}.json", "hold_acks": h, "phase": p} for s, h, p in seq]}
        (out / "animations" / f"{name}.json").write_text(json.dumps(doc, indent=2) + "\n")


if __name__ == "__main__":
    write(Path(sys.argv[1]))

#!/usr/bin/env python3
"""Generates src/gen/assets.c/.h: tiles, metatiles, palettes, sprites, map and text.

All art is defined here (ASCII pixels or small drawing routines) so the whole
game builds from source. Pixels are colour indices 0-3 into a GBC palette.
"""
import sys, textwrap
import numpy as np

OUT = sys.argv[1] if len(sys.argv) > 1 else "src/gen"
TILE_BASE = 128          # BG tiles live at 128..255, font at 0..95
SOLID, DOOR, GRASS = 1, 2, 4

# ---------------------------------------------------------------- palettes
def rgb(h):
    r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)

P_GRASS, P_PATH, P_WATER, P_RED, P_BLUE, P_FLOWER, P_WOOD, P_UI = range(8)
BG_PALS = [
    ["#a8e070", "#70c048", "#388830", "#184818"],  # grass / trees
    ["#f0e0a8", "#d8b870", "#a07840", "#a8e070"],  # path (3 = grass, for ragged edges)
    ["#c8f0f8", "#60a8f0", "#885028", "#301808"],  # water + ship + bridge
    ["#f8f0e0", "#e86040", "#983020", "#281818"],  # red-roof house
    ["#f8f0e0", "#6890c8", "#385890", "#181828"],  # slate-roof house
    ["#a8e070", "#70c048", "#f8d030", "#e84858"],  # flowers
    ["#a8e070", "#e0b060", "#a06830", "#301808"],  # wood on grass
    ["#f8f8f8", "#b0b0a8", "#686870", "#181820"],  # UI + quay stone
]
OBJ_PALS = [
    ["#000000", "#f8d0a0", "#7038a8", "#201828"],  # player (purple & gold county)
    ["#000000", "#f8d0a0", "#d04040", "#201828"],  # NPC
]

# ---------------------------------------------------------------- helpers
def art(rows, w=16):
    for r in rows:
        assert len(r) == w, (len(r), r)
    return np.array([[0 if c == "." else int(c) for c in r] for r in rows], dtype=np.uint8)

def rep(pat8):
    return np.tile(art(pat8, 8), (2, 2))

tiles, tile_ix = [], {}
def add_tile(px):
    key = px.tobytes()
    if key not in tile_ix:
        tile_ix[key] = len(tiles)
        tiles.append(px.copy())
    return TILE_BASE + tile_ix[key]

def to2bpp(px):
    out = []
    for row in px:
        lo = hi = 0
        for c in row:
            lo = (lo << 1) | (int(c) & 1)
            hi = (hi << 1) | (int(c) >> 1)
        out += [lo, hi]
    return out

metatiles, mt_char, mt_ix, mt_src = [], {}, {}, {}
def mt_id(px, pal, flags=0):
    t = [add_tile(px[y:y + 8, x:x + 8]) for y in (0, 8) for x in (0, 8)]
    pals = pal if isinstance(pal, list) else [pal] * 4
    key = (tuple(t), tuple(pals), flags)
    if key not in mt_ix:
        mt_ix[key] = len(metatiles)
        metatiles.append((t, pals, flags))
    return mt_ix[key]
def add_mt(ch, px, pal, flags=0):
    mt_char[ch] = mt_id(px, pal, flags)
    mt_src[ch] = (px, pal, flags)

# ---------------------------------------------------------------- terrain art
grass = rep(["........", "..1.....", ".1.1....", "........",
             "........", "......1.", ".....1.1", "........"])
tall = rep(["...2....", ".2.2..2.", ".212.12.", "2212.122",
            "...2....", ".2...2.2", ".21.212.", "221.2122"])
path = rep(["........", "....1...", "........", ".1......",
            "........", "......1.", "..1.....", "........"])
water = rep(["11111111", "11100111", "10011001", "11111111",
             "11111111", "01111110", "10011001", "11111111"])
flower = rep(["........", "..3.....", ".323....", "..3..1..",
              ".....3..", "....323.", ".1...3..", "........"])
tree = art([
    "....33333333....", "..331111111133..", ".31101111111113.", "3110011112111113",
    "3100111111112113", "3101111211111123", "3111112111111223", "3111111111212223",
    "3211211111122223", "3221111211222223", ".32221122222223.", "..332222222233..",
    "....33322333....", ".....332233.....", "....33222233....", "...1333333331...",
])
sign = art([
    "................", "................", ".33333333333333.", ".31111111111113.",
    ".31333133313313.", ".31111111111113.", ".31331333133113.", ".31111111111113.",
    ".32222222222223.", ".33333333333333.", "......3113......", "......3113......",
    "......3113......", "......3223......", ".....333333.....", "................",
])

quay = np.full((16, 16), 1, np.uint8)          # cut stone, UI palette
quay[::8, :] = 2
for y in range(16):
    quay[y, (4 if (y // 8) % 2 else 12)] = 2
quay[:, 0] = 3; quay[:, 1] = 2; quay[:, 15] = 2

bridge = np.full((16, 16), 2, np.uint8)        # planks over the river
bridge[:, ::4] = 3
bridge[0:2, :] = 3; bridge[14:16, :] = 3; bridge[2, :] = 0; bridge[13, :] = 0

def house():
    h = np.zeros((32, 48), np.uint8)
    h[0:18, :] = 1                              # slate roof, staggered courses
    for y in range(18):
        if y % 4 == 3:
            h[y, :] = 2
        else:
            h[y, (np.arange(48) + (y // 4) % 2 * 4) % 8 == 0] = 2
    h[0, :] = 3; h[17, :] = 3; h[0:18, 0] = 3; h[0:18, 47] = 3
    h[1, 1:47] = 0                              # ridge highlight
    h[16, 1:47] = 2                             # eave shadow
    h[2:9, 35:43] = 3; h[3:8, 36:42] = 0        # chimney
    h[4:7, 37:41] = 3; h[5, 38:40] = 2
    h[18:32, 0:2] = 3; h[18:32, 46:48] = 3; h[31, :] = 3     # whitewashed walls
    h[18, 2:46] = 1                             # shadow under the eaves
    for x0 in (5, 33):                          # four-pane windows with sills
        h[20:28, x0:x0 + 10] = 3
        h[21:27, x0 + 1:x0 + 9] = 1
        h[21:27, x0 + 4:x0 + 6] = 0; h[23:25, x0 + 1:x0 + 9] = 0
        h[21, x0 + 1] = 0; h[21, x0 + 6] = 0    # glint
        h[28, x0 - 1:x0 + 11] = 3; h[29, x0:x0 + 10] = 2
    h[19:32, 18:30] = 3                         # panelled door
    h[20:31, 19:29] = 2
    h[21:25, 20:23] = 1; h[21:25, 25:28] = 1; h[26:30, 20:23] = 1; h[26:30, 25:28] = 1
    h[25, 27] = 0
    h[31, 18:30] = 0; h[30, 18:30] = 3          # doorstep
    return h

stone = np.full((16, 16), 1, np.uint8)         # dry-stone wall, UI greys
for y0, joints in ((0, (5, 11)), (5, (2, 8, 14)), (10, (4, 10))):
    stone[y0, :] = 0
    stone[y0 + 4 if y0 < 10 else 15, :] = 3
    stone[y0 + 3 if y0 < 10 else 14, :] = 2
    for j in joints:
        stone[y0:y0 + (5 if y0 < 10 else 6), j] = 3
        stone[y0, j] = 3

def ship():
    s = np.full((48, 32), 1, np.uint8)
    for y in range(2, 46):
        w = min(13, 2 + (y - 2)) if y < 30 else min(13, 9 + (45 - y) // 2)
        s[y, 16 - w:16 + w] = 2
        s[y, 16 - w] = 3; s[y, 16 + w - 1] = 3
        if y % 4 == 0:
            s[y, 16 - w + 2:16 + w - 2] = 3     # deck planks
    s[2, 14:18] = 3; s[45, 16 - 9:16 + 9] = 3
    for my in (13, 24, 35):                     # masts and furled sails
        s[my, 5:27] = 0; s[my + 1, 5:27] = 3
        s[my - 2:my + 2, 14:18] = 3; s[my - 1:my + 1, 15:17] = 0
    return s

add_mt(".", grass, P_GRASS)
add_mt(",", tall, P_GRASS, GRASS)
add_mt("=", path, P_PATH)
add_mt("~", water, P_WATER, SOLID)
add_mt("T", tree, P_GRASS, SOLID)
add_mt("F", flower, P_FLOWER)
add_mt("S", sign, P_WOOD, SOLID)
add_mt("Q", quay, P_UI)
add_mt("B", bridge, P_WATER)
add_mt("W", stone, P_UI, SOLID)
H = house()
for chars, pal in (("abcdef", P_RED), ("ghijkl", P_BLUE)):
    for i, ch in enumerate(chars):
        y, x = (i // 3) * 16, (i % 3) * 16
        add_mt(ch, H[y:y + 16, x:x + 16], pal, SOLID | (DOOR if i == 4 else 0))
S = ship()
for i, ch in enumerate("123456"):
    y, x = (i // 2) * 16, (i % 2) * 16
    add_mt(ch, S[y:y + 16, x:x + 16], P_WATER, SOLID)

WATER_TILE = add_tile(water[0:8, 0:8])
water_b = np.roll(water[0:8, 0:8], 4, axis=1)

# dialog frame (UI palette)
def frame(top, bottom, left, right):
    f = np.zeros((8, 8), np.uint8)
    if top: f[1:3, :] = 3
    if bottom: f[5:7, :] = 3
    if left: f[:, 1:3] = 3
    if right: f[:, 5:7] = 3
    if top: f[0, :] = 0
    if bottom: f[7, :] = 0
    if left: f[:, 0] = 0
    if right: f[:, 7] = 0
    if top and left: f[0:1, :] = 0; f[:, 0:1] = 0; f[1, 1] = 0
    if top and right: f[1, 6] = 0
    if bottom and left: f[6, 1] = 0
    if bottom and right: f[6, 6] = 0
    return f
FR = {n: add_tile(frame(*a)) for n, a in {
    "TL": (1, 0, 1, 0), "T": (1, 0, 0, 0), "TR": (1, 0, 0, 1), "L": (0, 0, 1, 0),
    "R": (0, 0, 0, 1), "BL": (0, 1, 1, 0), "B": (0, 1, 0, 0), "BR": (0, 1, 0, 1)}.items()}
FR["ARROW"] = add_tile(art(["........", "........", ".333333.", "..3333..",
                            "...33...", "........", "........", "........"], 8))
assert len(tiles) <= 128, len(tiles)

# ---------------------------------------------------------------- sprites
down = [
    "................", ".....333333.....", "....32222223....", "...3222222223...",
    "...3233333323...", "...3311111133...", "...3131111313...", "...3111111113...",
    "....31111113....", "...3322222233...", "..312222222213..", "..312222222213..",
    "...3322222233...", "....33333333....", "....3113..3113..", "....3333..3333..",
]
up = down[:4] + ["...3222222223...", "...3222222223...", "...3333333333...",
                 "....33333333....", "....31111113...."] + down[9:]
left = [
    "................", ".....333333.....", "....32222223....", "...3222222223...",
    ".3333222222223..", "...3111133333...", "...3131113333...", "...3111111333...",
    "....3111113.....", "....32222223....", "....32211223....", "....32211223....",
    "....32222223....", "....33333333....", "......3113......", "......3333......",
]
def step(rows):
    return rows[:14] + ["....3333..3113..", "..........3333.."]
d, u, l = art(down), art(up), art(left)
d1, u1 = art(step(down)), art(step(up))
l1 = art(left[:14] + ["....3113.3113...", "....333..3333..."])
npc = d.copy(); npc[1:5][npc[1:5] == 2] = 3
frames = [d, d1, d1[:, ::-1], u, u1, u1[:, ::-1], l, l1, npc]
spr = []
for f in frames:
    for x in (0, 8):
        spr += [f[0:8, x:x + 8], f[8:16, x:x + 8]]

# ---------------------------------------------------------------- New Ross
MAP = [
    "~~~QTTTT==TTTTTT",
    "~~~Q.abc==.,,,,T",
    "~~~Q.def==.,,,,T",
    "BBB=======..,,,T",
    "~~~QSF..==S....T",
    "~12Q....==.abc.T",
    "~34Q.ghi==.def.T",
    "~56Q.jkl========",
    "~~~Q==========.T",
    "~~~Q.F..==..F..T",
    "~~~Q....==.ghi.T",
    "~~~QWWW.==.jkl.T",
    "~~~Q,,,.=====..T",
    "~~~Q,,,,==..F..T",
    "~~~Q,,,,==.....T",
    "~~~QTTTT==TTTTTT",
]
assert len(MAP) == 16 and all(len(r) == 16 for r in MAP)
START = (12, 12)
NPC_POS = (7, 9)

PATHLIKE = set("=BQek")
def cell(x, y):
    ch = MAP[y][x]
    if ch != "=":
        return mt_char[ch]
    px = mt_src["="][0].copy()
    def open_(dx, dy):
        nx, ny = x + dx, y + dy
        return 0 <= nx < 16 and 0 <= ny < 16 and MAP[ny][nx] not in PATHLIKE
    rag = np.array([(i * 7 + x * 3 + y * 5) % 5 < 2 for i in range(16)])
    if open_(0, -1): px[0, :] = 3; px[1, rag] = 3
    if open_(0, 1): px[15, :] = 3; px[14, rag] = 3
    if open_(-1, 0): px[:, 0] = 3; px[rag, 1] = 3
    if open_(1, 0): px[:, 15] = 3; px[rag, 14] = 3
    return mt_id(px, P_PATH, 0)
MAP_IDS = [cell(x, y) for y in range(16) for x in range(16)]
assert len(tiles) <= 128 and len(metatiles) <= 255, (len(tiles), len(metatiles))

def wrap(text):
    """Word-wrap to the 18x2 dialog box: \\n = second line, \\f = new page."""
    pages = []
    for para in text.split("|"):
        lines = textwrap.wrap(para, 18)
        pages += ["\\n".join(lines[i:i + 2]) for i in range(0, len(lines), 2)]
    return "\\f".join(pages)

TEXTS = {
    "TOWN": "NEW ROSS|Ros Mhic Thriuin. Where the Barrow meets the tide.",
    "SHIP": "THE DUNBRODY|A tall ship from long ago. She still dreams of the sea.",
    "HOME": "Home. The kettle is always on.",
    "LOCKED": "Nobody's home. Probably down at the match.",
    "NPC": "Well! Up early? They say strange creatures were seen in the long grass "
           "by the river.|Mind yourself out there without a partner of your own!",
    "NORTH": "The road north to ENNISCORTHY isn't finished yet.",
    "SOUTH": "The road south to HOOK HEAD isn't finished yet.",
    "EAST": "The road east to WEXFORD TOWN isn't finished yet.",
    "WEST": "The bridge to KILKENNY is closed for repairs.",
}
INTERACT = [(10, 4, "TOWN"), (4, 4, "SHIP"), (12, 11, "HOME"), NPC_POS + ("NPC",)]

# ---------------------------------------------------------------- emit
def carr(vals, per=16):
    vals = list(vals)
    return ",\n".join("  " + ",".join(str(v) for v in vals[i:i + per]) for i in range(0, len(vals), per))

h = ["#ifndef ASSETS_H", "#define ASSETS_H", "#include <gb/gb.h>", "#include <gb/cgb.h>",
     f"#define TILE_BASE {TILE_BASE}", f"#define N_TILES {len(tiles)}",
     f"#define N_SPR_TILES {len(spr)}", f"#define WATER_TILE {WATER_TILE}",
     f"#define MAP_W 16", f"#define MAP_H 16",
     f"#define START_X {START[0]}", f"#define START_Y {START[1]}",
     f"#define NPC_X {NPC_POS[0]}", f"#define NPC_Y {NPC_POS[1]}",
     f"#define F_SOLID {SOLID}", f"#define F_DOOR {DOOR}", f"#define F_GRASS {GRASS}",
     f"#define P_UI {P_UI}", f"#define N_INTERACT {len(INTERACT)}"]
h += [f"#define FR_{k} {v}" for k, v in FR.items()]
h += [f"#define TXT_{k} {i}" for i, k in enumerate(TEXTS)]
h += ["typedef struct { uint8_t x, y, text; } interact_t;",
      "extern const uint8_t bg_tiles[], spr_tiles[], water_anim[2][16];",
      "extern const palette_color_t bg_pals[], obj_pals[];",
      "extern const uint8_t mt_tiles[][4], mt_attr[][4], mt_flags[], town_map[];",
      "extern const interact_t interacts[];", "extern const char * const texts[];",
      "#endif"]
c = ['#include "assets.h"',
     "const uint8_t bg_tiles[] = {\n" + carr(v for t in tiles for v in to2bpp(t)) + "\n};",
     "const uint8_t spr_tiles[] = {\n" + carr(v for t in spr for v in to2bpp(t)) + "\n};",
     "const uint8_t water_anim[2][16] = {{" + ",".join(map(str, to2bpp(water[0:8, 0:8]))) +
     "},{" + ",".join(map(str, to2bpp(water_b))) + "}};",
     "const palette_color_t bg_pals[] = {\n" + carr((rgb(x) for p in BG_PALS for x in p), 4) + "\n};",
     "const palette_color_t obj_pals[] = {\n" + carr((rgb(x) for p in OBJ_PALS for x in p), 4) + "\n};",
     "const uint8_t mt_tiles[][4] = {\n" + ",\n".join("  {%d,%d,%d,%d}" % tuple(m[0]) for m in metatiles) + "\n};",
     "const uint8_t mt_attr[][4] = {\n" + ",\n".join("  {%d,%d,%d,%d}" % tuple(m[1]) for m in metatiles) + "\n};",
     "const uint8_t mt_flags[] = {" + ",".join(str(m[2]) for m in metatiles) + "};",
     "const uint8_t town_map[] = {\n" + carr(MAP_IDS) + "\n};",
     "const interact_t interacts[] = {" + ",".join("{%d,%d,TXT_%s}" % i for i in INTERACT) + "};",
     "const char * const texts[] = {\n" + ",\n".join('  "%s"' % wrap(t) for t in TEXTS.values()) + "\n};"]
open(f"{OUT}/assets.h", "w").write("\n".join(h) + "\n")
open(f"{OUT}/assets.c", "w").write("\n".join(c) + "\n")
print(f"{len(tiles)} bg tiles, {len(metatiles)} metatiles, {len(spr)} sprite tiles")

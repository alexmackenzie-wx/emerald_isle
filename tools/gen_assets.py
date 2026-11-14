#!/usr/bin/env python3
"""Generates src/gen/assets.c/.h: tiles, metatiles, palettes, sprites, maps, card art, text.

All art is defined here (ASCII pixels or small drawing routines) so the whole
game builds from source. Pixels are colour indices 0-3 into a GBC palette.
"""
import sys, textwrap, re
import numpy as np
from PIL import Image, ImageDraw

OUT = sys.argv[1] if len(sys.argv) > 1 else "src/gen"
TILE_BASE = 96           # BG tiles live at 96..255, font at 0..95
SOLID, DOOR, GRASS = 1, 2, 4

# ---------------------------------------------------------------- palettes
def rgb(h):
    r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)

UI = ["#f8f8f8", "#b0b0a8", "#686870", "#181820"]
P_UI = 7
# outdoor set
P_GRASS, P_PATH, P_WATER, P_RED, P_BLUE, P_FLOWER, P_WOOD = range(7)
BG_PALS = [
    ["#a8e070", "#70c048", "#388830", "#184818"],  # grass / trees
    ["#f0e0a8", "#d8b870", "#a07840", "#a8e070"],  # path (3 = grass, for ragged edges)
    ["#c8f0f8", "#60a8f0", "#885028", "#301808"],  # water + ship + bridge
    ["#f8f0e0", "#e86040", "#983020", "#281818"],  # red-roof house
    ["#f8f0e0", "#6890c8", "#385890", "#181828"],  # slate-roof house
    ["#a8e070", "#70c048", "#f8d030", "#e84858"],  # flowers
    ["#a8e070", "#e0b060", "#a06830", "#301808"],  # wood on grass
    UI,                                            # UI + quay stone
]
# indoor set
I_FLOOR, I_WALL, I_SPARE, I_RUG, I_APPL, I_WIN, I_PACK = range(7)
IN_PALS = [
    ["#f0d8a0", "#d8b070", "#a87840", "#402810"],  # floorboards + furniture
    ["#e8f0d8", "#c0d8a8", "#a87840", "#402810"],  # wallpaper
    UI,
    ["#f0d8a0", "#e86050", "#a03028", "#402810"],  # rug
    ["#f0d8a0", "#c8d0d8", "#687890", "#202830"],  # TV, counter, kettle
    ["#f8f8f8", "#88c8f8", "#a87840", "#402810"],  # window
    ["#f0d8a0", "#f8d030", "#209048", "#402810"],  # card packs on the table
    UI,
]
# card pack screen
K_DARK, K_CARD, K_GRASS, K_FIRE, K_WATER, K_FOIL, K_SHINY = range(7)
PACK_PALS = [
    ["#101830", "#283860", "#f8d030", "#f8f8f8"],  # backdrop, light-on-dark text
    ["#f8f0d8", "#d8c890", "#a08840", "#282018"],  # card face
    ["#d8f0c0", "#f8f0e0", "#48a848", "#202020"],  # grass art
    ["#f8d8a8", "#fff8e8", "#e86820", "#202020"],  # fire art
    ["#c0e8f8", "#f8f0e0", "#806040", "#202020"],  # water art
    ["#209048", "#48c070", "#f8d030", "#103820"],  # foil pack
    ["#f8f0d8", "#d8c890", "#a08840", "#c89010"],  # shiny card frame (3 cycles at runtime)
    UI,
]
OBJ_PALS = [
    ["#000000", "#f8d0a0", "#7038a8", "#201828"],  # player (purple & gold county)
    ["#000000", "#f8d0a0", "#d04040", "#201828"],  # red
    ["#000000", "#f8d0a0", "#209048", "#201828"],  # green
    ["#000000", "#f8d0a0", "#3070d0", "#201828"],  # blue
    ["#000000", "#f8d0a0", "#208898", "#402010"],  # mom
    ["#000000", "#f8f8f8", "#f8d030", "#f8a020"],  # sparkle
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

def tiles2bpp(px):
    """Any WxH image (multiples of 8) -> flat 2bpp bytes, tiles in row order."""
    h, w = px.shape
    return [v for y in range(0, h, 8) for x in range(0, w, 8) for v in to2bpp(px[y:y + 8, x:x + 8])]

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
    assert ch not in mt_char, f"map letter {ch!r} used twice"
    mt_char[ch] = mt_id(px, pal, flags)
    mt_src[ch] = (px, pal, flags)

# ---------------------------------------------------------------- outdoor art
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
    """A 64x48 slate-roofed cottage: 4x3 metatiles, door in the second column."""
    h = np.zeros((48, 64), np.uint8)
    h[0:28, :] = 1                              # slate roof, staggered courses
    for y in range(28):
        if y % 4 == 3:
            h[y, :] = 2
        else:
            h[y, (np.arange(64) + (y // 4) % 2 * 4) % 8 == 0] = 2
    for y in range(4, 26, 4):                   # light catching the slate edges
        h[y, 2 + (y // 4) % 2 * 4:62:8] = 0
    h[0, :] = 3; h[1, 1:63] = 0; h[2, 1:63] = 2 # ridge
    h[0:28, 0:2] = 3; h[0:28, 62:64] = 3
    h[25, 2:62] = 2; h[26, :] = 3; h[27, 1:63] = 0; h[28, :] = 3     # eave + fascia
    h[0:12, 8:20] = 3; h[1:11, 9:19] = 0        # chimney
    h[1:4, 11:17] = 2; h[4, 9:19] = 3
    h[7, 10:18:3] = 2; h[9, 11:18:3] = 2
    h[8:20, 38:52] = 3; h[9:19, 39:51] = 0      # skylight
    h[10:18, 40:50] = 2; h[10:18, 45] = 0; h[11, 41:44] = 1; h[12, 41] = 1
    h[29:48, 0:2] = 3; h[29:48, 62:64] = 3      # whitewashed walls
    h[29, 2:62] = 1; h[30, 2:62:2] = 1          # shadow under the eave
    h[42:47, 2:62] = 1; h[42, 2:62] = 3; h[44, 3:62:6] = 2; h[47, :] = 3   # painted plinth
    for x0 in (4, 35, 50):                      # windows: panes, curtains, sills
        h[31:41, x0:x0 + 11] = 3
        h[32:40, x0 + 1:x0 + 10] = 2
        h[32:40, x0 + 5] = 0; h[36, x0 + 1:x0 + 10] = 0
        h[32:34, x0 + 1:x0 + 4] = 0; h[32:34, x0 + 7:x0 + 10] = 0; h[34, x0 + 1] = 0; h[34, x0 + 9] = 0
        h[37, x0 + 2:x0 + 4] = 1; h[38, x0 + 2] = 1
        h[41, x0 - 1:x0 + 12] = 3
    h[30:48, 18:30] = 3                         # door with fanlight
    h[31:47, 19:29] = 1
    h[31:35, 19:29] = 0; h[31:35, 22] = 3; h[31:35, 26] = 3; h[35, 19:29] = 3
    h[37:41, 20:23] = 2; h[37:41, 25:28] = 2; h[42:46, 20:23] = 2; h[42:46, 25:28] = 2
    h[41, 28] = 0
    h[46, 18:30] = 3; h[47, 18:30] = 0          # doorstep
    return h

stone = np.full((16, 16), 1, np.uint8)         # dry-stone wall, UI greys
for y0, joints in ((0, (5, 11)), (5, (2, 8, 14)), (10, (4, 10))):
    stone[y0, :] = 0
    stone[y0 + 4 if y0 < 10 else 15, :] = 3
    stone[y0 + 3 if y0 < 10 else 14, :] = 2
    for j in joints:
        stone[y0:y0 + (5 if y0 < 10 else 6), j] = 3

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
HOUSE_PAL = {"R": P_RED, "U": P_BLUE}      # map letter = top-left corner of a house
S = ship()
for i, ch in enumerate("123456"):
    y, x = (i // 2) * 16, (i % 2) * 16
    add_mt(ch, S[y:y + 16, x:x + 16], P_WATER, SOLID)

WATER_TILE = add_tile(water[0:8, 0:8])
water_b = np.roll(water[0:8, 0:8], 4, axis=1)

# ---------------------------------------------------------------- indoor art
def box(fill, edge=3, y0=0, y1=16, x0=0, x1=16, base=None):
    b = np.zeros((16, 16), np.uint8) if base is None else base.copy()
    b[y0:y1, x0:x1] = edge
    b[y0 + 1:y1 - 1, x0 + 1:x1 - 1] = fill
    return b

floor = np.zeros((16, 16), np.uint8)
floor[7, :] = 1; floor[15, :] = 1
floor[0:7, 5] = 1; floor[8:15, 12] = 1
wall_hi = np.zeros((16, 16), np.uint8); wall_hi[:, 1::4] = 1
wall_lo = wall_hi.copy(); wall_lo[12:16, :] = 2; wall_lo[12, :] = 3; wall_lo[15, :] = 3
window = wall_lo.copy(); window[:12, :] = 2
window[1:11, 1:15] = 3; window[2:10, 2:14] = 0; window[3:9, 3:13] = 1
window[3:9, 7:9] = 0; window[5:7, 3:13] = 0; window[11, :] = 3
rug = np.full((16, 16), 1, np.uint8); rug[::4, ::4] = 0; rug[2::4, 2::4] = 2
table = box(0, y1=12); table[1, 1:15] = 1; table[12:16, :] = 2; table[12, :] = 3
table[13:16, 2:4] = 3; table[13:16, 12:14] = 3; table[15, :] = 3
ptable = table.copy(); ptable[ptable == 2] = 3; ptable[ptable == 1] = 0
for x0 in (3, 9):
    ptable[2:10, x0:x0 + 5] = 3; ptable[3:9, x0 + 1:x0 + 4] = 2; ptable[5:7, x0 + 1:x0 + 4] = 1
tv = box(1, y0=1, y1=13); tv[3:10, 2:11] = 3; tv[4:9, 3:10] = 2; tv[4, 3:6] = 1; tv[5, 3] = 1
tv[5, 12:14] = 3; tv[8, 12:14] = 3; tv[13:16, 4:12] = 3; tv[14, 5:11] = 2
counter = box(1, y1=7); counter[6:16, :] = 3; counter[7:15, 1:15] = 2; counter[7:15, 7:9] = 3
counter[10, 3:5] = 1; counter[10, 11:13] = 1
kettle = counter.copy(); kettle[0:6, 4:11] = 3; kettle[1:5, 5:10] = 1; kettle[2, 11:13] = 3; kettle[1, 6:8] = 0
mat = np.zeros((16, 16), np.uint8); mat[3:14, 1:15] = 2; mat[4:13, 2:14] = 1; mat[6:11:2, 4:12] = 2

add_mt("_", floor, I_FLOOR)
add_mt("^", wall_hi, I_WALL, SOLID)
add_mt("#", wall_lo, I_WALL, SOLID)
add_mt("o", window, I_WIN, SOLID)
add_mt("r", rug, I_RUG)
add_mt("t", table, I_FLOOR, SOLID)
add_mt("p", ptable, I_PACK, SOLID)
add_mt("v", tv, I_APPL, SOLID)
add_mt("C", counter, I_APPL, SOLID)
add_mt("K", kettle, I_APPL, SOLID)
add_mt("m", mat, I_RUG)

# ---------------------------------------------------------------- UI + pack tiles
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
    if top and left: f[1, 1] = 0
    if top and right: f[1, 6] = 0
    if bottom and left: f[6, 1] = 0
    if bottom and right: f[6, 6] = 0
    return f
FR = {n: add_tile(frame(*a)) for n, a in {
    "TL": (1, 0, 1, 0), "T": (1, 0, 0, 0), "TR": (1, 0, 0, 1), "L": (0, 0, 1, 0),
    "R": (0, 0, 0, 1), "BL": (0, 1, 1, 0), "B": (0, 1, 0, 0), "BR": (0, 1, 0, 1)}.items()}
FR["ARROW"] = add_tile(art(["........", "........", ".333333.", "..3333..",
                            "...33...", "........", "........", "........"], 8))
foil = np.array([[1 if (x + y) % 8 < 2 else 0 for x in range(8)] for y in range(8)], np.uint8)
crimp = np.array([[3 if (x % 4 in (0, 1)) == (y < 4) else 0 for x in range(8)] for y in range(8)], np.uint8)
gold = np.full((8, 8), 2, np.uint8); gold[0, :] = 3; gold[7, :] = 3
PK = {"FOIL": add_tile(foil), "CRIMP": add_tile(crimp), "GOLD": add_tile(gold)}

# ---------------------------------------------------------------- sprites
# 16x16, colours: 1 skin/light, 2 clothing colour (from the sprite palette), 3 dark.
BODY = ["...3321111233...", "..312221122213..", "..312221122213..", "..332221122233..",
        "....32222223....", "....3113.3113...", "....3333.3333..."]
FACE = ["...3311111133...", "...3131111313...", "...3111111113...", "....31111113...."]
hero_d = [".....333333.....", "....32112223....", "...3211222223...", "...3222222223...",
          "..333333333333.."] + FACE + BODY
hero_u = [".....333333.....", "....32222223....", "...3222222223...", "...3222222223...",
          "...3222222223...", "...3333333333...", "...3333333333...", "...3113333113...",
          "....33333333....", "...3322222233...", "..312233332213..", "..312231132213..",
          "..332233332233.."] + BODY[4:]
hero_l = [".....333333.....", "....32112223....", "...3211222223...", "..33222222223...",
          "3333332222223...", "...3111133333...", "...3131113333...", "...3111111333...",
          "....3111113.....", "....33222233....", "....32212223....", "....32112223....",
          "....33222233....", ".....322223.....", "......3113......", "......3333......"]
girl = [".....333333.....", "....33333333....", "...3333333333...", "...3333333333...",
        "...3331111333...", "...3311111133...", "..331311113133..", "..331111111133..",
        "..333111111333..", "...3321111233...", "..312221122213..", "..312221122213..",
        "..332221122233..", "...3222222223...", "....3113.3113...", "....3333.3333..."]
boy = ["....3.33.33.3...", "....33333333....", "...3333333333...", "...3333333333...",
       "...3331331333..."] + FACE + BODY
mom = ["......3333......", ".....333333.....", "....33333333....", "...3333333333...",
       "...3333113333...", "...3311111133...", "...3131111313...", "...3111111113...",
       "....31111113....", "...3321111233...", "..312211112213..", "..312211112213..",
       "..332211112233..", "...3221111223...", "...3222222223...", "....33333333...."]
oldman = ["................", "....33333333....", "...3222222223...", "..322222222223..",
          "..333333333333.."] + FACE + BODY
def step(rows):
    return rows[:14] + ["....3113.3333...", "....3333........"]
d, u, l = art(hero_d), art(hero_u), art(hero_l)
d1, u1 = art(step(hero_d)), art(step(hero_u))
l1 = art(hero_l[:14] + ["....3113.3113...", "....3333.3333..."])
frames = [d, d1, d1[:, ::-1], u, u1, u1[:, ::-1], l, l1, art(girl), art(boy), art(mom), art(oldman)]
F_GIRL, F_BOY, F_MOM, F_OLD = 8, 9, 10, 11
spr = []
for f in frames:
    for x in (0, 8):
        spr += [f[0:8, x:x + 8], f[8:16, x:x + 8]]
SPARK_TILE = len(spr)
blank8 = np.zeros((8, 8), np.uint8)
spr += [art(["...1....", "...1....", "..121...", "1122211.", "..121...", "...1....", "...1....", "........"], 8), blank8,
        art(["........", "........", "...1....", "..121...", "...1....", "........", "........", "........"], 8), blank8]

# ---------------------------------------------------------------- card art
# Creatures are drawn flat with shapes (1 light, 2 mid, 3 line), then finish()
# adds volume: dithered shadow on the lower right, highlights on the upper left,
# a sunburst behind and a ground shadow beneath.
def canvas(n):
    im = Image.new("L", (n, n), 0)
    return im, ImageDraw.Draw(im)

def finish(im, light_shadow=2, burst=True):
    a = np.array(im, np.uint8)
    h, w = a.shape
    sil = a != 0
    def run(y, x, dy, dx, n):
        for k in range(1, n + 1):
            yy, xx = y + dy * k, x + dx * k
            if not (0 <= yy < h and 0 <= xx < w) or not sil[yy, xx]:
                return k
        return 99
    out = a.copy()
    for y in range(h):
        for x in range(w):
            v = a[y, x]
            if v not in (1, 2):
                continue
            s = min(run(y, x, 1, 1, 7), run(y, x, 1, 0, 7), run(y, x, 0, 1, 7))
            t = min(run(y, x, -1, -1, 5), run(y, x, -1, 0, 5), run(y, x, 0, -1, 5))
            ch = (x + y) % 2 == 0
            thin = t <= 3                    # skip small shapes: shading them is just noise
            if v == 2:
                if s <= 4 and not thin: out[y, x] = 3 if ch else 2
                elif s <= 6 and not thin and ch and y % 2 == 0: out[y, x] = 3
                elif t <= 2 and s > 6 and ch: out[y, x] = 1
            elif s <= 3 and not thin:
                if light_shadow == 2: out[y, x] = 2 if ch else 1
                elif ch and y % 2 == 0: out[y, x] = 3
    cx, cy = w / 2, h * 0.55
    for y in range(h):
        for x in range(w):
            if sil[y, x]:
                continue
            if ((x - cx) / 24) ** 2 + ((y - (h - 4)) / 3.5) ** 2 <= 1:
                out[y, x] = 3 if (x + y) % 2 == 0 else 0            # ground shadow
            elif burst and int((np.arctan2(y - cy, x - cx) + np.pi) / (2 * np.pi) * 24) % 2 == 0 \
                    and (x + y) % 2 == 0 and (x - cx) ** 2 + (y - cy) ** 2 > 400:
                out[y, x] = 1                                        # sunburst rays
    out[0, :] = 3; out[-1, :] = 3; out[:, 0] = 3; out[:, -1] = 3
    return out

def eye(d, x, y, w=7, h=8):
    d.ellipse((x, y, x + w, y + h), fill=3)
    d.rectangle((x + 1, y + 1, x + 2, y + 2), fill=1)
    d.point((x + w - 2, y + h - 2), fill=2)

def boveen():           # grass calf
    im, d = canvas(64); E = d.ellipse
    d.line([(49, 40), (58, 32)], fill=3, width=3)
    d.polygon([(55, 34), (52, 23), (62, 25), (63, 35)], fill=2, outline=3)
    d.line([(57, 33), (58, 27)], fill=3)
    for x in (14, 23, 35, 44):
        d.rectangle((x, 44, x + 7, 59), fill=1, outline=3); d.rectangle((x, 55, x + 7, 59), fill=3)
        d.line([(x + 3, 56), (x + 3, 59)], fill=2)
    E((10, 26, 56, 54), fill=1, outline=3)
    for cx, cy in ((43, 34), (38, 41), (48, 41)):                    # shamrock patch
        E((cx - 5, cy - 5, cx + 5, cy + 5), fill=2)
    d.line([(43, 42), (45, 49)], fill=2, width=2)
    E((16, 43, 23, 50), fill=2)
    d.polygon([(13, 16), (1, 9), (5, 22), (15, 23)], fill=2, outline=3); d.line([(12, 18), (5, 13)], fill=3)
    d.polygon([(43, 16), (55, 9), (51, 22), (41, 23)], fill=2, outline=3); d.line([(44, 18), (51, 13)], fill=3)
    E((15, 4, 21, 12), fill=1, outline=3); E((35, 4, 41, 12), fill=1, outline=3)     # horn buds
    E((8, 8, 48, 40), fill=1, outline=3)
    E((30, 10, 45, 26), fill=2)
    d.polygon([(28, 9), (19, 0), (30, 3)], fill=2, outline=3)
    d.polygon([(28, 9), (38, 1), (30, 3)], fill=2, outline=3)
    E((13, 24, 43, 41), fill=1, outline=3)
    E((19, 30, 23, 35), fill=3); E((33, 30, 37, 35), fill=3)
    d.arc((23, 32, 33, 39), 20, 160, fill=3)
    eye(d, 15, 14); eye(d, 33, 14)
    return finish(im, light_shadow=3)

def ruakit():           # fire fox kit
    im, d = canvas(64); E = d.ellipse
    d.polygon([(40, 59), (58, 57), (63, 46), (59, 35), (50, 30), (42, 36), (37, 47)], fill=2, outline=3)
    d.polygon([(50, 31), (52, 19), (56, 26), (59, 12), (62, 24), (63, 35), (62, 44), (57, 37)], fill=1, outline=3)
    E((16, 31, 46, 61), fill=2, outline=3)
    d.polygon([(23, 38), (27, 43), (31, 39), (35, 43), (39, 38), (39, 52), (35, 59), (27, 59), (23, 52)], fill=1)
    E((19, 49, 29, 62), fill=2, outline=3); E((33, 49, 43, 62), fill=2, outline=3)
    d.chord((19, 53, 29, 62), 0, 180, fill=3); d.chord((33, 53, 43, 62), 0, 180, fill=3)   # dark socks
    d.polygon([(11, 21), (8, 0), (27, 12)], fill=2, outline=3)
    d.polygon([(51, 21), (54, 0), (35, 12)], fill=2, outline=3)
    d.polygon([(13, 15), (12, 6), (21, 12)], fill=1); d.polygon([(49, 15), (50, 6), (41, 12)], fill=1)
    d.polygon([(8, 0), (9, 6), (14, 4)], fill=3); d.polygon([(54, 0), (53, 6), (48, 4)], fill=3)
    d.polygon([(9, 27), (1, 31), (8, 33), (3, 39), (14, 38)], fill=1, outline=3)           # cheek fluff
    d.polygon([(53, 27), (61, 31), (54, 33), (59, 39), (48, 38)], fill=1, outline=3)
    E((7, 9, 55, 42), fill=2, outline=3)
    d.chord((9, 17, 53, 42), 0, 180, fill=1)
    d.polygon([(27, 30), (35, 30), (33, 23), (29, 23)], fill=2)                             # nose bridge
    d.polygon([(27, 10), (31, 15), (35, 10)], fill=1)                                       # forehead tuft
    eye(d, 17, 20); eye(d, 39, 20)
    E((28, 30, 34, 34), fill=3)
    d.line([(31, 34), (31, 36)], fill=3); d.line([(31, 36), (28, 38)], fill=3); d.line([(31, 36), (34, 38)], fill=3)
    return finish(im)

def dovran():           # water otter pup
    im, d = canvas(64); E = d.ellipse
    d.polygon([(40, 46), (55, 58), (63, 53), (61, 45), (46, 38)], fill=2, outline=3)
    E((17, 24, 47, 61), fill=2, outline=3)
    E((23, 31, 41, 58), fill=1)
    E((15, 54, 29, 63), fill=2, outline=3); E((35, 54, 49, 63), fill=2, outline=3)
    for x in (19, 22, 25, 39, 42, 45):
        d.line([(x, 59), (x, 62)], fill=3)
    E((9, 5, 20, 16), fill=2, outline=3); E((44, 5, 55, 16), fill=2, outline=3)
    E((12, 8, 17, 13), fill=1); E((47, 8, 52, 13), fill=1)
    E((10, 5, 54, 34), fill=2, outline=3)
    d.polygon([(29, 6), (32, 0), (35, 6)], fill=2, outline=3)
    E((19, 18, 45, 33), fill=1)
    eye(d, 18, 12, 6, 7); eye(d, 40, 12, 6, 7)
    E((29, 20, 35, 24), fill=3)
    d.line([(32, 24), (32, 27)], fill=3); d.arc((27, 24, 32, 30), 0, 120, fill=3); d.arc((32, 24, 37, 30), 60, 180, fill=3)
    for y0, y1 in ((22, 20), (25, 25), (28, 30)):
        d.line([(20, y0), (12, y1)], fill=3); d.line([(44, y0), (52, y1)], fill=3)
    d.polygon([(32, 32), (24, 42), (32, 49), (40, 42)], fill=1, outline=3)                  # shell
    d.line([(32, 33), (32, 48)], fill=3); d.line([(32, 34), (27, 43)], fill=3); d.line([(32, 34), (37, 43)], fill=3)
    E((18, 37, 28, 46), fill=2, outline=3); E((36, 37, 46, 46), fill=2, outline=3)
    for cx, cy in ((7, 40), (57, 28), (9, 52)):                                             # droplets
        E((cx - 2, cy - 2, cx + 2, cy + 2), fill=1, outline=3)
    return finish(im)

def icon(im):            # light shading for the small energy icons
    a = np.array(im, np.uint8); out = a.copy()
    for y in range(1, 31):
        for x in range(1, 31):
            if a[y, x] == 2 and (x + y) % 2 == 0 and (a[y + 1, x + 1] == 3 or a[y + 2, x + 2] == 3 or a[y + 1, x] == 3):
                out[y, x] = 3
    return out

def shamrock():
    im, d = canvas(32); E = d.ellipse
    d.line([(16, 18), (20, 30)], fill=3, width=3); d.line([(16, 18), (20, 29)], fill=2)
    for cx, cy in ((16, 8), (8, 17), (24, 17)):
        E((cx - 7, cy - 7, cx + 7, cy + 7), fill=2, outline=3); E((cx - 4, cy - 4, cx - 1, cy - 1), fill=1)
    return icon(im)

def flame():
    im, d = canvas(32)
    d.rectangle((5, 25, 26, 30), fill=3)
    d.polygon([(16, 1), (23, 12), (22, 8), (27, 18), (24, 26), (8, 26), (5, 18), (9, 10), (11, 15)], fill=2, outline=3)
    d.polygon([(16, 12), (20, 20), (18, 25), (13, 25), (11, 20)], fill=1)
    return icon(im)

def raindrop():
    im, d = canvas(32); E = d.ellipse
    E((6, 11, 26, 31), fill=1, outline=3)
    d.polygon([(16, 1), (8, 17), (24, 17)], fill=1)
    d.line([(16, 1), (7, 18)], fill=3); d.line([(16, 1), (25, 18)], fill=3)
    E((10, 17, 13, 23), fill=0)
    return np.array(im, np.uint8)

STARTERS = [("BOVEEN", "GRASS", boveen(), K_GRASS), ("RUAKIT", "FIRE", ruakit(), K_FIRE),
            ("DOVRAN", "WATER", dovran(), K_WATER)]
ICONS = [("SHAMROCK", shamrock(), K_GRASS), ("TURF FIRE", flame(), K_FIRE), ("RAINDROP", raindrop(), K_WATER)]

# ---------------------------------------------------------------- maps
PATHLIKE = set("=BQ")
def compile_map(rows):
    h, w = len(rows), len(rows[0])
    assert all(len(r) == w for r in rows) and w <= 16 and h <= 16
    stamp, doors = {}, set()
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch in HOUSE_PAL:
                for j in range(3):
                    for i in range(4):
                        door = (i, j) == (1, 2)
                        stamp[(x + i, y + j)] = mt_id(H[j * 16:j * 16 + 16, i * 16:i * 16 + 16], HOUSE_PAL[ch],
                                                      SOLID | (DOOR if door else 0))
                        if door: doors.add((x + i, y + j))
    def cell(x, y):
        ch = rows[y][x]
        if (x, y) in stamp:
            return stamp[(x, y)]
        if ch != "=":
            return mt_char[ch]
        px = mt_src["="][0].copy()
        def open_(dx, dy):
            nx, ny = x + dx, y + dy
            return 0 <= nx < w and 0 <= ny < h and rows[ny][nx] not in PATHLIKE and (nx, ny) not in doors
        rag = np.array([(i * 7 + x * 3 + y * 5) % 5 < 2 for i in range(16)])
        if open_(0, -1): px[0, :] = 3; px[1, rag] = 3
        if open_(0, 1): px[15, :] = 3; px[14, rag] = 3
        if open_(-1, 0): px[:, 0] = 3; px[rag, 1] = 3
        if open_(1, 0): px[:, 15] = 3; px[rag, 14] = 3
        return mt_id(px, P_PATH, 0)
    return w, h, [cell(x, y) for y in range(h) for x in range(w)]

TEXTS = {
    "TOWN": "NEW ROSS|Ros Mhic Thriuin. Where the Barrow meets the tide.",
    "SHIP": "THE DUNBRODY|A tall ship from long ago. She still dreams of the sea.",
    "LOCKED": "Nobody's home. Probably down at the match.",
    "NPC": "Well, @! Strange creatures were seen in the long grass by the river.|Mind yourself out there.",
    "NORTH": "The road north to ENNISCORTHY isn't finished yet.",
    "SOUTH": "The road south to HOOK HEAD isn't finished yet.",
    "EAST": "The road east to WEXFORD TOWN isn't finished yet.",
    "WEST": "The bridge to KILKENNY is closed for repairs.",
    "INTRO": "CIARA: Go on, @! Your pack is on the table.|The last card is always a shiny, and "
             "whatever's on it becomes your partner. That's the rule!",
    "PACK": "",
    "PACK_AGAIN": "Open another pack? Your partner may change.|Press A to open it, or B to leave it.",
    "GOT": "@'s partner is $! Look after each other.",
    "MOM0": "MOM: Open your pack first, @. The lads are waiting!",
    "MOM1": "MOM: $ suits you! Your brother ALEX was asking for you. He went up the north road.|"
            "Ring me if you need anything. And mind yourself in the long grass!",
    "CIARA0": "CIARA: Go on, open it! I can't look.",
    "CIARA1": "CIARA: A shiny $! I only got a Raindrop. Again.",
    "OISIN0": "OISIN: I'm saving mine for after the tea.",
    "OISIN1": "OISIN: ALEX says the WEXFORD gym leader is no joke. Train up first!",
    "TV": "On the telly: 'IRELAND names its squad for the WORLD CUP!'",
    "KETTLE": "The kettle is on. It is always on.",
}
TXT = {k: i for i, k in enumerate(TEXTS)}

# npc: (x, y, frame, flip, pal, text before starter, text after)
MAPS = [
    dict(name="TOWN", pals="bg_pals", edges=("NORTH", "SOUTH", "EAST", "WEST"), rows=[
        "~~~QTTTT==TTTTTT",
        "~~~Q....==.,,,,T",
        "BBB=======.,,,,T",
        "~~~QSF..==S.,,,T",
        "~12QR+++==.....T",
        "~34Q++++==.R+++T",
        "~56Q++++==.++++T",
        "~~~Q.=..==.++++T",
        "~~~Q============",
        "~~~Q.F..==..F..T",
        "~~~QWWW.==.U+++T",
        "~~~Q,,,.==.++++T",
        "~~~Q,,,,==.++++T",
        "~~~Q,,,,=====..T",
        "~~~Q,,,,==..F..T",
        "~~~QTTTT==TTTTTT"],
        ints=[(10, 3, "TOWN"), (4, 3, "SHIP")],
        npcs=[(7, 9, F_OLD, 0, 1, "NPC", "NPC")],
        warps=[(12, 12, "HOME", 4, 7)]),
    dict(name="HOME", pals="in_pals", edges=None, rows=[
        "^^^^^^^^^^",
        "#o##o##o##",
        "v______CK_",
        "__________",
        "___rrrr___",
        "___rptr___",
        "___rrrr___",
        "__________",
        "____m_____"],
        ints=[(4, 5, "PACK"), (0, 2, "TV"), (8, 2, "KETTLE"), (7, 2, "KETTLE")],
        npcs=[(8, 3, F_MOM, 0, 4, "MOM0", "MOM1"), (3, 5, F_GIRL, 0, 2, "CIARA0", "CIARA1"),
              (6, 5, F_BOY, 0, 3, "OISIN0", "OISIN1")],
        warps=[(4, 8, "TOWN", 12, 13)]),
]
MAP_ID = {m["name"]: i for i, m in enumerate(MAPS)}
for m in MAPS:
    m["w"], m["h"], m["ids"] = compile_map(m["rows"])
assert len(tiles) <= 160 and len(metatiles) <= 255, (len(tiles), len(metatiles))

def wrap(text):
    """Word-wrap to the 18x2 dialog box: \\n = second line, \\f = new page.
    @ = player name, $ = partner name (both reserve 7 characters)."""
    text = text.replace("@", "@" * 7).replace("$", "$" * 7)
    pages = []
    for para in text.split("|"):
        lines = textwrap.wrap(para, 18)
        pages += ["\\n".join(lines[i:i + 2]) for i in range(0, len(lines), 2)]
    return re.sub(r"([@$])\1+", r"\1", "\\f".join(pages))

# ---------------------------------------------------------------- emit
def carr(vals, per=16):
    vals = list(vals)
    return ",\n".join("  " + ",".join(str(v) for v in vals[i:i + per]) for i in range(0, len(vals), per))
def pals(name, sets):
    return f"const palette_color_t {name}[] = {{\n" + carr((rgb(x) for p in sets for x in p), 4) + "\n};"
def rows_of(fmt, items):
    return ",".join(fmt % i for i in items) if items else "{0}"

h = ["#ifndef ASSETS_H", "#define ASSETS_H", "#include <gb/gb.h>", "#include <gb/cgb.h>",
     f"#define TILE_BASE {TILE_BASE}", f"#define N_TILES {len(tiles)}",
     f"#define N_SPR_TILES {len(spr)}", f"#define SPARK_TILE {SPARK_TILE}", f"#define WATER_TILE {WATER_TILE}",
     f"#define F_SOLID {SOLID}", f"#define F_DOOR {DOOR}", f"#define F_GRASS {GRASS}",
     f"#define P_UI {P_UI}", "#define NO_TEXT 255"]
h += [f"#define K_{k} {v}" for k, v in dict(DARK=K_DARK, CARD=K_CARD, FOIL=K_FOIL, SHINY=K_SHINY).items()]
h += [f"#define FR_{k} {v}" for k, v in FR.items()] + [f"#define PK_{k} {v}" for k, v in PK.items()]
h += [f"#define TXT_{k} {i}" for k, i in TXT.items()] + [f"#define MAP_{k} {i}" for k, i in MAP_ID.items()]
h += ["typedef struct { uint8_t x, y, text; } interact_t;",
      "typedef struct { uint8_t x, y, frame, flip, pal, text0, text1; } npc_t;",
      "typedef struct { uint8_t x, y, map, tx, ty; } warp_t;",
      "typedef struct { uint8_t w, h; const uint8_t *data; const palette_color_t *pals;",
      "  uint8_t n_int; const interact_t *ints; uint8_t n_npc; const npc_t *npcs;",
      "  uint8_t n_warp; const warp_t *warps; uint8_t edge[4]; } map_t;",
      "typedef struct { const char *name; const char *type; uint8_t pal; } card_t;",
      "extern const uint8_t bg_tiles[], spr_tiles[], water_anim[2][16];",
      "extern const uint8_t starter_art[3][1024], icon_art[3][256];",
      "extern const card_t starter_cards[3], icon_cards[3];",
      "extern const palette_color_t bg_pals[], in_pals[], pack_pals[], obj_pals[];",
      "extern const uint8_t mt_tiles[][4], mt_attr[][4], mt_flags[];",
      "extern const map_t maps[];", "extern const char * const texts[];",
      "#endif"]
c = ['#include "assets.h"',
     "const uint8_t bg_tiles[] = {\n" + carr(v for t in tiles for v in to2bpp(t)) + "\n};",
     "const uint8_t spr_tiles[] = {\n" + carr(v for t in spr for v in to2bpp(t)) + "\n};",
     "const uint8_t water_anim[2][16] = {{" + ",".join(map(str, to2bpp(water[0:8, 0:8]))) +
     "},{" + ",".join(map(str, to2bpp(water_b))) + "}};",
     "const uint8_t starter_art[3][1024] = {\n" + ",\n".join("{\n" + carr(tiles2bpp(s[2])) + "\n}" for s in STARTERS) + "\n};",
     "const uint8_t icon_art[3][256] = {\n" + ",\n".join("{\n" + carr(tiles2bpp(s[1])) + "\n}" for s in ICONS) + "\n};",
     "const card_t starter_cards[3] = {" + ",".join('{"%s","%s",%d}' % (s[0], s[1], s[3]) for s in STARTERS) + "};",
     "const card_t icon_cards[3] = {" + ",".join('{"%s","ENERGY",%d}' % (s[0], s[2]) for s in ICONS) + "};",
     pals("bg_pals", BG_PALS), pals("in_pals", IN_PALS), pals("pack_pals", PACK_PALS), pals("obj_pals", OBJ_PALS),
     "const uint8_t mt_tiles[][4] = {\n" + ",\n".join("  {%d,%d,%d,%d}" % tuple(m[0]) for m in metatiles) + "\n};",
     "const uint8_t mt_attr[][4] = {\n" + ",\n".join("  {%d,%d,%d,%d}" % tuple(m[1]) for m in metatiles) + "\n};",
     "const uint8_t mt_flags[] = {" + ",".join(str(m[2]) for m in metatiles) + "};"]
for i, m in enumerate(MAPS):
    ints = [(x, y, TXT[t]) for x, y, t in m["ints"]]
    npcs = [(x, y, f, fl, p, TXT[a], TXT[b]) for x, y, f, fl, p, a, b in m["npcs"]]
    warps = [(x, y, MAP_ID[t], tx, ty) for x, y, t, tx, ty in m["warps"]]
    c += [f"static const uint8_t m{i}_data[] = {{\n" + carr(m["ids"]) + "\n};",
          f"static const interact_t m{i}_int[] = {{" + rows_of("{%d,%d,%d}", ints) + "};",
          f"static const npc_t m{i}_npc[] = {{" + rows_of("{%d,%d,%d,%d,%d,%d,%d}", npcs) + "};",
          f"static const warp_t m{i}_warp[] = {{" + rows_of("{%d,%d,%d,%d,%d}", warps) + "};"]
    m["c"] = "{%d,%d,m%d_data,%s,%d,m%d_int,%d,m%d_npc,%d,m%d_warp,{%s}}" % (
        m["w"], m["h"], i, m["pals"], len(ints), i, len(npcs), i, len(warps), i,
        ",".join(str(TXT[e]) for e in m["edges"]) if m["edges"] else "255,255,255,255")
c += ["const map_t maps[] = {\n  " + ",\n  ".join(m["c"] for m in MAPS) + "\n};",
      "const char * const texts[] = {\n" + ",\n".join('  "%s"' % wrap(t) for t in TEXTS.values()) + "\n};"]
open(f"{OUT}/assets.h", "w").write("\n".join(h) + "\n")
open(f"{OUT}/assets.c", "w").write("\n".join(c) + "\n")

# preview sheet of the card art, for eyeballing
if len(sys.argv) > 2:
    sheet = Image.new("RGB", (64 * 6, 64), "white")
    for i, (px, pal) in enumerate([(s[2], s[3]) for s in STARTERS] + [(s[1], s[2]) for s in ICONS]):
        cols = [tuple(int(PACK_PALS[pal][v][j:j + 2], 16) for j in (1, 3, 5)) for v in range(4)]
        im = Image.fromarray(np.array(cols, np.uint8)[px])
        sheet.paste(im, (i * 64, 0))
    sheet.resize((64 * 6 * 4, 256), 0).save(sys.argv[2])
print(f"{len(tiles)} bg tiles, {len(metatiles)} metatiles, {len(spr)} sprite tiles")

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
    ["#f8f8f0", "#78c850", "#2f7038", "#181818"],  # grass art: white, hue, shade, line
    ["#f8f8f0", "#f08030", "#a03818", "#181010"],  # fire art
    ["#f8f8f0", "#5898e0", "#28488c", "#101020"],  # water art
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
    ["#000000", "#f8f8f8", "#f8d030", "#f8a020"],  # sparkle, butterfly
    ["#000000", "#70c048", "#388830", "#184818"],  # long grass over the player's legs
    ["#000000", "#f8f8f8", "#c8f0b0", "#388830"],  # whirling breeze
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

def shear(px, rows):      # lean the top of a tile one pixel to the right
    out = px.copy(); out[:rows] = np.roll(px[:rows], 1, axis=1); return out
SWAY = {",": np.roll(tall, 1, axis=1), "T": shear(tree, 8), "F": np.roll(flower, 1, axis=1)}
sway_of = {}
for ch, px in SWAY.items():
    _, pal, flags = mt_src[ch]
    sway_of[mt_char[ch]] = mt_id(px, pal, flags)

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
BODY = ["....33311333....", "..312221122213..", "..312221122213..", "..332221122233..",
        "....32222223....", "....3113.3113...", "....3333.3333..."]
FACE = ["...3311111133...", "...3131111313...", "...3111311113...", "....31111113...."]
hero_d = [".....333333.....", "....32112223....", "...3211222223...", "...3222222223...",
          "..333333333333.."] + FACE + BODY
hero_u = [".....333333.....", "....32222223....", "...3222222223...", "...3222222223...",
          "...3222222223...", "...3333333333...", "...3333333333...", "...3113333113...",
          "....33333333....", "...3322222233...", "..312233332213..", "..312231132213..",
          "..332233332233.."] + BODY[4:]
hero_l = [".....333333.....", "....32112223....", "...3211222223...", "..33222222223...",
          "3333332222223...", "...3111133333...", "...3131113333...", "..31111111333...",
          "...33111113.....", "....33322233....", "....32212223....", "....32112223....",
          "....33222233....", ".....322223.....", "......3113......", "......3333......"]
girl = [".....333333.....", "....33333333....", "...3333333333...", "...3333333333...",
        "...3331111333...", "...3311111133...", "..331311113133..", "..331113111133..",
        "..333111111333..", "...3333113333...", "..312221122213..", "..312221122213..",
        "..332221122233..", "...3222222223...", "....3113.3113...", "....3333.3333..."]
boy = ["....3.33.33.3...", "....33333333....", "...3333333333...", "...3333333333...",
       "...3331331333..."] + FACE + BODY
mom = ["......3333......", ".....333333.....", "....33333333....", "...3333333333...",
       "...3333113333...", "...3311111133...", "...3131111313...", "...3111311113...",
       "....31111113....", "....33311333....", "..312211112213..", "..312211112213..",
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
DRUM_BODY = ["....33311333....", "..3333.3222213..", ".3111133222213..", ".3111132222233..",
             "..3333.3222223..", "....3113.3113...", "....3333.3333..."]
drum_a = oldman[:9] + DRUM_BODY
drum_b = oldman[:9] + DRUM_BODY[:2] + [".3113133222213..", ".3131132222233.."] + DRUM_BODY[4:]
frames += [art(drum_a), art(drum_b)]
F_DRUM = 12
spr = []
for f in frames:
    for x in (0, 8):
        spr += [f[0:8, x:x + 8], f[8:16, x:x + 8]]
over_b = np.zeros((16, 16), np.uint8); over_b[8:16] = tall[4:12]       # waist-deep blades
over_b[13:16][over_b[13:16] == 0] = 1
over_a = np.zeros((16, 16), np.uint8); over_a[7:15] = np.roll(tall[4:12], 2, axis=1)
over_a[13:16][over_a[13:16] == 0] = 1
for x, y in ((2, 4), (3, 3), (11, 2), (12, 3), (7, 5), (14, 5), (0, 6), (8, 1)):   # flying bits
    over_a[y, x] = 3
whirl = np.zeros((16, 16), np.uint8)       # a spiral of air with a few leaves caught in it
for i in range(140):
    t = i / 139 * 2.3 * 2 * np.pi
    r = 1.2 + 6.2 * i / 139
    x, y = 7.5 + r * np.cos(t), 7.5 + r * np.sin(t)
    whirl[int(round(y)) % 16, int(round(x)) % 16] = 1
    if r > 3.5:
        whirl[int(round(y + 0.7)) % 16, int(round(x + 0.7)) % 16] = 1
for x, y in ((2, 3), (12, 2), (13, 12), (4, 13)):
    whirl[y:y + 2, x:x + 2] = 3; whirl[y, x + 1] = 2
F_GRASS_A, F_GRASS_B = len(frames), len(frames) + 1
F_WHIRL_A, F_WHIRL_B = len(frames) + 2, len(frames) + 3
for f in (over_a, over_b, whirl, np.rot90(whirl)):
    for x in (0, 8):
        spr += [f[0:8, x:x + 8], f[8:16, x:x + 8]]
SPARK_TILE = len(spr)
blank8 = np.zeros((8, 8), np.uint8)
spr += [art(["...1....", "...1....", "..121...", "1122211.", "..121...", "...1....", "...1....", "........"], 8), blank8,
        art(["........", "........", "...1....", "..121...", "...1....", "........", "........", "........"], 8), blank8]
BFLY_TILE = len(spr)
spr += [art(["........", "22...22.", "212.212.", "2112112.", ".21312..", ".2112...", "..2.2...", "........"], 8), blank8,
        art(["........", "...2....", "..212...", "..213...", "..212...", "...2....", "........", "........"], 8), blank8]

# ---------------------------------------------------------------- card art
# Creature art follows a few rules, taken from studying good 8-bit monster sprites:
#  - four tones only: white, one hue, a darker shade of it, and black line
#  - white is both the paper and the brightest part of the creature
#  - shadow is laid down as solid shapes on the lower right, with at most a
#    one-pixel dither where it meets the lit side; never noise
#  - limbs on the far side are drawn in the shade colour, which gives depth
#  - a few small white glints on the upper left of the big forms
#  - a pose with attitude: weight on two feet, a raised paw, a narrowed eye
# Shapes are drawn with 1 hue, 2 shade, 3 line, 4 white; finish() adds the shadow.
def canvas(n):
    im = Image.new("L", (n, n), 0)
    return im, ImageDraw.Draw(im)

def finish(im):
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
            if v not in (1, 2, 4):
                continue
            s = min(run(y, x, 1, 1, 8), run(y, x, 1, 0, 8), run(y, x, 0, 1, 8))
            t = min(run(y, x, -1, -1, 5), run(y, x, -1, 0, 5), run(y, x, 0, -1, 5))
            if t <= 3:                       # too thin to shade
                continue
            ch = (x + y) % 2 == 0
            if v == 1:
                if s <= 5: out[y, x] = 2
                elif s == 6 and ch: out[y, x] = 2
            elif v == 4:
                if s <= 3: out[y, x] = 1
                elif s == 4 and ch: out[y, x] = 1
            elif s <= 3:
                out[y, x] = 3
    out[out == 4] = 0
    return out

def boveen():           # grass: a bog calf up on its hind legs, hooves raised
    im, d = canvas(64); E = d.ellipse; P = d.polygon
    d.line([(44, 50), (54, 50), (58, 44)], fill=3, width=3)                 # tail with a clover
    for cx, cy in ((59, 38), (55, 42), (62, 43)):
        E((cx - 3, cy - 3, cx + 3, cy + 3), fill=1, outline=3)
    P([(10, 52), (26, 50), (27, 62), (8, 62)], fill=4, outline=3); d.rectangle((8, 58, 27, 62), fill=3)
    P([(36, 50), (52, 52), (54, 62), (35, 62)], fill=4, outline=3); d.rectangle((35, 58, 54, 62), fill=3)
    E((13, 26, 49, 58), fill=4, outline=3)                                  # body
    P([(46, 33), (55, 25), (58, 17), (63, 22), (59, 31), (50, 40)], fill=2, outline=3)   # far arm
    E((54, 12, 63, 22), fill=3)
    d.chord((13, 24, 49, 48), 180, 360, fill=1, outline=3)                  # moss mantle
    for cx in range(17, 48, 6):
        E((cx - 4, 32, cx + 4, 41), fill=1)
    P([(16, 36), (6, 30), (2, 23), (9, 20), (13, 27), (20, 31)], fill=4, outline=3)      # near arm
    E((0, 15, 10, 25), fill=2, outline=3)
    P([(18, 11), (9, 3), (14, 0), (18, 5), (23, 8)], fill=1, outline=3)     # fern horns
    P([(46, 11), (55, 3), (50, 0), (46, 5), (41, 8)], fill=1, outline=3)
    P([(15, 14), (4, 11), (8, 20), (16, 20)], fill=1, outline=3)            # leaf ears
    P([(49, 14), (60, 11), (56, 20), (48, 20)], fill=1, outline=3)
    E((13, 4, 51, 33), fill=4, outline=3)                                   # head
    for cx, cy in ((32, 8), (28, 12), (36, 12)):
        E((cx - 3, cy - 3, cx + 3, cy + 3), fill=1)
    E((19, 19, 45, 35), fill=1, outline=3)                                  # muzzle
    E((24, 24, 28, 29), fill=3); E((36, 24, 40, 29), fill=3)
    d.line([(27, 32), (34, 33), (39, 31)], fill=3)
    for x in (19, 37):                                                      # heavy-lidded eyes
        d.chord((x, 12, x + 8, 21), 0, 180, fill=3); d.point((x + 2, 18), fill=4)
    d.line([(17, 14), (28, 17)], fill=3, width=2); d.line([(47, 14), (36, 17)], fill=3, width=2)
    E((17, 7, 21, 9), fill=4); E((22, 44, 26, 47), fill=4)
    return finish(im)

def ruakit():           # fire: a prowling fox with a flame mane and tail
    im, d = canvas(64); E = d.ellipse; P = d.polygon
    P([(48, 42), (56, 34), (53, 24), (58, 14), (61, 3), (63, 20), (63, 36), (60, 46), (52, 50)], fill=1, outline=3)
    P([(54, 40), (58, 32), (57, 24), (60, 15), (61, 28), (60, 40), (56, 45)], fill=4)
    P([(44, 44), (53, 44), (56, 60), (47, 60)], fill=2, outline=3); d.rectangle((47, 57, 56, 60), fill=3)
    P([(27, 42), (34, 42), (34, 60), (28, 60)], fill=2, outline=3); d.rectangle((28, 57, 34, 60), fill=3)
    E((20, 26, 54, 50), fill=1, outline=3)
    E((36, 26, 58, 52), fill=1, outline=3)
    P([(38, 46), (47, 44), (48, 60), (39, 60)], fill=1, outline=3); d.rectangle((39, 57, 48, 60), fill=3)
    P([(18, 40), (26, 40), (25, 60), (17, 60)], fill=1, outline=3); d.rectangle((17, 57, 25, 60), fill=3)
    for pts in ([(28, 28), (31, 15), (35, 27)], [(35, 27), (40, 14), (43, 27)], [(43, 28), (48, 17), (50, 30)]):
        P(pts, fill=4, outline=3)                                           # flame mane
    P([(13, 34), (16, 43), (20, 38), (23, 47), (27, 40), (29, 48), (32, 36), (22, 30)], fill=4, outline=3)
    P([(24, 16), (29, 1), (33, 19)], fill=2, outline=3)
    P([(15, 17), (14, 0), (25, 13)], fill=1, outline=3); P([(17, 13), (17, 6), (22, 12)], fill=2)
    P([(3, 31), (9, 21), (20, 13), (31, 17), (35, 29), (30, 38), (14, 39)], fill=1, outline=3)
    P([(4, 32), (14, 39), (30, 38), (33, 32), (20, 31), (12, 29)], fill=4)
    P([(30, 33), (38, 35), (32, 39), (36, 44), (27, 41)], fill=4, outline=3)
    E((1, 28, 6, 33), fill=3)
    d.line([(6, 34), (13, 36)], fill=3)
    P([(9, 35), (12, 36), (10, 39)], fill=4, outline=3)                     # fang
    P([(11, 25), (21, 22), (20, 28), (14, 28)], fill=4, outline=3)          # narrow slit eye
    d.line([(16, 23), (16, 28)], fill=3, width=2)
    d.line([(9, 23), (22, 19)], fill=3, width=2)
    P([(40, 36), (43, 32), (46, 36), (43, 40)], fill=4); P([(30, 36), (32, 33), (34, 36), (32, 39)], fill=4)
    E((40, 29, 46, 31), fill=4); E((22, 16, 26, 17), fill=4)
    return finish(im)

def dovran():           # water: a river-hound pup, one paw raised, with a spiral belly
    im, d = canvas(64); E = d.ellipse; P = d.polygon
    P([(46, 52), (56, 46), (55, 33), (60, 40), (63, 27), (63, 46), (58, 56), (48, 60)], fill=2, outline=3)
    E((38, 30, 51, 39), fill=2, outline=3)                                  # far paw
    E((24, 36, 56, 61), fill=1, outline=3)
    E((14, 22, 44, 54), fill=1, outline=3)
    E((19, 28, 37, 52), fill=4); E((30, 44, 48, 58), fill=4)
    d.arc((21, 32, 35, 46), 30, 330, fill=1, width=2); d.arc((25, 36, 31, 42), 200, 500, fill=1)
    P([(16, 36), (8, 30), (1, 20), (6, 16), (12, 24), (20, 30)], fill=1, outline=3)      # raised paw
    for x in (2, 5, 8):
        d.line([(x, 20), (x + 1, 16)], fill=3)
    P([(17, 10), (21, 0), (27, 6), (33, 0), (37, 9)], fill=4, outline=3)    # head crest
    d.line([(22, 3), (24, 9)], fill=3); d.line([(32, 3), (31, 9)], fill=3)
    P([(44, 14), (52, 9), (48, 21)], fill=2, outline=3)
    E((6, 6, 46, 32), fill=1, outline=3)
    E((16, 18, 36, 32), fill=4)
    for x in (9, 32):                                                       # goggle eyes, looking sideways
        E((x, 9, x + 11, 20), fill=4, outline=3); E((x + 1, 12, x + 6, 17), fill=3); d.point((x + 2, 13), fill=4)
        d.line([(x, 11), (x + 11, 10)], fill=3, width=2)
    E((23, 20, 29, 24), fill=3)
    d.line([(20, 28), (26, 30), (33, 27)], fill=3)                          # smirk
    P([(30, 28), (33, 27), (32, 31)], fill=4, outline=3)
    for y0, y1 in ((24, 21), (27, 29)):
        d.line([(37, y0), (49, y1)], fill=3)
    for cx, cy, r in ((56, 12, 4), (60, 22, 2), (8, 54, 3)):                # bubbles
        E((cx - r, cy - r, cx + r, cy + r), fill=4, outline=3)
    E((20, 8, 25, 9), fill=4); E((40, 42, 44, 44), fill=4)
    return finish(im)

def girrin():           # normal: a boxing hare, all ears and feet
    im, d = canvas(64); E = d.ellipse; P = d.polygon
    E((43, 40, 56, 53), fill=4, outline=3)                                  # scut
    E((8, 54, 30, 63), fill=1, outline=3); E((34, 54, 57, 63), fill=1, outline=3)
    P([(44, 34), (52, 28), (54, 22), (60, 25), (56, 33), (48, 39)], fill=2, outline=3)   # far arm
    E((52, 13, 63, 24), fill=2, outline=3)
    E((17, 26, 47, 59), fill=1, outline=3)
    E((23, 34, 41, 57), fill=4)
    P([(21, 35), (10, 31), (7, 22), (14, 20), (18, 27), (25, 31)], fill=1, outline=3)    # near arm
    E((3, 13, 15, 25), fill=4, outline=3)
    P([(22, 14), (16, 2), (20, 0), (27, 3), (30, 13)], fill=1, outline=3)   # ears, one bent
    P([(22, 11), (20, 4), (24, 4), (26, 11)], fill=2)
    P([(34, 13), (38, 2), (45, 0), (53, 7), (50, 10), (44, 6), (41, 14)], fill=1, outline=3)
    E((15, 10, 47, 35), fill=1, outline=3)
    E((22, 23, 40, 35), fill=4)
    for x in (19, 34):                                                      # wide, wild ring eyes
        E((x, 14, x + 9, 23), fill=4, outline=3); d.rectangle((x + 4, 18, x + 5, 19), fill=3)
    P([(29, 23), (33, 23), (31, 26)], fill=3)
    d.rectangle((29, 28, 33, 32), fill=4, outline=3); d.line([(31, 28), (31, 32)], fill=3)
    d.line([(21, 27), (13, 26)], fill=3); d.line([(41, 27), (49, 26)], fill=3)
    E((19, 12, 23, 13), fill=4)
    return finish(im)

def spidge():           # flying: a robin with its wings on its hips
    im, d = canvas(64); E = d.ellipse; P = d.polygon
    d.line([(26, 53), (23, 61)], fill=3, width=2); d.line([(38, 53), (41, 61)], fill=3, width=2)
    d.line([(18, 62), (28, 62)], fill=3); d.line([(36, 62), (46, 62)], fill=3)
    P([(44, 43), (60, 38), (63, 45), (48, 53)], fill=2, outline=3)          # tail
    E((11, 13, 53, 57), fill=2, outline=3)
    E((16, 22, 46, 55), fill=1)                                             # red breast
    d.chord((20, 38, 42, 57), 0, 180, fill=4)
    P([(13, 29), (3, 38), (8, 49), (17, 44)], fill=2, outline=3)            # wings akimbo
    P([(51, 29), (61, 38), (56, 49), (47, 44)], fill=2, outline=3)
    P([(27, 15), (29, 5), (32, 12), (36, 4), (38, 15)], fill=2, outline=3)  # crest
    P([(27, 28), (37, 28), (32, 36)], fill=4, outline=3)                    # beak
    for x in (21, 38):                                                      # beady eyes
        E((x, 20, x + 5, 26), fill=3); d.point((x + 1, 21), fill=4)
    d.line([(18, 18), (28, 21)], fill=3, width=2); d.line([(46, 18), (36, 21)], fill=3, width=2)
    E((17, 16, 21, 17), fill=4)
    return finish(im)

def granog():           # ground: a hedgehog with its arms folded, unimpressed
    im, d = canvas(64); E = d.ellipse; P = d.polygon
    cx, cy = 35, 35
    for k in range(14):                                                     # a ring of spines
        t = -2.6 + k * 0.42
        bx, by = cx + 21 * np.cos(t), cy + 22 * np.sin(t)
        P([(bx - 5 * np.sin(t), by + 5 * np.cos(t)), (bx + 5 * np.sin(t), by - 5 * np.cos(t)),
           (cx + 31 * np.cos(t), cy + 32 * np.sin(t))], fill=2, outline=3)
    E((15, 13, 55, 59), fill=2, outline=3)
    E((16, 24, 44, 60), fill=1, outline=3)                                  # face and front
    E((23, 38, 41, 58), fill=4)
    E((18, 55, 31, 63), fill=1, outline=3); E((34, 55, 47, 63), fill=1, outline=3)
    P([(19, 29), (6, 36), (19, 41)], fill=1, outline=3)                     # snout
    E((4, 33, 10, 39), fill=3)
    E((29, 17, 37, 25), fill=1, outline=3)
    d.line([(18, 26), (28, 29)], fill=3, width=2)                           # a heavy brow over a small eye
    E((21, 29, 25, 33), fill=3)
    P([(21, 41), (42, 36), (44, 41), (23, 46)], fill=1, outline=3)          # folded arms
    P([(21, 37), (41, 42), (41, 47), (21, 42)], fill=1, outline=3)
    E((40, 18, 44, 20), fill=4)
    return finish(im)

def faolan():           # dark: a wolf pup with a hood of dark fur and a crescent on its chest
    im, d = canvas(64); E = d.ellipse; P = d.polygon
    P([(44, 46), (58, 37), (63, 44), (60, 55), (48, 59)], fill=2, outline=3)
    P([(58, 37), (63, 44), (61, 49), (55, 43)], fill=4, outline=3)
    E((17, 28, 49, 61), fill=1, outline=3)
    E((24, 35, 41, 54), fill=4); E((28, 32, 46, 50), fill=1)                # crescent
    E((19, 52, 30, 63), fill=1, outline=3); E((35, 52, 46, 63), fill=1, outline=3)
    for x in (22, 25, 38, 41):
        d.line([(x, 59), (x, 62)], fill=3)
    P([(13, 17), (10, 0), (27, 10)], fill=2, outline=3); P([(51, 17), (54, 0), (37, 10)], fill=2, outline=3)
    P([(15, 13), (14, 5), (22, 10)], fill=1); P([(49, 13), (50, 5), (42, 10)], fill=1)
    P([(14, 33), (19, 43), (25, 37), (32, 45), (39, 37), (45, 43), (50, 33)], fill=2, outline=3)   # ruff
    E((9, 8, 55, 39), fill=1, outline=3)
    d.chord((9, 8, 55, 39), 180, 360, fill=2, outline=3)                    # the hood
    P([(23, 25), (41, 25), (37, 38), (27, 38)], fill=4)
    for pts, px in (([(15, 21), (26, 24), (25, 27), (17, 26)], 21), ([(49, 21), (38, 24), (39, 27), (47, 26)], 42)):
        P(pts, fill=4, outline=3); d.line([(px, 23), (px, 26)], fill=3, width=2)      # narrow eyes
    d.line([(44, 13), (48, 30)], fill=4, width=2)                           # an old scar
    E((29, 28, 35, 32), fill=3)
    d.line([(32, 32), (32, 34)], fill=3); d.line([(27, 35), (32, 34), (37, 35)], fill=3)
    P([(35, 35), (38, 35), (37, 39)], fill=4, outline=3)
    E((16, 12, 20, 13), fill=4)
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

# ---------------------------------------------------------------- creatures, moves, types
TYPES = ["NORMAL", "FIRE", "WATER", "GRASS", "ELECTRIC", "ICE", "FIGHTING", "POISON", "GROUND",
         "FLYING", "PSYCHIC", "BUG", "ROCK", "GHOST", "DRAGON", "DARK", "STEEL"]
SPECIAL = {"FIRE", "WATER", "GRASS", "ELECTRIC", "ICE", "PSYCHIC", "DRAGON", "DARK"}
# attacker: (strong against, weak against, no effect on)
CHART = {
    "NORMAL": ("", "ROCK STEEL", "GHOST"),
    "FIRE": ("GRASS ICE BUG STEEL", "FIRE WATER ROCK DRAGON", ""),
    "WATER": ("FIRE GROUND ROCK", "WATER GRASS DRAGON", ""),
    "GRASS": ("WATER GROUND ROCK", "FIRE GRASS POISON FLYING BUG DRAGON STEEL", ""),
    "ELECTRIC": ("WATER FLYING", "ELECTRIC GRASS DRAGON", "GROUND"),
    "ICE": ("GRASS GROUND FLYING DRAGON", "FIRE WATER ICE STEEL", ""),
    "FIGHTING": ("NORMAL ICE ROCK DARK STEEL", "POISON FLYING PSYCHIC BUG", "GHOST"),
    "POISON": ("GRASS", "POISON GROUND ROCK GHOST", "STEEL"),
    "GROUND": ("FIRE ELECTRIC POISON ROCK STEEL", "GRASS BUG", "FLYING"),
    "FLYING": ("GRASS FIGHTING BUG", "ELECTRIC ROCK STEEL", ""),
    "PSYCHIC": ("FIGHTING POISON", "PSYCHIC STEEL", "DARK"),
    "BUG": ("GRASS PSYCHIC DARK", "FIRE FIGHTING POISON FLYING GHOST STEEL", ""),
    "ROCK": ("FIRE ICE FLYING BUG", "FIGHTING GROUND STEEL", ""),
    "GHOST": ("PSYCHIC GHOST", "DARK STEEL", "NORMAL"),
    "DRAGON": ("DRAGON", "STEEL", ""),
    "DARK": ("PSYCHIC GHOST", "FIGHTING DARK STEEL", ""),
    "STEEL": ("ICE ROCK", "FIRE WATER ELECTRIC STEEL", ""),
}
# move: name (max 7), type, power, accuracy, effect (0 damage, 1 lowers ATTACK, 2 lowers DEFENSE)
MOVES = [("-", "NORMAL", 0, 0, 0), ("TACKLE", "NORMAL", 35, 95, 0), ("SCRATCH", "NORMAL", 40, 100, 0),
         ("BELLOW", "NORMAL", 0, 100, 1), ("GLARE", "NORMAL", 0, 100, 2), ("LEAFCUT", "GRASS", 45, 100, 0),
         ("CINDER", "FIRE", 40, 100, 0), ("SPLASH", "WATER", 40, 100, 0), ("PECK", "FLYING", 35, 100, 0),
         ("SODKICK", "GROUND", 40, 95, 0), ("NIP", "DARK", 40, 100, 0)]
MOVE_ID = {m[0]: i for i, m in enumerate(MOVES)}
# species: name, type, art, palette, (hp, atk, def, spd, spc), exp yield, catch rate, learnset
SPECIES = [
    ("BOVEEN", "GRASS", boveen(), ["#f8f8f0", "#78c850", "#2f7038", "#181818"], (50, 49, 55, 40, 55), 64, 45,
     [(1, "TACKLE"), (1, "BELLOW"), (7, "LEAFCUT")]),
    ("RUAKIT", "FIRE", ruakit(), ["#f8f8f0", "#f08030", "#a03818", "#181010"], (39, 52, 43, 65, 55), 64, 45,
     [(1, "SCRATCH"), (1, "GLARE"), (7, "CINDER")]),
    ("DOVRAN", "WATER", dovran(), ["#f8f8f0", "#5898e0", "#28488c", "#101020"], (46, 50, 50, 50, 52), 64, 45,
     [(1, "TACKLE"), (1, "BELLOW"), (7, "SPLASH")]),
    ("GIRRIN", "NORMAL", girrin(), ["#f8f8f0", "#d0a868", "#805830", "#181010"], (35, 46, 35, 60, 30), 50, 220,
     [(1, "TACKLE"), (4, "GLARE")]),
    ("SPIDGE", "FLYING", spidge(), ["#f8f8f0", "#e86838", "#705038", "#181010"], (38, 42, 35, 56, 35), 52, 220,
     [(1, "PECK"), (5, "BELLOW")]),
    ("GRANOG", "GROUND", granog(), ["#f8f8f0", "#d0a060", "#684828", "#181010"], (42, 48, 60, 30, 30), 58, 190,
     [(1, "TACKLE"), (4, "SODKICK")]),
    ("FAOLAN", "DARK", faolan(), ["#f8f8f0", "#8090b0", "#343c58", "#101018"], (45, 55, 42, 62, 52), 70, 45,
     [(1, "SCRATCH"), (1, "GLARE"), (6, "NIP")]),
]
STARTERS = [(s[0], s[1], s[2], k) for s, k in zip(SPECIES[:3], (K_GRASS, K_FIRE, K_WATER))]
bar_tiles = []
for k in range(9):          # HP bar segments, 0..8 pixels filled
    t = np.zeros((8, 8), np.uint8); t[1, :] = 3; t[6, :] = 3; t[2:6, :] = 2; t[2:6, :k] = 1
    bar_tiles.append(t)
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
        rag = np.array([(i * 7) % 5 < 2 for i in range(16)])      # one edge pattern everywhere keeps the tile count down
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
    "NPC": "Well, @! Wild PMONs were seen in the long grass by the river.|With one of your own you'll be grand.",
    "NORTH": "The road north to ENNISCORTHY isn't finished yet.",
    "ROUTE1": "ROUTE 1|North: ENNISCORTHY. South: NEW ROSS.",
    "DRUM": "SEAMUS: Hear that? Years back I played this bodhran on the quay at dusk...|"
            "...and something answered from the river. Big as a horse, and shining like the moon.|"
            "A mythical PMON, I'd swear to it. It never came again. But I keep playing.",
    "ALEX0": "ALEX: Well, look who finally got a PMON. $, is it? Cute.|"
             "Mom said to mind you. Let's see if you can mind yourself!",
    "ALEX1": "ALEX: ...Not bad. Don't let it go to your head.|Here. You'll run out fast if you throw like that.|"
             "@ got 5 PBALLs!|"
             "ALEX: WEXFORD is north, past ENNISCORTHY. The gym leader won't go easy on you either. See you on the road.",
    "SOUTH": "The road south to HOOK HEAD isn't finished yet.",
    "EAST": "The road east to WEXFORD TOWN isn't finished yet.",
    "WEST": "The bridge to KILKENNY is closed for repairs.",
    "INTRO": "CIARA: Go on, @! Your pack is on the table.|The last card is always a shiny, and "
             "whatever's on it becomes your partner. That's the rule!",
    "PACK": "",
    "PACK_AGAIN": "Open another pack? Your partner may change.|Press A to open it, or B to leave it.",
    "GOT": "@'s partner is $! Look after each other.",
    "MOM0": "MOM: Open your pack first, @. The lads are waiting!",
    "MOM1": "MOM: $ suits you! Sit down a minute and I'll look after your PMONs.|"
            "Your brother ALEX was asking for you. He went up the north road.",
    "MOM_TORCS": "MOM: And take these. Five PBALLs, for catching wild PMONs. Don't lose them!",
    "HEALED": "Your PMONs are full of beans again!",
    "BLACKOUT": "@ has no PMON left that can fight! @ hurried home...",
    "SAVED": "@ saved the game.",
    "PACK_DONE": "Only empty wrappers left.",
    "CIARA0": "CIARA: Go on, open it! I can't look.",
    "CIARA1": "CIARA: A shiny $! I only got a Raindrop. Again.",
    "OISIN0": "OISIN: I'm saving mine for after the tea.",
    "OISIN1": "OISIN: ALEX says the WEXFORD gym leader is no joke. Train up first!",
    "TV": "On the telly: 'IRELAND names its squad for the WORLD CUP!'",
    "KETTLE": "The kettle is on. It is always on.",
}
TXT = {k: i for i, k in enumerate(TEXTS)}

def npc(x, y, frame, pal, t0, t1=None, flip=0, wander=0, script=0, hide=0, anim=0):
    """script: 1 Mom heals, 2 Alex battles, 3 plays the drum. hide: flag bit that removes them."""
    return (x, y, frame, flip, pal, t0, t1 or t0, wander, script, hide, anim)

FLAG_BEAT_ALEX = 4
# wild: (species, lowest level, highest level); edges/conn are in N, S, E, W order
MAPS = [
    dict(name="TOWN", pals="bg_pals", outdoor=1, edges=(None, "SOUTH", "EAST", "WEST"),
         conn=("ROUTE1", None, None, None), wild=[("GIRRIN", 2, 3), ("GIRRIN", 2, 4), ("SPIDGE", 2, 3)], rows=[
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
        npcs=[npc(7, 9, 0, 1, "NPC", wander=1), npc(6, 3, F_DRUM, 2, "DRUM", script=3, anim=1)],
        warps=[(12, 12, "HOME", 4, 7)]),
    dict(name="HOME", pals="in_pals", outdoor=0, edges=(None,) * 4, conn=(None,) * 4, wild=[], rows=[
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
        npcs=[npc(8, 3, F_MOM, 4, "MOM0", "MOM1", script=1), npc(3, 5, F_GIRL, 2, "CIARA0", "CIARA1"),
              npc(6, 5, F_BOY, 3, "OISIN0", "OISIN1")],
        warps=[(4, 8, "TOWN", 12, 13)]),
    dict(name="ROUTE1", pals="bg_pals", outdoor=1, edges=("NORTH", None, None, None),
         conn=(None, "TOWN", None, None), wild=[("GIRRIN", 3, 5), ("SPIDGE", 3, 5), ("GRANOG", 3, 5)], rows=[
        "TTTTTT==TTTTTTTT",
        "T,,,,.==.....TTT",
        "T,,,,.==..FF.TTT",
        "T,,,..==S....,,T",
        "T.....==....,,,T",
        "T..F..===...,,,T",
        "TTT....==..TTTTT",
        "TTTTTT.==.TTTTTT",
        "TTTTTTTT=TTTTTTT",
        "TT,,,..==...TTTT",
        "T,,,,..==.....TT",
        "T,,,,.===..F...T",
        "T.....==~~~~...T",
        "T..F..==~~~~..TT",
        "TT....===....TTT",
        "TTTTTTTT==TTTTTT"],
        ints=[(8, 3, "ROUTE1")],
        npcs=[npc(8, 8, 0, 3, "ALEX0", script=2, hide=FLAG_BEAT_ALEX)],
        warps=[]),
]
MAP_ID = {m["name"]: i for i, m in enumerate(MAPS)}
SP_ID = {sp[0]: i for i, sp in enumerate(SPECIES)}
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
     f"#define N_SPR_TILES {len(spr)}", f"#define SPARK_TILE {SPARK_TILE}", f"#define BFLY_TILE {BFLY_TILE}",
     f"#define F_GRASS_A {F_GRASS_A}", f"#define F_GRASS_B {F_GRASS_B}",
     f"#define F_WHIRL_A {F_WHIRL_A}", f"#define F_WHIRL_B {F_WHIRL_B}", f"#define WATER_TILE {WATER_TILE}",
     f"#define F_SOLID {SOLID}", f"#define F_DOOR {DOOR}", f"#define F_GRASS {GRASS}",
     f"#define P_UI {P_UI}", "#define NO_TEXT 255"]
h += [f"#define K_{k} {v}" for k, v in dict(DARK=K_DARK, CARD=K_CARD, FOIL=K_FOIL, SHINY=K_SHINY).items()]
h += [f"#define FR_{k} {v}" for k, v in FR.items()] + [f"#define PK_{k} {v}" for k, v in PK.items()]
h += [f"#define TXT_{k} {i}" for k, i in TXT.items()] + [f"#define MAP_{k} {i}" for k, i in MAP_ID.items()]
h += ["typedef struct { uint8_t x, y, text; } interact_t;",
      "typedef struct { uint8_t x, y, frame, flip, pal, text0, text1, wander, script, hide, anim; } npc_t;",
      "typedef struct { uint8_t species, lo, hi; } wild_t;", f"#define FLAG_BEAT_ALEX {FLAG_BEAT_ALEX}",
      "typedef struct { uint8_t x, y, map, tx, ty; } warp_t;",
      "typedef struct { uint8_t w, h, outdoor; const uint8_t *data; const palette_color_t *pals;",
      "  uint8_t n_int; const interact_t *ints; uint8_t n_npc; const npc_t *npcs;",
      "  uint8_t n_warp; const warp_t *warps; uint8_t edge[4], conn[4]; uint8_t n_wild; const wild_t *wild; } map_t;",
      "typedef struct { const char *name; const char *type; uint8_t pal; } card_t;",
      "extern const uint8_t bg_tiles[], spr_tiles[], water_anim[2][16];",
      "extern const uint8_t icon_art[3][256], bar_tiles[], type_chart[17][17];",
      "#define ART_BANK 2", "extern const uint8_t species_art[][1024];",
      "typedef struct { char name[8]; uint8_t type, hp, atk, def, spd, spc, yield, rate; uint8_t learn[4][2]; } species_t;",
      "typedef struct { char name[8]; uint8_t type, power, acc, effect; } move_t;",
      "extern const species_t species[]; extern const move_t moves[]; extern const palette_color_t art_pals[][4];",
      "extern const char * const type_names[]; extern const uint8_t type_special[];",
      "extern const card_t starter_cards[3], icon_cards[3];",
      "extern const palette_color_t bg_pals[], in_pals[], pack_pals[], obj_pals[];",
      "extern const uint8_t mt_tiles[][4], mt_attr[][4], mt_flags[], mt_sway[];",
      "extern const map_t maps[];", "extern const char * const texts[];",
      "#endif"]
c = ['#include "assets.h"',
     "const uint8_t water_anim[2][16] = {{" + ",".join(map(str, to2bpp(water[0:8, 0:8]))) +
     "},{" + ",".join(map(str, to2bpp(water_b))) + "}};",
     "const card_t starter_cards[3] = {" + ",".join('{"%s","%s",%d}' % (s[0], s[1], s[3]) for s in STARTERS) + "};",
     "const card_t icon_cards[3] = {" + ",".join('{"%s","ENERGY",%d}' % (s[0], s[2]) for s in ICONS) + "};",
     pals("bg_pals", BG_PALS), pals("in_pals", IN_PALS), pals("pack_pals", PACK_PALS), pals("obj_pals", OBJ_PALS),
     "const uint8_t mt_tiles[][4] = {\n" + ",\n".join("  {%d,%d,%d,%d}" % tuple(m[0]) for m in metatiles) + "\n};",
     "const uint8_t mt_attr[][4] = {\n" + ",\n".join("  {%d,%d,%d,%d}" % tuple(m[1]) for m in metatiles) + "\n};",
     "const uint8_t mt_flags[] = {" + ",".join(str(m[2]) for m in metatiles) + "};",
     "const uint8_t mt_sway[] = {" + ",".join(str(sway_of.get(i, i)) for i in range(len(metatiles))) + "};"]
for i, m in enumerate(MAPS):
    ints = [(x, y, TXT[t]) for x, y, t in m["ints"]]
    npcs = [n[:5] + (TXT[n[5]], TXT[n[6]]) + n[7:] for n in m["npcs"]]
    wild = [(SP_ID[sp], lo, hi) for sp, lo, hi in m["wild"]]
    warps = [(x, y, MAP_ID[t], tx, ty) for x, y, t, tx, ty in m["warps"]]
    c += [f"static const uint8_t m{i}_data[] = {{\n" + carr(m["ids"]) + "\n};",
          f"static const interact_t m{i}_int[] = {{" + rows_of("{%d,%d,%d}", ints) + "};",
          f"static const npc_t m{i}_npc[] = {{" + rows_of("{%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d}", npcs) + "};",
          f"static const wild_t m{i}_wild[] = {{" + rows_of("{%d,%d,%d}", wild) + "};",
          f"static const warp_t m{i}_warp[] = {{" + rows_of("{%d,%d,%d,%d,%d}", warps) + "};"]
    m["c"] = "{%d,%d,%d,m%d_data,%s,%d,m%d_int,%d,m%d_npc,%d,m%d_warp,{%s},{%s},%d,m%d_wild}" % (
        m["w"], m["h"], m["outdoor"], i, m["pals"], len(ints), i, len(npcs), i, len(warps), i,
        ",".join(str(TXT[e]) if e else "255" for e in m["edges"]),
        ",".join(str(MAP_ID[e]) if e else "255" for e in m["conn"]), len(wild), i)
c += ["const map_t maps[] = {\n  " + ",\n  ".join(m["c"] for m in MAPS) + "\n};",
      "const char * const texts[] = {\n" + ",\n".join('  "%s"' % wrap(t) for t in TEXTS.values()) + "\n};"]
def eff(a, dname):
    strong, weak, none = (set(x.split()) for x in CHART[a])
    return 20 if dname in strong else 5 if dname in weak else 0 if dname in none else 10
c += ["const uint8_t type_chart[17][17] = {\n" + ",\n".join(
          "  {" + ",".join(str(eff(a, dn)) for dn in TYPES) + "}" for a in TYPES) + "\n};",
      "const char * const type_names[] = {" + ",".join('"%s"' % t for t in TYPES) + "};",
      "const uint8_t type_special[] = {" + ",".join("1" if t in SPECIAL else "0" for t in TYPES) + "};",
      "const move_t moves[] = {" + ",".join('{"%s",%d,%d,%d,%d}' % (m[0], TYPES.index(m[1]), m[2], m[3], m[4]) for m in MOVES) + "};",
      "const palette_color_t art_pals[][4] = {" + ",".join("{" + ",".join(str(rgb(x)) for x in sp[3]) + "}" for sp in SPECIES) + "};"]
def learn(ls):
    ls = [(l, MOVE_ID[m]) for l, m in ls] + [(0, 0)] * (4 - len(ls))
    return "{" + ",".join("{%d,%d}" % x for x in ls) + "}"
c.append("const species_t species[] = {\n" + ",\n".join(
    '  {"%s",%d,%d,%d,%d,%d,%d,%d,%d,%s}' % ((sp[0], TYPES.index(sp[1])) + sp[4] + (sp[5], sp[6], learn(sp[7])))
    for sp in SPECIES) + "\n};")
h.insert(-1, f"#define N_SPECIES {len(SPECIES)}")
h[-1:-1] = [f"#define T_{t} {i}" for i, t in enumerate(TYPES)] + [f"#define SP_{sp[0]} {i}" for i, sp in enumerate(SPECIES)]
open(f"{OUT}/art.c", "w").write("\n".join([
    "// Graphics live in ROM bank 2; only bank 0 routines may read them.",
    "#pragma bank 2", '#include "assets.h"',
    "const uint8_t species_art[][1024] = {\n" + ",\n".join("{\n" + carr(tiles2bpp(sp[2])) + "\n}" for sp in SPECIES) + "\n};",
    "const uint8_t bg_tiles[] = {\n" + carr(v for t in tiles for v in to2bpp(t)) + "\n};",
    "const uint8_t spr_tiles[] = {\n" + carr(v for t in spr for v in to2bpp(t)) + "\n};",
    "const uint8_t icon_art[3][256] = {\n" + ",\n".join("{\n" + carr(tiles2bpp(s[1])) + "\n}" for s in ICONS) + "\n};",
    "const uint8_t bar_tiles[] = {\n" + carr(v for t in bar_tiles for v in to2bpp(t)) + "\n};"]) + "\n")
open(f"{OUT}/assets.h", "w").write("\n".join(h) + "\n")
open(f"{OUT}/assets.c", "w").write("\n".join(c) + "\n")

# preview sheet of the card art, for eyeballing
if len(sys.argv) > 2:
    sheet = Image.new("RGB", (64 * len(SPECIES), 64), "white")
    for i, (px, pal) in enumerate([(sp[2], sp[3]) for sp in SPECIES]):
        cols = [tuple(int(pal[v][j:j + 2], 16) for j in (1, 3, 5)) for v in range(4)]
        im = Image.fromarray(np.array(cols, np.uint8)[px])
        sheet.paste(im, (i * 64, 0))
    sheet.resize((64 * len(SPECIES) * 4, 256), 0).save(sys.argv[2])
print(f"{len(tiles)} bg tiles, {len(metatiles)} metatiles, {len(spr)} sprite tiles")

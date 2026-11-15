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
def dim(h, k=0.74):                                    # a wet, overcast version of a colour
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % (int(r * k), int(g * k), min(255, int(b * k + 18)))
RAIN_PALS = [[dim(c) for c in p] for p in BG_PALS[:7]] + [UI]
WEX_PALS = [list(p) for p in BG_PALS]
WEX_PALS[P_FLOWER] = ["#f8f0e0", "#e8b830", "#a87818", "#281808"]       # the gym's gold roof (so no flower beds in Wexford)
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
    ["#000000", "#f8f8f8", "#f8c828", "#a84808"],  # sparkle, butterfly, PBalls
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

# Outdoor and indoor maps each get their own set of up to 160 background tiles.
POOL = "out"
tiles = {"out": [], "in": []}
tile_ix = {"out": {}, "in": {}}
# Landmark tiles go in VRAM bank 1 (tiles 128-255), which the overworld otherwise
# leaves empty; battles borrow the same space for creature art. add_tile marks
# them by adding 256, which mt_id turns into the bank bit of the tile's attribute.
EXTRA_MAX = 128
def add_tile(px, pool=None):
    pool = pool or POOL
    key = px.tobytes()
    if pool.startswith("x:"):                   # a landmark: reuse a shared tile where one already matches
        if key in tile_ix["out"]:
            return TILE_BASE + tile_ix["out"][key]
        tiles.setdefault(pool, []); tile_ix.setdefault(pool, {})
        if key not in tile_ix[pool]:
            tile_ix[pool][key] = len(tiles[pool])
            tiles[pool].append(px.copy())
        return 256 + 128 + tile_ix[pool][key]
    if key not in tile_ix[pool]:
        tile_ix[pool][key] = len(tiles[pool])
        tiles[pool].append(px.copy())
    return TILE_BASE + tile_ix[pool][key]
def add_ui(px):             # dialog and card tiles sit at the same index in both sets
    a, b = add_tile(px, "out"), add_tile(px, "in")
    assert a == b
    return a

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
    pals = [p_ | (0x08 if v >= 256 else 0) for p_, v in zip(pals, t)]      # bank-1 tiles
    t = [v & 255 for v in t]
    key = (POOL, tuple(t), tuple(pals), flags)
    if key not in mt_ix:
        mt_ix[key] = len(metatiles)
        metatiles.append((t, pals, flags))
    return mt_ix[key]
def add_mt(ch, px, pal, flags=0):
    assert ch not in mt_char, f"map letter {ch!r} used twice"
    mt_char[ch] = mt_id(px, pal, flags)
    mt_src[ch] = (px, pal, flags)

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
FR = {n: add_ui(frame(*a)) for n, a in {
    "TL": (1, 0, 1, 0), "T": (1, 0, 0, 0), "TR": (1, 0, 0, 1), "L": (0, 0, 1, 0),
    "R": (0, 0, 0, 1), "BL": (0, 1, 1, 0), "B": (0, 1, 0, 0), "BR": (0, 1, 0, 1)}.items()}
FR["ARROW"] = add_ui(art(["........", "........", ".333333.", "..3333..",
                            "...33...", "........", "........", "........"], 8))
foil = np.array([[1 if (x + y) % 8 < 2 else 0 for x in range(8)] for y in range(8)], np.uint8)
crimp = np.array([[3 if (x % 4 in (0, 1)) == (y < 4) else 0 for x in range(8)] for y in range(8)], np.uint8)
gold = np.full((8, 8), 2, np.uint8); gold[0, :] = 3; gold[7, :] = 3
PK = {"FOIL": add_ui(foil), "CRIMP": add_ui(crimp), "GOLD": add_ui(gold)}
FR["BLACK"] = add_ui(np.full((8, 8), 3, np.uint8))
FR["EURO"] = add_ui(art(["........", "...333..", "..3.....", ".3333...", "..3.....", ".3333...", "..3.....", "...333.."], 8))


# ---------------------------------------------------------------- outdoor art
grass = rep(["........", "..1...1.", ".1.1....", "......2.",
             "1.......", "....1.1.", "..2..1..", "........"])
tall = rep(["...2...1", ".2.2..2.", ".212.212", "2212.212",
            "1..2..1.", ".2...2.2", ".21.212.", "221.2122"])
path = rep(["........", "....1...", "........", ".1......",
            "........", "......1.", "..1.....", "........"])
water = rep(["11111111", "11100111", "10011001", "11111111",
             "11111111", "01111110", "10011001", "11111111"])
flower = rep(["........", "..3.....", ".323....", "..3..1..",
              ".....3..", "....323.", ".1...3..", "........"])
tree = np.zeros((16, 16), np.uint8)            # a round crown lit from the top left, on a short trunk
for y in range(13):
    for x in range(16):
        dd = ((x - 7.5) / 7.7) ** 2 + ((y - 6) / 6.5) ** 2
        if dd > 1:
            continue
        lit = (x - 5) + (y - 4) * 1.2           # how far from the light
        v = 0 if lit < -2.5 else 1 if lit < 3 else 2
        if lit > 7: v = 3 if (x + y) % 2 else 2                     # deep shade
        if v == 1 and (x * 5 + y * 3) % 7 == 0: v = 2               # clumps of leaves
        if v == 2 and lit < 6 and (x * 3 + y * 7) % 11 == 0: v = 1
        if v == 0 and (x + y * 2) % 5 == 0: v = 1
        tree[y, x] = 3 if dd > 0.80 else v
tree[12:15, 6:10] = 3; tree[12:14, 7:9] = 2
tree[15, 3:13] = 1; tree[14, 4:6] = 1; tree[14, 10:12] = 1; tree[15, 5:11] = 2
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
    """The Dunbrody from above: a three-masted barque moored at the quay, bow to the north."""
    s = np.full((64, 32), 1, np.uint8)
    def half(y):                                    # half the hull's width at row y
        if y < 3: return 0
        if y < 14: return 2 + (y - 3) * 10 // 11
        if y < 52: return 12
        return max(8, 12 - (y - 52) // 2)
    for y in range(3, 61):
        w = half(y)
        s[y, 16 - w:16 + w] = 2
        s[y, 16 - w] = 3; s[y, 16 + w - 1] = 3
        if w > 3: s[y, 16 - w + 1] = 0; s[y, 16 + w - 2] = 0        # white-painted rails
        if y % 3 == 0 and w > 4: s[y, 16 - w + 3:16 + w - 3] = 3    # deck planking
    s[60, 8:24] = 3
    s[0:4, 15:17] = 3                               # bowsprit
    for my in (12, 25, 48):                         # stays running from each mast down to the rails
        for k in range(2, 9):
            if half(my + k) > 2 + k: s[my + k, 13 - k] = 3; s[my + k, 18 + k] = 3
    for y0, y1, x0, x1 in ((17, 22, 12, 20), (38, 44, 11, 21)):     # deck houses with portholes
        s[y0:y1, x0:x1] = 3; s[y0 + 1:y1 - 1, x0 + 1:x1 - 1] = 0; s[y0 + 2, x0 + 2:x1 - 2:2] = 3
    s[30:35, 13:19] = 3; s[31:34:2, 14:18] = 2      # cargo hatch
    s[54:57, 14:18] = 3; s[55, 15:17] = 0           # the wheel
    for my, wide in ((12, 9), (25, 13), (48, 10)):  # masts, each with a yard and its furled sail
        s[my - 1, 16 - wide:16 + wide] = 3; s[my, 16 - wide:16 + wide] = 0; s[my + 1, 16 - wide:16 + wide] = 3
        s[my, 16 - wide - 1] = 3; s[my, 16 + wide] = 3
        s[my, 16 - wide + 2:16 + wide - 2:4] = 3    # gaskets
        s[my - 2:my + 3, 14:18] = 3; s[my - 1:my + 2, 15:17] = 0
    for y, x in ((8, 2), (21, 0), (35, 29), (46, 0), (57, 28), (62, 13)):     # ripples
        s[y, x:x + 3] = 0
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
POOL = "x:WEXFORD"       # Wexford's landmarks
pike = quay.copy()                              # the Pikeman on his plinth, in the Bullring
pike[12:16, 3:13] = 3; pike[13:15, 4:12] = 2; pike[13, 4:12] = 0
pike[4:12, 6:10] = 3; pike[5:11, 7:9] = 2                       # body
pike[1:4, 6:10] = 3; pike[2, 7:9] = 0                           # head and hat
pike[0:12, 11] = 3; pike[0, 10:13] = 3; pike[1, 11] = 0         # the pike
pike[6, 9:12] = 3                                               # arm
add_mt("P", pike, P_UI, SOLID)

ruin = np.zeros((16, 16), np.uint8)             # a stub of abbey wall, sandstone on grass
for y in range(3, 16):
    ruin[y, 2:14] = 1
ruin[3, 2:5] = 0; ruin[3, 9:11] = 0; ruin[4, 12:14] = 0; ruin[2, 5:9] = 1      # a broken top
ruin[7, 2:14] = 2; ruin[11, 2:14] = 2; ruin[15, 2:14] = 3
for y, xs in ((5, (6, 11)), (9, (4, 9)), (13, (7, 12))):
    for x in xs:
        ruin[y - 1:y + 2, x] = 2
ruin[4:16, 1] = 3; ruin[4:16, 14] = 3; ruin[12:15, 3:5] = 0                     # weeds at the foot
arch = ruin.copy(); arch[6:16, 5:11] = 0                                        # a doorway you can see through
arch[5, 6:10] = 3; arch[6, 5] = 3; arch[6, 10] = 3; arch[6:16, 4] = 3; arch[6:16, 11] = 3
add_mt("x", ruin, P_WOOD, SOLID)
add_mt("y", arch, P_WOOD, SOLID)

boat = np.full((16, 32), 1, np.uint8)           # a mussel boat at its mooring
for y in range(5, 13):
    w = 13 - abs(y - 9) // 2 if y > 6 else 12
    boat[y, 16 - w:16 + w] = 2
    boat[y, 16 - w] = 3; boat[y, 16 + w - 1] = 3
boat[4, 5:27] = 3; boat[13, 6:26] = 3; boat[8, 5:27] = 3
boat[2:8, 12:20] = 3; boat[3:7, 13:19] = 0; boat[4:6, 14:18] = 1               # wheelhouse
boat[6, 22:25] = 0; boat[10, 6:9] = 0; boat[14, 8:24:3] = 0                     # nets, wake
add_mt("7", boat[:, 0:16], P_WATER, SOLID)
add_mt("8", boat[:, 16:32], P_WATER, SOLID)

FONT5 = {"G": ["01110", "10000", "10111", "10001", "01110"], "Y": ["10001", "01010", "00100", "00100", "00100"],
         "M": ["10001", "11011", "10101", "10001", "10001"], "O": ["01110", "10001", "10001", "10001", "01110"],
         "P": ["11110", "10001", "11110", "10000", "10000"], "E": ["11111", "10000", "11110", "10000", "11111"],
         "R": ["11110", "10001", "11110", "10010", "10001"], "A": ["01110", "10001", "11111", "10001", "10001"],
         "C": ["01111", "10000", "10000", "10000", "01111"], "N": ["10001", "11001", "10101", "10011", "10001"],
         "T": ["11111", "00100", "00100", "00100", "00100"]}
def letters(px, text, x, y, col):
    for ch in text:
        for j, row in enumerate(FONT5[ch]):
            for i, c in enumerate(row):
                if c == "1": px[y + j, x + i] = col
        x += 6

def opera():
    """The Opera House: a stone front with a pediment, the name across the frieze,
    four columns and a wide central doorway up a flight of steps."""
    o = np.full((48, 64), 1, np.uint8)
    o[0, :] = 3; o[:, 0] = 3; o[:, 63] = 3; o[1, 1:63] = 0
    for x in range(4, 60):                          # the pediment: a low triangle with an oculus
        top = 3 + abs(x - 31.5) * 10 / 28
        o[int(top):14, x] = 0
        o[int(top), x] = 3
    o[13, 3:61] = 3
    o[7:11, 30:34] = 3; o[8:10, 31:33] = 2
    o[14:22, 1:63] = 0; o[14, 1:63] = 3; o[21, 1:63] = 3     # the frieze
    letters(o, "OPERA", 18, 15, 3)
    o[22:44, 1:63] = 2                              # the shaded porch behind the columns
    for x in (3, 13, 46, 56):                       # columns
        o[24:42, x:x + 5] = 0; o[24:42, x + 4] = 1; o[24:42, x - 1] = 3; o[24:42, x + 5] = 3
        o[22:24, x - 2:x + 7] = 0; o[22, x - 2:x + 7] = 3; o[42:44, x - 2:x + 7] = 0; o[43, x - 2:x + 7] = 3
    o[26:44, 22:42] = 3                             # the doorway, with a fanlight
    o[27:44, 23:41] = 0; o[30:44, 24:40] = 3; o[31:44, 25:31] = 2; o[31:44, 33:39] = 2
    o[28, 25:39] = 3; o[27:30, 31:33] = 3
    o[37, 30] = 0; o[37, 33] = 0
    o[26:42, 9:12] = 3; o[27:41, 10] = 1; o[26:42, 52:55] = 3; o[27:41, 53] = 1     # tall side windows
    o[44, :] = 0; o[45, :] = 2; o[46, :] = 0; o[47, :] = 3     # steps
    return o

def gym_art():
    """Wexford's gym: the standard building with a name board and pennants on the roof."""
    g = H.copy()
    g[2:14, 20:44] = 3; g[3:13, 21:43] = 0
    letters(g, "GYM", 24, 5, 3)
    g[11, 22:42] = 2
    for x in (5, 55):                               # pennants
        g[1:12, x] = 3
        g[2:7, x + 1:x + 6] = 0; g[3:6, x + 4:x + 6] = 1; g[2, x + 1:x + 6] = 3; g[6, x + 1:x + 6] = 3
    g[19:21, 17:31] = 3; g[20, 18:30] = 0           # a lintel over the door
    return g

def townhouse():
    """A two-storey terraced house with a painted front: 3 cells wide, 3 tall."""
    t = np.full((48, 48), 1, np.uint8)              # the painted wall
    t[0:6, :] = 2; t[0, :] = 3; t[5, :] = 3; t[2, 2:46:4] = 1       # parapet
    t[6, :] = 0; t[7, :] = 3                                        # cornice
    t[:, 0:2] = 3; t[:, 46:48] = 3
    for x0 in (6, 30):                                              # upstairs sash windows
        t[11:25, x0:x0 + 12] = 3; t[12:24, x0 + 1:x0 + 11] = 0
        t[13:23, x0 + 2:x0 + 10] = 2; t[17:19, x0 + 2:x0 + 10] = 0; t[13:23, x0 + 5:x0 + 7] = 0
        t[25, x0 - 1:x0 + 13] = 3
    t[27, 2:46] = 0; t[28, 2:46] = 3                                # string course
    t[31:44, 4:15] = 3; t[32:43, 5:14] = 0; t[33:42, 6:13] = 2; t[33:42, 9] = 0; t[37, 6:13] = 0    # downstairs window
    t[44, 3:16] = 3
    t[30:48, 18:30] = 3; t[31:47, 19:29] = 0                        # door with a fanlight
    t[31:35, 20:28] = 2; t[33, 20:28] = 0; t[35, 19:29] = 3
    t[36:47, 20:28] = 2; t[37:41, 21:24] = 1; t[37:41, 25:28] = 1; t[42:46, 21:24] = 1; t[42:46, 25:28] = 1
    t[41, 27] = 0
    t[31:44, 34:44] = 3; t[32:43, 35:43] = 0; t[33:42, 36:42] = 2; t[37, 36:42] = 0                  # narrow window
    t[44, 33:45] = 3
    t[47, :] = 3; t[46, 18:30] = 3; t[47, 18:30] = 0
    return t

def shop(name):
    """A flat-roofed shop with a name board and a glass front: the PMon Centre and the Mart."""
    b = np.zeros((48, 64), np.uint8)
    b[0:12, :] = 1; b[0, :] = 3; b[11, :] = 3; b[3:9:3, 1:63] = 2; b[0:12, 0] = 3; b[0:12, 63] = 3    # roof
    b[12:23, :] = 3; b[13:22, 1:63] = 0                             # the name board
    w = len(name) * 6 - 1
    letters(b, name, (64 - w) // 2, 15, 3)
    b[13, 1:63] = 1; b[21, 1:63] = 1
    b[23:48, 0:2] = 3; b[23:48, 62:64] = 3; b[47, :] = 3            # walls
    b[24:27, 2:62] = 1; b[25, 2:62:4] = 0; b[27, 2:62] = 3          # awning
    for x0, x1 in ((3, 16), (32, 46), (48, 61)):                    # plate glass
        b[30:43, x0:x1] = 3; b[31:42, x0 + 1:x1 - 1] = 2
        b[32, x0 + 2:x0 + 6] = 0; b[33, x0 + 2:x0 + 4] = 0; b[38:42, x0 + 1:x1 - 1] = 1
    b[29:48, 17:31] = 3; b[30:47, 18:30] = 2; b[30:47, 24] = 3      # sliding doors
    b[31:36, 19:23] = 0; b[31:36, 26:30] = 0; b[40, 22] = 0; b[40, 26] = 0
    b[44:47, 2:17] = 1; b[44:47, 31:62] = 1; b[44, 2:17] = 3; b[44, 31:62] = 3      # painted plinth
    b[46, 17:31] = 3; b[47, 17:31] = 0
    return b

POOL = "x:TOWN"          # New Ross's landmark: the Dunbrody
S = ship()
for i, ch in enumerate("123456ab"):
    y, x = (i // 2) * 16, (i % 2) * 16
    add_mt(ch, S[y:y + 16, x:x + 16], P_WATER, SOLID)
POOL = "out"

# Buildings. Standard ones are drawn once and reused in every town; landmarks
# ("own") are unique to a town and their tiles load with that town's map.
# The map letter marks a building's top-left corner; doors are bottom-row columns.
BUILDINGS = {
    "R": dict(art=None, pal=P_RED, doors=(1,), own=False),      # cottage, red tiles
    "U": dict(art=None, pal=P_BLUE, doors=(1,), own=False),     # cottage, blue slate
    "H": dict(art=townhouse, pal=P_RED, doors=(1,), own=True, w=3),     # townhouse, red front
    "J": dict(art=townhouse, pal=P_BLUE, doors=(1,), own=True, w=3),    # townhouse, blue front
    "9": dict(art=lambda: shop("CENTRE"), pal=P_RED, doors=(1,), own=False),    # PMon Centre: red roof
    "0": dict(art=lambda: shop("MART"), pal=P_BLUE, doors=(1,), own=False),     # Mart: blue roof
    "G": dict(art=gym_art, pal=P_FLOWER, doors=(1,), own=True),  # Wexford gym (the flower slot is gold there)
    "O": dict(art=opera, pal=P_UI, doors=(1, 2), own=True),     # Wexford Opera House, grey stone
}

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

POOL = "in"
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
machine = counter.copy()                         # the PMon Centre's healing machine: a tray of six cradles under a lamp
machine[0:7, 1:15] = 3; machine[1:6, 2:14] = 2
for x0 in (3, 7, 11):
    machine[1:3, x0:x0 + 2] = 0; machine[4:6, x0:x0 + 2] = 0
machine[8:14, 2:14] = 3; machine[9:13, 3:13] = 1; machine[10:12, 4:8] = 0; machine[10:12, 10:12] = 2
add_mt("M", machine, I_APPL, SOLID)
cage = floor.copy()                              # a brass bird cage on a stand, a small bird on its perch
cage[1:12, 3:13] = 3; cage[0, 6:10] = 3; cage[2:11, 4:12] = 0
cage[2:11, 5:12:2] = 3
cage[5:8, 6:10] = 2; cage[4:6, 8:10] = 2; cage[5, 10] = 1; cage[4, 9] = 3; cage[8, 4:12] = 3      # the bird and its perch
cage[12:14, 7:9] = 3; cage[14:16, 5:11] = 3; cage[14, 6:10] = 2
add_mt("A", cage, I_PACK, SOLID)
rail = floor.copy()                              # brass railings across the hall
rail[2:14, 1::4] = 3; rail[2:14, 2::4] = 2; rail[3, :] = 3; rail[4, :] = 2; rail[11, :] = 3; rail[12, :] = 2
add_mt("j", rail, I_PACK, SOLID)
gate = rail.copy(); gate[1:15, 0:2] = 3; gate[1:15, 14:16] = 3; gate[6:9, 6:10] = 3; gate[7, 7:9] = 1    # with a lock plate
add_mt("g", gate, I_PACK, SOLID)
statue = np.zeros((16, 16), np.uint8)
statue[11:16, 2:14] = 3; statue[12:15, 3:13] = 2; statue[12, 3:13] = 1            # plinth
statue[5:11, 4:11] = 3; statue[6:10, 5:10] = 1; statue[8:10, 5:10] = 2             # body
statue[1:6, 9:12] = 3; statue[2:6, 10] = 1                                         # neck
statue[1:3, 11:15] = 3; statue[2, 12:14] = 1                                       # head and bill
statue[6:9, 2:5] = 3; statue[7, 3] = 1                                             # wing
add_mt("s", statue, I_APPL, SOLID)
curtain = np.full((16, 16), 1, np.uint8)
curtain[:, 2::4] = 2; curtain[:, 0] = 3; curtain[:, 15] = 3; curtain[0:2, :] = 3; curtain[2, 1:15] = 0
curtain[13:16, :] = 2; curtain[15, :] = 3
add_mt("c", curtain, I_RUG, SOLID)
seat = floor.copy()
seat[2:9, 3:13] = 3; seat[3:8, 4:12] = 1; seat[9:13, 2:14] = 3; seat[10:12, 3:13] = 2; seat[13:15, 3:5] = 3; seat[13:15, 11:13] = 3
add_mt("h", seat, I_RUG, SOLID)
shelf = box(1, y1=15); shelf[5, 1:15] = 3; shelf[10, 1:15] = 3
for y0 in (1, 6, 11):
    for x0, c in ((2, 2), (6, 0), (10, 2)):
        shelf[y0 + 1:y0 + 4, x0:x0 + 3] = c; shelf[y0 + 1, x0:x0 + 3] = 3
shelf[15, :] = 3
add_mt("k", shelf, I_APPL, SOLID)
add_mt("m", mat, I_RUG)
POOL = "out"

# ---------------------------------------------------------------- sprites
# 16x16, colours: 1 skin/light, 2 clothing colour (from the sprite palette), 3 dark.
# Proportions, learned from studying good 8-bit character sprites: the head fills
# eleven of the sixteen rows and nearly the full width; the body is four rows and
# the feet two; eyes are two tall dark pixels set wide; hats and hair are one big
# simple shape, with a tuft or two breaking the outline.
# People are drawn 12 pixels wide and 14 tall inside their 16x16 cell, so the world
# around them reads as bigger than they are.
B2 = ["................"] * 2
FACE = ["..331111111133..", "..311311113113..", "..311311113113..", "...3111111113..."]
PLAIN = ["..311111111113.."] + FACE[1:]
BODY = ["...3322112233...", "...3122222213...", "...3122222213...", "....32222223....",
        "....322..223....", "....333..333...."]
HAT = ["......3333......", "....33222233....", "...3222222223...", "..333333333333.."]
# James: a bobble hat in the county purple, hair showing at the temples
hero_d = B2 + HAT + FACE + BODY
hero_u = B2 + HAT[:3] + ["...3222222223...", "..322222222223..", "..333333333333..", "..313333333313..",
                         "...3333333333...", "...3322222233..."] + BODY[1:]
hero_l = B2 + ["......3333......", "....33222233....", "...3222222223...", "..33333333333...",
               "...3111133333...", "...3131133333...", "...3131113333...", "...3111111333...",
               "....33111133....", "....32222223....", "....32112223....", "....32222223....",
               ".....322223.....", ".....333333....."]
girl = B2 + [".....333333.....", "...3333333333...", "..333333333333..", "..333111111333..",
             "..331111111133..", "..331311113133..", "..331311113133..", "..333111111333..",
             "..333322223333..", "...3122222213...", "...3122222213...", "....32222223....",
             "...3222222223...", "....311..113...."]
boy = B2 + ["...3.3.33.3.3...", "...3333333333...", "..333333333333..", "..333313313333..",
            "..331111111133.."] + FACE[1:] + BODY
mom = ["................", "......3333......", ".....333333.....", "...3333333333...",
       "..333333333333..", "..333311113333.."] + PLAIN + ["...3322112233...", "...3121111213...",
       "...3121111213...", "....32222223....", "...3222222223...", "....33333333...."]
CAP = ["................"] * 3 + ["....33333333....", "...3222222223...", "..333333333333.."]
oldman = CAP + PLAIN + BODY
def step(rows):
    return rows[:14] + ["....322..333....", "....333........."]
def bob(px):                    # the passing pose between steps: the body lifts a pixel
    out = px.copy(); out[0:14] = px[1:15]
    return out
_art = art
def art(rows, n=16):            # every sprite must be exactly square, or it comes out sheared
    assert len(rows) == n and all(len(r) == n for r in rows), rows
    return _art(rows, n) if n != 16 else _art(rows)
d, u, l = art(hero_d), art(hero_u), art(hero_l)
d1, u1 = art(step(hero_d)), art(step(hero_u))
l1 = art(hero_l[:14] + ["....3223.3223...", "....3333........"])      # leading leg planted
l2 = art(hero_l[:14] + [".....3223223....", ".........333...."])      # trailing leg planted
# Four frames a direction: standing, one step, passing, the other step.
frames = [d, d1, bob(d), d1[:, ::-1], u, u1, bob(u), u1[:, ::-1], l, l1, bob(l), l2,
          art(girl), art(boy), art(mom), art(oldman)]
F_GIRL, F_BOY, F_MOM, F_OLD = 12, 13, 14, 15
# the bodhran player: the drum held on his left, the tipper in his right hand
DRUM = ["...3322112233...", "..3333.3222213..", ".311113.322213..", ".311113.322233..",
        "..3333..32223...", "........33333..."]
drum_a = CAP + PLAIN + DRUM
drum_b = CAP + PLAIN + DRUM[:2] + [".313113.322213..", ".311313.322233.."] + DRUM[4:]
frames += [art(drum_a), art(drum_b)]
F_DRUM = len(frames) - 2
sleep_a = art(["................", "................", "................", "...3..3..3..3...",
               "..323323323323..", ".32222222222223.", ".322222222222223", "3222222222221113",
               "3222222222211113", "3222222222213313", "3222222222211113", ".322222222221133",
               "..3333333333333.", "................", "................", "................"])
sleep_b = sleep_a.copy(); sleep_b[2:6] = sleep_a[3:7]            # breathing in
frames += [sleep_a, sleep_b]
F_SLEEP = len(frames) - 2
def pball(gap=0):
    b = np.zeros((16, 16), np.uint8)
    for y in range(16):
        for x in range(16):
            d = ((x - 7.5) ** 2 + (y - 7.5) ** 2) ** 0.5
            if d < 7.6:
                b[y, x] = 3 if d > 6.3 else (2 if y < 8 else 1)
    b[7:9, 1:15] = 3; b[6:10, 6:10] = 3; b[7:9, 7:9] = 1                 # band and button
    b[3, 4:7] = 1; b[4, 3:5] = 1                                           # shine
    if gap:                                                                # the halves spring apart
        o = np.zeros((16, 16), np.uint8)
        o[0:6] = b[2:8]; o[10:16] = b[8:14]; o[7:9, 2:14] = 1; o[6, 5:11] = 1; o[9, 5:11] = 1
        return o
    return b
frames += [pball(), np.rot90(pball()), pball(1)]
F_BALL = len(frames) - 3
assert len(frames) <= 23            # leave room below tile 128 for the effects that follow

# A second sheet of sprites, kept in the other video memory bank (frame numbers 32 up).
alex = ["................", "....3..33..3....", "...3333333333...", "..333333333333..",
        "..333333333333..", "..333333313333..", "..333311111133..", "..311311113113..",
        "..311311113113..", "...3111111113...", "...3222222223...", "...3332222333...",
        "...3333223333...", "....33333333....", "....333..333....", "....333..333...."]
prof = ["................"] * 3 + [".....333333.....", "...3311111133...", "..331111111133..",
        "..331111111133..", "..313313313313..", "..311111111113..", "...3133333313...",
        "...3322112233...", "...3122112213...", "...3122222213...", "....32222223....",
        "....322..223....", "....333..333...."]
prof_u = ["................"] * 3 + [".....333333.....", "...3311111133...", "..331111111133..",
          "..333111111333..", "..333333333333..", "..313333333313..", "...3333333333...",
          "...3322222233...", "...3122222213...", "...3122222213...", "....32222223....",
          "....322..223....", "....333..333...."]
prof_l = ["................"] * 3 + ["......33333.....", "....331111133...", "...3111111333...",
          "...3111113333...", "..33331113333...", "...3111111333...", "...3331111133...",
          "....33111133....", "....32222223....", "....32112223....", "....32222223....",
          ".....322223.....", ".....333333....."]
# A PBall lying on the ground with something in it: small, and sunk a little into the grass.
item = ["................"] * 5 + ["......3333......", "....33222233....", "...3211222223...",
        "...3212222223...", "..322222222223..", "..333333113333..", "..311113113113..",
        "...3111133113...", "...3311111133...", "....3.3333.3....", "................"]
potion = ["................", "......3333......", ".....311113.....", "......3113......",
          "......3113......", ".....311113.....", "....31222213....", "...3122222213...",
          "...3122122213...", "...3121222213...", "...3122222213...", "...3122222213...",
          "....31222213....", ".....333333.....", "................", "................"]
soda = ["................", "....33333333....", "...3111111113...", "...3333333333...",
        "...3122222213...", "...3122222213...", "...3111111113...", "...3133333313...",
        "...3111111113...", "...3122222213...", "...3122222213...", "...3122222213...",
        "...3111111113...", "....33333333....", "................", "................"]
def back_of(rows):               # the same person seen from behind
    out = []
    for y, r in enumerate(rows):
        r = list(r)
        for x, ch in enumerate(r):
            if ch != "1": continue
            if y <= 9: r[x] = "3"
            elif y == 10: r[x] = "2"
            elif y < 15 and x not in (4, 11): r[x] = "2"
        if y == 8: r[3] = "1"; r[12] = "1"                  # ears
        out.append("".join(r))
    return out
def side_of(rows, long_hair=False):         # ...and in profile, facing left
    top = rows[5] if "1" not in rows[5] else "...3311133333..."
    return rows[:5] + [top, "...3111133333...", "...3131133333...", "...3131113333...", "...3111111333...",
                       "....331113333..." if long_hair else "....33111133....", "....32222223....",
                       "....32112223....", "....32222223....", ".....322223.....", ".....333333....."]
alex_l = side_of(alex)
alex_l[11:14] = ["....33333333....", "....33113333....", "....33333333...."]; alex_l[10] = "....32222223...."
turned = []
for who, lh in ((girl, True), (boy, False), (mom, True), (oldman, False)):
    turned += [art(back_of(who)), art(side_of(who, lh))]
wave = ["................", "......3333......", "....33111133....", "...3111221113.3.",
        "..311222222113..", ".31122222222213.", ".3122223322221.3", "31222231.3222213",
        "312222313.322213", "3122222133222213", "3122222222222213", "3112222222222113",
        ".31122222222113.", "..331122221133..", "....33333333....", "................"]
flame = ["................", ".......3........", "......33........", "......323.......",
         ".....3223...3...", ".....32223.33...", "..3.322223323...", "..33322122223...",
         "..32322112223...", ".3222211122223..", ".3222111112223..", ".3221111111223..",
         ".3221111111223..", "..32211111223...", "...322222223....", "....3333333....."]
leaf = ["................"] * 3 + [".........333....", ".......332223...", "......3222223...",
        ".....32223223...", ".....3223223....", "....32232223....", "....3232223.....",
        "....322223......", "...3333333......", "..33............"] + ["................"] * 3
dot = ["................"] * 9 + ["..3333..........", ".322223.........", ".321223.........",
       ".333333.........", ".311113.........", "..3333..........", "................"]
spr2 = []
for f in [art(alex), art(prof), art(potion), art(soda), art(item), art(prof_u), art(prof_l),
          art(back_of(alex)), art(alex_l)] + turned + [art(wave), art(flame), art(leaf), art(dot)]:
    for x in (0, 8):
        spr2 += [f[0:8, x:x + 8], f[8:16, x:x + 8]]
F_ALEX, F_PROF, F_POTION, F_SODA, F_ITEM, F_PROF_U, F_PROF_L, F_ALEX_U, F_TURN = 32, 33, 34, 35, 36, 37, 38, 39, 41
F_WAVE, F_FLAME, F_LEAF, F_DOT = 49, 50, 51, 52
assert len(spr2) == 21 * 4

def scale3x(px):                 # a sprite blown up three times, with its diagonals smoothed
    h, w = px.shape
    out = np.zeros((h * 3, w * 3), np.uint8)
    g = lambda y, x: int(px[min(max(y, 0), h - 1), min(max(x, 0), w - 1)])
    for y in range(h):
        for x in range(w):
            A, B, C, D, E, F, G, H, I = (g(y - 1, x - 1), g(y - 1, x), g(y - 1, x + 1), g(y, x - 1), g(y, x),
                                         g(y, x + 1), g(y + 1, x - 1), g(y + 1, x), g(y + 1, x + 1))
            o = [E] * 9
            if B != H and D != F:
                o[0] = D if D == B else E
                o[1] = B if (D == B and E != C) or (B == F and E != A) else E
                o[2] = F if B == F else E
                o[3] = D if (D == B and E != G) or (D == H and E != A) else E
                o[5] = F if (B == F and E != I) or (H == F and E != C) else E
                o[6] = D if D == H else E
                o[7] = H if (D == H and E != I) or (H == F and E != G) else E
                o[8] = F if H == F else E
            out[y * 3:y * 3 + 3, x * 3:x * 3 + 3] = np.array(o).reshape(3, 3)
    return out
PIC_ME = 3

def feather():                   # the Feather Badge, 64x64
    f = np.zeros((64, 64), np.uint8)
    ax, ay, bx_, by_ = 9.0, 57.0, 53.0, 7.0                 # the quill runs from bottom left to top right
    L = ((bx_ - ax) ** 2 + (by_ - ay) ** 2) ** 0.5
    ux, uy = (bx_ - ax) / L, (by_ - ay) / L
    for y in range(64):
        for x in range(64):
            t = ((x - ax) * ux + (y - ay) * uy) / L
            d = (x - ax) * uy - (y - ay) * ux                # which side of the quill, and how far
            if -0.02 <= t <= 0.2 and abs(d) < 1.2: f[y, x] = 3
            if not 0.16 <= t <= 1.02: continue
            v = (t - 0.16) / 0.86
            wdt = 12.5 * (np.sin(np.pi * min(v, 1) ** 0.75) ** 0.55) + 0.5
            if abs(d) > wdt: continue
            c = 1 if d > 0 else 2                            # lit side and shaded side
            if abs(d) > wdt - 1.3: c = 3
            elif int(t * L * 0.9 + abs(d) * 0.8) % 4 == 0: c = 2 if c == 1 else 3      # barbs
            if abs(d) < 0.9: c = 0 if (x + y) % 2 else 3     # the shaft catches the light
            f[y, x] = c
    for cx, cy in ((30, 46), (20, 36)):                      # two little splits in the vane
        f[cy - 1:cy + 2, cx - 2:cx + 1][f[cy - 1:cy + 2, cx - 2:cx + 1] > 0] = 3
    return f
BADGE = feather()
BADGE_PAL = ["#101830", "#f8f8f8", "#88c8f0", "#f8d030"]
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
BALL_TILE = len(spr)
spr += [art(["..3333..", ".322223.", "32222223", "33333333", "31111113", "31111113", ".311113.", "..3333.."], 8), blank8]
BANG_TILE = len(spr)
spr += [art([".333333.", "31111113", "31122113", "31122113", "31122113", "31111113", "31122113", ".333333."], 8),
        art(["...33...", "...3....", "........", "........", "........", "........", "........", "........"], 8)]
RAIN_TILE = len(spr)
spr += [art([".......1", "......1.", "......1.", ".....1..", ".....1..", "....1...", "....1...", "...1...."], 8), blank8]
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

# ---- the detailed toolkit: curved forms that shade themselves and cast shadows,
# ---- interior linework, and textures. Used for the starters.
def spline(pts, closed=True, k=8):
    """Catmull-Rom curve through the points."""
    P = np.array(pts, float); n = len(P); out = []
    for i in (range(n) if closed else range(n - 1)):
        p0 = P[(i - 1) % n] if (closed or i > 0) else P[i]
        p1, p2 = P[i], P[(i + 1) % n]
        p3 = P[(i + 2) % n] if (closed or i + 2 < n) else P[i + 1]
        for t in np.linspace(0, 1, k, endpoint=False):
            out.append(tuple(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                                    + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3)))
    if not closed:
        out.append(tuple(P[-1]))
    return out

def oval(cx, cy, rx, ry, n=12):
    return [(cx + rx * np.cos(2 * np.pi * i / n), cy + ry * np.sin(2 * np.pi * i / n)) for i in range(n)]

class Art:
    DARKER = {1: 2, 4: 1, 2: 3, 5: 1}     # 5 is the accent colour; its shade is the main hue
    def __init__(self, n=64):
        self.n = n; self.a = np.zeros((n, n), np.uint8)
    def mask(self, pts, smooth=True):
        im = Image.new("L", (self.n, self.n), 0)
        ImageDraw.Draw(im).polygon(spline(pts) if smooth else pts, fill=1)
        return np.array(im, bool)
    @staticmethod
    def shifted(m, dy, dx):
        out = np.zeros_like(m); h, w = m.shape
        ys, yd = (slice(dy, h), slice(0, h - dy)) if dy >= 0 else (slice(0, h + dy), slice(-dy, h))
        xs, xd = (slice(dx, w), slice(0, w - dx)) if dx >= 0 else (slice(0, w + dx), slice(-dx, w))
        out[yd, xd] = m[ys, xs]
        return out
    def form(self, pts, base, shade=None, depth=4, smooth=True, cast=2, outline=3):
        """Fill a shape. It darkens what lies just behind it to the lower right (a cast
        shadow), shades its own lower-right side, and gets an outline."""
        m = self.mask(pts, smooth); a = self.a
        if cast:
            sh = self.shifted(m, -cast, -cast) & ~m
            before = a.copy()
            for v, w in self.DARKER.items():
                a[sh & (before == v)] = w
        a[m] = base
        if shade is not None:
            dist = np.full(m.shape, 99)
            for k in range(1, depth + 2):
                gone = ~self.shifted(m, k, k) | ~self.shifted(m, k, 0) | ~self.shifted(m, 0, k)
                dist[gone & (dist == 99)] = k
            yy, xx = np.indices(m.shape)
            a[m & (dist <= depth)] = shade
            a[m & (dist == depth + 1) & ((xx + yy) % 2 == 0)] = shade
        if outline:
            inner = m & self.shifted(m, 1, 0) & self.shifted(m, -1, 0) & self.shifted(m, 0, 1) & self.shifted(m, 0, -1)
            a[m & ~inner] = outline
        return m
    def line(self, pts, col=3, smooth=True, width=1):
        im = Image.fromarray(self.a)
        ImageDraw.Draw(im).line(spline(pts, closed=False) if (smooth and len(pts) > 2) else pts, fill=col, width=width)
        self.a = np.array(im)
    def dots(self, pts, col=3):
        for x, y in pts:
            self.a[y, x] = col
    def box(self, x0, y0, x1, y1, col):
        self.a[y0:y1 + 1, x0:x1 + 1] = col
    def texture(self, region, on, col, kind):
        """Stamp a pattern over the part of `region` currently coloured `on`."""
        m = self.mask(region) & (self.a == on); a = self.a
        if kind == "scales":
            stamps = [((x, y), (x + 1, y + 1), (x + 2, y + 1), (x + 3, y)) for y in range(0, self.n, 4)
                      for x in range((y // 4 % 2) * 3, self.n - 3, 6)]
        elif kind == "fur":
            stamps = [((x, y), (x + 1, y + 1)) for y in range(0, self.n, 4) for x in range((y // 4 % 2) * 3, self.n - 1, 6)]
        elif kind == "speck":
            stamps = [((x, y),) for y in range(0, self.n, 3) for x in range((y // 3 % 2) * 2, self.n, 4)]
        else:   # dither
            stamps = [((x, y),) for y in range(self.n) for x in range(y % 2, self.n, 2)]
        for st in stamps:
            if all(0 <= x < self.n and 0 <= y < self.n and m[y, x] for x, y in st):
                for x, y in st:
                    a[y, x] = col
    def done(self):
        out = self.a.copy(); out[out == 4] = 0
        return out

# Trainer pictures for battles, 56x56. Colours: 4 white, 1 skin / light, 2 the trainer's colour, 3 dark.
def _legs(A, col, shade, stance=0):
    A.form([(21 - stance, 35), (28, 35), (27, 51), (20 - stance, 51)], col, shade, depth=1, smooth=False, cast=0)
    A.form([(28, 35), (35 + stance, 35), (36 + stance, 51), (29, 51)], col, shade, depth=1, smooth=False, cast=0)
    A.line([(28, 37), (28, 50)], 3)
def _shoes(A, stance=0, col=3):
    A.form([(17 - stance, 50), (27, 50), (27, 54), (16 - stance, 54)], col, None, cast=0)
    A.form([(29, 50), (39 + stance, 50), (40 + stance, 54), (29, 54)], col, None, cast=0)
    A.line([(17 - stance, 54), (26, 54)], 1); A.line([(30, 54), (39 + stance, 54)], 1)
def _head(A, cx=28, cy=10):
    A.box(cx - 2, cy + 5, cx + 2, cy + 9, 1); A.line([(cx - 3, cy + 6), (cx - 3, cy + 9)], 3); A.line([(cx + 3, cy + 6), (cx + 3, cy + 9)], 3)
    A.form(oval(cx, cy, 6.5, 7.2), 1, None, cast=0)
def _face(A, cx=28, cy=10, brow=0):
    A.box(cx - 4, cy, cx - 3, cy + 1, 3); A.box(cx + 2, cy, cx + 3, cy + 1, 3)   # eyes
    A.dots([(cx - 4, cy), (cx + 2, cy)], 4)
    if brow: A.line([(cx - 5, cy - 3), (cx - 2, cy - 2)], 3); A.line([(cx + 4, cy - 3), (cx + 1, cy - 2)], 3)
    A.dots([(cx + 1, cy + 3)], 3)                                                 # nose
    A.line([(cx - 2, cy + 5), (cx + 1, cy + 5)], 3)                               # mouth

def pic_alex():          # the rival: tall, three-quarter on, long coat and scarf on the wind, a PBall loose in one hand
    A = Art(56)
    # coat tail lifting behind him
    A.form([(33, 27), (39, 31), (45, 38), (49, 46), (44, 47), (40, 42), (35, 40)], 2, 3, depth=2, cast=0)
    A.line([(37, 32), (44, 44)], 3)
    # legs: slim dark trousers, the near one a step forward
    A.form([(28, 31), (34, 31), (34, 42), (36, 51), (31, 51), (29, 42)], 3, None, smooth=False, cast=0)
    A.form([(21, 31), (28, 31), (27, 42), (26, 52), (20, 52), (21, 42)], 3, None, smooth=False, cast=0)
    A.line([(23, 33), (22, 50)], 2); A.line([(32, 33), (33, 49)], 2)                 # light along each shin
    A.line([(22, 42), (26, 43)], 2); A.line([(30, 42), (33, 42)], 2)                 # knees
    # runners
    A.form([(30, 50), (38, 50), (40, 53), (40, 55), (30, 55)], 4, 1, depth=1, smooth=False, cast=0)
    A.form([(16, 51), (26, 51), (27, 55), (15, 55)], 4, 1, depth=1, smooth=False, cast=0)
    A.line([(15, 55), (27, 55)], 3); A.line([(30, 55), (40, 55)], 3)
    A.line([(19, 52), (22, 52)], 3); A.line([(33, 51), (36, 51)], 3)                 # laces
    # shirt and belt
    A.form([(23, 15), (32, 15), (32, 32), (22, 32)], 3, None, smooth=False, cast=0)
    A.line([(25, 20), (27, 22)], 2); A.line([(27, 22), (30, 19)], 2)                 # a slash of colour across the chest
    A.box(22, 30, 32, 31, 1); A.box(26, 30, 28, 31, 4); A.line([(22, 32), (32, 32)], 3)
    # the coat, hanging open
    A.form([(21, 14), (26, 15), (24, 25), (24, 35), (22, 42), (16, 41), (17, 29), (18, 19)], 2, 3, depth=1, cast=0)
    A.form([(29, 15), (35, 14), (38, 19), (38, 29), (41, 41), (34, 43), (31, 35), (31, 24)], 2, 3, depth=1, cast=0)
    A.line([(34, 22), (35, 38)], 3); A.line([(19, 24), (19, 38)], 3)                 # folds
    A.line([(25, 17), (24, 34)], 1); A.line([(30, 17), (31, 34)], 1)                 # the lining catching the light
    A.line([(18, 36), (22, 37)], 3); A.dots([(20, 30), (36, 30), (36, 34)], 1)       # pocket flap, studs
    # near arm: elbow out, hand buried in the coat pocket
    A.form([(21, 14), (16, 16), (12, 23), (14, 31), (19, 33), (20, 28), (18, 24), (21, 19)], 2, None)
    A.line([(15, 18), (14, 23)], 1); A.line([(16, 27), (18, 30)], 3)
    A.line([(13, 24), (17, 25)], 3); A.line([(15, 31), (19, 32)], 4)                 # elbow crease, cuff
    # far arm: bent up, a PBall balanced on the fingertips
    A.form([(35, 14), (40, 16), (43, 22), (46, 20), (49, 23), (45, 28), (40, 28), (37, 22)], 2, None)
    A.line([(41, 23), (43, 26)], 3); A.line([(38, 17), (40, 21)], 1); A.line([(46, 21), (48, 23)], 4)
    A.form(oval(48.5, 19.5, 2.2, 2.2), 1, None, cast=0)
    A.form(oval(49.5, 14, 3.6, 3.6), 4, 1, depth=1, cast=0)
    A.form([(46, 14), (47, 11), (49.5, 10), (52, 11), (53, 14)], 2, None, cast=0)
    A.line([(46, 14), (53, 14)], 3); A.box(49, 13, 50, 15, 3); A.dots([(49, 14)], 4); A.dots([(48, 12)], 4)
    # upturned collar
    A.form([(21, 15), (23, 9), (26, 15)], 2, 3, depth=0, smooth=False, cast=0)
    A.form([(34, 15), (32, 9), (29, 15)], 2, 3, depth=0, smooth=False, cast=0)
    # neck and head, turned a little to his right
    A.box(25, 11, 29, 15, 1)
    A.form(oval(27, 7.5, 4.8, 5.4), 1, None, cast=0)
    A.dots([(31, 8), (32, 8), (32, 9)], 1); A.dots([(33, 8), (33, 9), (32, 10), (32, 7)], 3)       # ear
    # scarf: wound once, the long end flying
    A.form([(22, 12), (27, 14), (32, 12), (34, 15), (28, 18), (22, 16)], 4, 1, depth=1, cast=1)
    A.form([(32, 13), (36, 8), (41, 5), (45, 6), (44, 9), (41, 9), (38, 12), (35, 17)], 4, 1, depth=1, cast=0)
    A.line([(36, 12), (40, 8)], 1); A.line([(42, 6), (43, 8)], 3)
    # face
    A.box(24, 7, 24, 8, 3); A.box(28, 7, 29, 8, 3); A.dots([(29, 7)], 4)             # eyes
    A.line([(23, 5), (25, 6)], 3); A.line([(27, 6), (30, 5)], 3)                     # brows, drawn down
    A.dots([(25, 10)], 3); A.line([(25, 12), (28, 12)], 3); A.dots([(29, 11)], 3)    # nose, a smirk
    # hair: swept up and forward in spikes, a lock over the brow
    A.form([(22, 8), (21, 5), (18, 5), (21, 3), (19, 0), (23, 2), (24, 0), (27, 2), (29, 0), (31, 2), (35, 0),
            (34, 3), (38, 3), (35, 5), (35, 9), (33, 6), (31, 4), (29, 6), (27, 3), (26, 6), (24, 4), (23, 8)], 3, None, smooth=False, cast=0)
    A.line([(24, 1), (25, 3)], 2); A.line([(29, 1), (29, 3)], 2); A.line([(34, 1), (33, 3)], 2); A.dots([(21, 3), (36, 4)], 2)
    return A.done()

def pic_lad():           # a hurler: hooped jersey, shorts, hurley on the shoulder, ball in hand
    A = Art(56)
    A.line([(41, 30), (46, 6)], 3, width=3); A.line([(42, 29), (46, 8)], 1)      # the hurley's handle
    A.form([(43, 8), (48, 1), (53, 2), (52, 9), (47, 11)], 1, 2, depth=1)        # and its bas
    A.form([(21, 35), (28, 35), (27, 45), (21, 45)], 1, None, smooth=False, cast=0)   # bare knees
    A.form([(28, 35), (35, 35), (35, 45), (29, 45)], 1, None, smooth=False, cast=0)
    A.form([(21, 44), (27, 44), (27, 51), (21, 51)], 2, 3, depth=1, smooth=False, cast=0)   # socks
    A.form([(29, 44), (35, 44), (35, 51), (29, 51)], 2, 3, depth=1, smooth=False, cast=0)
    A.line([(21, 46), (27, 46)], 4); A.line([(29, 46), (35, 46)], 4)
    _shoes(A)
    A.form([(19, 32), (37, 32), (38, 40), (29, 40), (28, 37), (27, 40), (18, 40)], 4, 1, depth=1, smooth=False)   # shorts
    A.form([(19, 19), (37, 19), (38, 34), (18, 34)], 2, 3, depth=2, smooth=False)                    # jersey
    A.box(19, 25, 37, 27, 4); A.line([(19, 28), (37, 28)], 3); A.line([(19, 24), (37, 24)], 3)        # hoop
    A.form([(19, 19), (14, 22), (12, 28), (16, 30), (20, 25)], 2, 3, depth=1)                         # short sleeves
    A.form([(37, 19), (42, 21), (44, 27), (40, 29), (36, 25)], 2, 3, depth=1)
    A.form([(12, 27), (16, 28), (16, 37), (12, 37)], 1, None, smooth=False, cast=0)                   # arms
    A.form([(40, 27), (44, 26), (43, 31), (40, 32)], 1, None, smooth=False, cast=0)
    A.form(oval(14, 39, 3.2, 3.2), 4, 1, depth=1, cast=0); A.line([(12, 38), (16, 40)], 3)            # sliotar
    A.form(oval(42, 31, 2.4, 2.4), 1, None, cast=0)
    _head(A)
    A.form([(22, 18), (28, 21), (34, 18), (33, 16), (23, 16)], 4, 1, depth=0, smooth=False, cast=0)   # collar
    A.form([(21, 9), (21, 4), (25, 1), (31, 1), (35, 4), (35, 9), (33, 6), (29, 5), (26, 7), (23, 6)], 3, None, cast=0)   # short hair
    A.line([(25, 3), (30, 3)], 2)
    _face(A)
    return A.done()

def pic_orla():          # gym leader: flying jacket with a fleece collar, long hair and scarf on the wind
    A = Art(56)
    A.form([(33, 6), (42, 8), (50, 14), (54, 22), (48, 21), (44, 26), (40, 20), (36, 16)], 3, None, cast=0)   # hair streaming out
    A.line([(38, 10), (48, 17)], 2); A.line([(40, 15), (46, 21)], 2)
    A.form([(22, 20), (12, 23), (4, 21), (1, 26), (8, 28), (16, 27), (23, 25)], 4, 1, depth=1)        # scarf tail
    A.line([(6, 24), (14, 25)], 3)
    _legs(A, 3, None); _shoes(A)
    A.line([(23, 38), (23, 49)], 2); A.line([(33, 38), (33, 49)], 2)
    A.box(20, 46, 27, 47, 2); A.box(29, 46, 36, 47, 2)                                               # boot cuffs
    A.form([(19, 19), (37, 19), (39, 36), (17, 36)], 2, 3, depth=2, smooth=False)                    # jacket
    A.line([(28, 21), (28, 36)], 3); A.dots([(26, 25), (26, 29), (26, 33)], 1)
    A.box(18, 35, 38, 37, 3); A.box(26, 35, 30, 37, 1)                                               # belt and buckle
    A.box(20, 28, 24, 31, 3); A.line([(20, 28), (24, 28)], 1)                                        # chest pocket
    A.form([(19, 19), (14, 22), (12, 33), (16, 35), (20, 26)], 2, 3, depth=1)                        # near sleeve, hand on hip
    A.form(oval(16, 35, 2.4, 2.4), 1, None, cast=0)
    A.form([(37, 19), (43, 16), (48, 9), (51, 11), (47, 20), (40, 26)], 2, 3, depth=1)               # far arm raised
    A.form(oval(50, 9, 2.6, 2.6), 1, None, cast=0)
    A.form([(49, 7), (51, -1), (55, 1), (53, 8)], 4, 1, depth=1, cast=0); A.line([(50, 7), (53, 1)], 3)   # a feather held high
    _head(A)
    A.form([(20, 17), (28, 22), (36, 17), (38, 21), (33, 25), (28, 23), (23, 25), (18, 21)], 4, 1, depth=1)   # fleece collar
    A.texture([(18, 17), (38, 17), (38, 25), (18, 25)], 4, 1, "speck")
    A.form([(21, 12), (20, 5), (24, 1), (31, 0), (36, 3), (37, 12), (35, 17), (34, 8), (30, 5), (25, 6), (23, 9), (22, 17)], 3, None, cast=0)   # hair
    A.line([(24, 3), (29, 2)], 2); A.line([(35, 6), (36, 13)], 2)
    A.form([(21, 5), (28, 3), (35, 5), (35, 7), (28, 5), (21, 7)], 2, None, cast=0, outline=0)       # goggles pushed up
    A.form(oval(24, 5, 2.2, 1.8), 4, None, cast=0); A.form(oval(32, 5, 2.2, 1.8), 4, None, cast=0)
    _face(A)
    return A.done()

def pic_james():         # from behind, close: bobble hat, jacket, a PBall drawn back to throw
    A = Art(56)
    A.form([(4, 55), (6, 42), (14, 36), (26, 34), (38, 36), (46, 42), (49, 55)], 2, 3, depth=4, smooth=False)   # shoulders and back
    A.line([(26, 38), (27, 55)], 3)                                                                   # seam
    A.line([(12, 44), (10, 55)], 3); A.line([(40, 44), (42, 55)], 3)                                  # where the arms hang
    A.form([(17, 36), (26, 39), (35, 36), (33, 32), (19, 32)], 4, 1, depth=1, smooth=False, cast=0)   # collar
    A.form([(40, 40), (46, 30), (50, 22), (55, 24), (53, 34), (48, 44)], 2, 3, depth=2)               # arm cocked back
    A.form(oval(51, 19, 3.5, 3.5), 1, None, cast=0)                                                   # hand
    A.form(oval(51, 13, 5, 5), 4, 1, depth=1, cast=0)                                                 # the PBall
    A.form([(46, 13), (47, 9), (51, 8), (55, 9), (56, 13)], 2, None, cast=0); A.line([(46, 13), (56, 13)], 3)
    A.box(50, 12, 52, 14, 3); A.dots([(51, 13)], 4)
    A.box(22, 27, 30, 34, 1); A.line([(21, 28), (21, 33)], 3); A.line([(31, 28), (31, 33)], 3)        # neck
    A.form(oval(26, 20, 12, 11), 1, None, cast=0)                                                     # head
    A.form(oval(13, 22, 2.5, 3.5), 1, None, cast=0); A.form(oval(39, 22, 2.5, 3.5), 1, None, cast=0)  # ears
    A.form([(14, 20), (15, 28), (20, 31), (32, 31), (37, 28), (38, 20)], 3, None, cast=0)             # hair below the hat
    A.line([(18, 26), (19, 30)], 2); A.line([(24, 26), (24, 30)], 2); A.line([(30, 26), (30, 30)], 2); A.line([(35, 25), (34, 29)], 2)
    A.form([(12, 22), (12, 13), (17, 6), (26, 4), (35, 6), (40, 13), (40, 22)], 2, 3, depth=3, cast=0)   # the hat
    A.form([(11, 18), (41, 18), (41, 23), (11, 23)], 4, 1, depth=1, smooth=False, cast=0)             # its turned-up band
    for x in range(13, 41, 3): A.line([(x, 19), (x, 22)], 1)
    A.line([(18, 9), (16, 16)], 3); A.line([(26, 6), (26, 16)], 3); A.line([(34, 9), (36, 16)], 3)    # knit ribs
    A.form(oval(26, 3, 4, 3.5), 4, 1, depth=1, cast=0)                                                # bobble
    A.dots([(24, 2), (27, 4), (28, 1), (25, 4)], 3)
    return A.done()

PICS = [pic_alex(), pic_lad(), pic_orla(), pic_james()]
PIC_PALS = [["#f8f8f8", "#f8d0a0", "#b83848", "#201828"], ["#f8f8f8", "#f8d0a0", "#209048", "#201828"],
            ["#f8f8f8", "#f8d0a0", "#208898", "#201828"], ["#f8f8f8", "#f8d0a0", "#7038a8", "#201828"]]

def boveen():           # grass: a bog calf reared up on its hind legs, hooves raised
    A = Art()
    A.line([(46, 50), (53, 53), (58, 48), (59, 41)], 3, width=2)                    # tail
    for cx, cy in ((59, 35), (55, 39), (62, 40)):
        A.form(oval(cx, cy, 3.5, 3.5), 1, 2, depth=1, cast=0)
    A.form([(47, 34), (54, 27), (57, 19), (62, 22), (60, 32), (52, 41)], 2, 3, depth=2)   # far arm
    A.form(oval(58, 17, 5, 5), 3, cast=0)
    A.form([(9, 51), (20, 47), (27, 52), (27, 62), (8, 62)], 4, 1, depth=2)        # hind legs
    A.form([(36, 52), (44, 47), (53, 51), (55, 62), (35, 62)], 4, 1, depth=2)
    A.box(9, 58, 26, 61, 3); A.box(36, 58, 54, 61, 3)
    A.dots([(17, 58), (17, 59), (45, 58), (45, 59)], 1)
    body = [(14, 30), (22, 25), (38, 25), (48, 30), (50, 42), (47, 53), (38, 58), (24, 58), (15, 52), (12, 41)]
    A.form(body, 4, 1, depth=3)
    A.form([(13, 31), (22, 25), (38, 25), (49, 31), (49, 37), (44, 41), (39, 37), (34, 42), (29, 37), (24, 42),
            (19, 37), (14, 40)], 1, 2, depth=3, cast=0)                             # moss mantle, scalloped
    A.texture([(13, 26), (49, 26), (49, 42), (13, 42)], 1, 2, "speck")
    A.line([(26, 46), (31, 49), (36, 46)], 1); A.line([(28, 52), (31, 54), (34, 52)], 1)   # belly creases
    A.form([(18, 37), (8, 32), (2, 25), (8, 21), (13, 27), (21, 31)], 4, 1, depth=1)        # near arm
    A.form(oval(5, 20, 5.5, 5.5), 2, 3, depth=2, cast=0)
    A.line([(3, 20), (7, 20)], 3)
    for pts in ([(19, 12), (12, 9), (8, 2), (13, 0), (16, 5), (22, 8)], [(45, 12), (52, 9), (56, 2), (51, 0), (48, 5), (42, 8)]):
        A.form(pts, 1, 2, depth=1, cast=0)                                          # fern-curl horns
    A.line([(12, 3), (15, 7)], 3); A.line([(52, 3), (49, 7)], 3)
    A.form([(16, 15), (5, 11), (7, 19), (15, 21)], 1, 2, depth=1, smooth=False, cast=0)    # leaf ears
    A.form([(48, 15), (59, 11), (57, 19), (49, 21)], 1, 2, depth=1, smooth=False, cast=0)
    A.line([(14, 17), (8, 14)], 3); A.line([(50, 17), (56, 14)], 3)
    A.form([(15, 10), (24, 5), (40, 5), (49, 10), (51, 20), (47, 30), (38, 34), (26, 34), (17, 30), (13, 20)], 4, 1, depth=2)
    for cx, cy in ((32, 8), (28, 12), (36, 12)):                                    # clover blaze
        A.form(oval(cx, cy, 3.4, 3.4), 1, None, cast=0, outline=0)
    A.line([(32, 12), (33, 16)], 1)
    A.form([(20, 24), (26, 20), (38, 20), (44, 24), (45, 30), (40, 35), (24, 35), (19, 30)], 5, None, cast=0)  # muzzle
    A.form(oval(26, 27, 2.6, 3), 3, cast=0); A.form(oval(38, 27, 2.6, 3), 3, cast=0)
    A.line([(26, 32), (32, 33), (38, 31)], 3)
    A.dots([(22, 23), (23, 22), (41, 22)], 4)
    for x, sgn in ((20, 1), (37, -1)):                                              # heavy-lidded eyes
        A.box(x, 15, x + 7, 15, 3); A.box(x + 1, 16, x + 6, 18, 3); A.box(x + 2, 19, x + 5, 19, 3)
        A.dots([(x + 2, 17), (x + 3, 17)], 4)
    A.line([(18, 13), (28, 15)], 3, width=2); A.line([(46, 13), (36, 15)], 3, width=2)
    A.dots([(18, 7), (19, 7), (20, 6), (18, 44), (19, 45), (17, 46)], 4)
    return A.done()

def ruakit():           # fire: a fox rearing to strike, jaws open, its tail and mane alight
    A = Art()
    # --- tail: a whipping S of flame with a white-hot core and loose tongues of fire
    A.form([(43, 47), (52, 45), (60, 39), (63, 28), (59, 18), (61, 8), (55, 1), (56, 11), (50, 6), (53, 17),
            (47, 14), (51, 25), (46, 29), (49, 38)], 1, 2, depth=3, cast=0)
    A.form([(51, 43), (58, 34), (59, 22), (57, 9), (53, 19), (50, 27), (48, 36)], 5, None, cast=0, outline=0)
    A.form([(52, 41), (57, 33), (57, 23), (56, 12), (54, 20), (51, 28), (50, 36)], 4, None, cast=0, outline=0)
    A.line([(54, 38), (58, 30), (58, 22)], 1); A.line([(49, 33), (50, 29)], 3); A.line([(55, 16), (55, 10)], 1)
    for pts in ([(46, 8), (47, 2), (50, 9)], [(60, 5), (63, 0), (63, 8)], [(43, 22), (42, 16), (46, 21)]):
        A.form(pts, 5, None, smooth=False, cast=0)
    # --- far-side limbs, in shadow
    A.form([(35, 46), (44, 47), (43, 55), (47, 61), (36, 61), (34, 54)], 2, 3, depth=2, cast=0)
    A.dots([(38, 60), (41, 60), (44, 60)], 1)
    A.form([(15, 41), (22, 43), (17, 51), (9, 55), (4, 52), (10, 47)], 2, 3, depth=2, cast=0)
    A.dots([(4, 53), (6, 55), (8, 56)], 4); A.line([(12, 48), (15, 50)], 3)
    A.form([(11, 15), (11, 1), (21, 11)], 2, 3, depth=1, smooth=False, cast=0)       # far ear
    A.dots([(11, 1), (11, 2), (12, 3)], 3)
    # --- torso, arching up toward the head
    A.form([(21, 31), (31, 24), (44, 26), (52, 33), (55, 44), (47, 51), (32, 49), (21, 43)], 1, 2, depth=5)
    A.form([(23, 41), (33, 46), (46, 48), (45, 51), (32, 50), (22, 45)], 4, 1, depth=1, cast=0, outline=0)
    A.line([(35, 29), (38, 35)], 2); A.line([(41, 29), (44, 35)], 2)               # back stripes
    # --- flames along the neck and spine
    for pts, core in (([(27, 27), (28, 11), (34, 25)], [(29, 23), (29, 16), (32, 23)]),
                      ([(33, 26), (38, 9), (41, 26)], [(36, 23), (38, 15), (39, 24)]),
                      ([(40, 27), (46, 13), (48, 29)], [(43, 25), (45, 18), (46, 26)]),
                      ([(47, 31), (54, 21), (53, 34)], [(49, 30), (52, 25), (52, 31)])):
        A.form(pts, 5, 1, depth=1, smooth=False, cast=0)
        A.form(core, 4, None, smooth=False, cast=0, outline=0)
    # --- near hind leg: thigh, hock and a clawed foot
    A.form([(39, 38), (50, 35), (58, 42), (58, 52), (52, 56), (54, 61), (41, 61), (44, 54), (38, 48)], 1, 2, depth=4)
    A.line([(41, 41), (47, 38), (54, 42)], 2); A.line([(46, 55), (51, 56)], 3)
    A.box(42, 58, 53, 60, 3); A.dots([(43, 61), (46, 61), (49, 61), (52, 61)], 4)
    A.form([(41, 42), (44, 38), (47, 42), (44, 46)], 5, None, smooth=False, cast=0, outline=0)    # ember mark
    # --- chest ruff: thick white fur in ragged locks
    A.form([(14, 33), (12, 43), (17, 41), (17, 49), (22, 45), (24, 52), (28, 45), (32, 40), (26, 31)],
           4, 1, depth=1, smooth=False)
    A.line([(19, 37), (20, 41)], 1); A.line([(25, 37), (25, 42)], 1)
    # --- near foreleg, raised and bent, claws out
    A.form([(23, 44), (31, 42), (34, 49), (29, 56), (22, 61), (15, 59), (20, 52)], 1, 2, depth=3)
    A.line([(25, 47), (29, 50)], 2); A.line([(18, 56), (22, 58)], 3)
    for pts in ([(15, 57), (11, 60), (16, 60)], [(17, 59), (14, 63), (19, 62)], [(20, 60), (19, 63), (23, 62)]):
        A.form(pts, 4, None, smooth=False, cast=0)                                  # claws
    # --- head, three-quarter view
    A.form([(22, 14), (27, 0), (35, 14)], 1, 2, depth=2, smooth=False, cast=0)       # near ear
    A.form([(25, 12), (28, 4), (32, 12)], 2, None, smooth=False, cast=0, outline=0)
    A.dots([(27, 0), (27, 1), (28, 2), (26, 2)], 3)
    A.form([(6, 23), (11, 15), (21, 10), (31, 12), (37, 21), (35, 31), (27, 36), (16, 35)], 1, 2, depth=3)   # skull
    A.form([(18, 12), (20, 3), (24, 11)], 5, 1, depth=1, smooth=False, cast=0)       # forehead flame
    A.form([(14, 28), (24, 27), (33, 28), (39, 30), (34, 32), (38, 37), (30, 35), (22, 37), (15, 35)],
           4, 1, depth=1, smooth=False, cast=0, outline=2)                          # white cheek, ragged at the back
    A.form([(1, 30), (7, 24), (16, 25), (19, 32), (13, 36), (4, 35)], 1, 2, depth=2, cast=0)                 # muzzle
    A.form([(5, 37), (13, 37), (18, 40), (12, 44), (5, 42)], 4, 1, depth=1, cast=0)  # lower jaw
    A.form([(4, 34), (14, 33), (18, 37), (16, 39), (6, 38)], 3, None, cast=0, outline=0)                     # open mouth
    A.form([(6, 34), (9, 34), (7, 38)], 4, None, smooth=False, cast=0, outline=0)    # fangs
    A.form([(12, 34), (15, 34), (14, 38)], 4, None, smooth=False, cast=0, outline=0)
    A.line([(8, 39), (13, 39)], 2)                                                  # tongue
    A.form(oval(2.5, 29.5, 2.6, 2.6), 3, cast=0)
    A.dots([(2, 28)], 1)
    A.dots([(8, 28), (10, 30), (12, 28)], 3)                                        # whisker spots
    A.line([(11, 21), (18, 16), (28, 17)], 3, width=2)                              # near brow
    A.form([(14, 24), (20, 19), (27, 21), (25, 26), (17, 27)], 4, None, smooth=False, cast=0)   # near eye
    A.box(20, 21, 21, 25, 3); A.dots([(22, 22)], 1)
    A.line([(24, 28), (28, 26)], 2); A.line([(26, 30), (30, 28)], 2)                # cheek stripes
    # --- white glints where the light catches: brow, muzzle, shoulder, thigh
    for pts in ([(12, 18), (16, 14), (18, 15), (14, 19)], [(5, 26), (9, 25), (9, 27), (6, 28)],
                [(30, 27), (35, 26), (36, 28), (31, 30)], [(47, 38), (52, 38), (53, 41), (48, 41)],
                [(24, 46), (27, 45), (27, 49), (25, 50)]):
        A.form(pts, 4, None, smooth=False, cast=0, outline=0)
    # --- embers kicked up at its feet
    A.dots([(8, 61), (10, 59), (30, 62), (33, 60), (57, 60), (60, 58), (61, 61)], 5)
    A.dots([(9, 62), (59, 61)], 3)
    return A.done()

def dovran():           # water: a river-hound pup on its hind legs, one paw raised, spiral on its belly
    A = Art()
    A.form([(45, 52), (55, 46), (55, 33), (60, 40), (63, 27), (63, 46), (58, 56), (48, 60)], 2, 3, depth=2, smooth=False)
    A.line([(56, 46), (61, 36)], 1); A.line([(57, 51), (62, 44)], 1)                # tail fluke
    A.form([(38, 30), (46, 27), (52, 31), (50, 38), (42, 40)], 2, 3, depth=2)       # far arm
    A.line([(46, 37), (47, 40)], 3); A.line([(49, 36), (51, 39)], 3)
    A.form([(27, 40), (40, 36), (52, 40), (56, 50), (50, 59), (36, 61), (26, 55)], 1, 2, depth=5)   # hips
    A.form([(15, 55), (22, 52), (29, 55), (29, 62), (14, 62)], 1, 2, depth=2)       # feet
    A.form([(35, 55), (42, 52), (49, 55), (50, 62), (34, 62)], 1, 2, depth=2)
    for x in (18, 21, 24, 38, 41, 44):
        A.line([(x, 58), (x, 61)], 3)
    A.form([(15, 28), (24, 22), (36, 22), (44, 28), (45, 42), (40, 53), (26, 55), (17, 48), (13, 38)], 1, 2, depth=5)   # torso
    A.texture([(30, 24), (45, 26), (46, 52), (36, 52)], 1, 2, "fur")
    A.form([(19, 32), (27, 28), (35, 31), (38, 42), (34, 52), (25, 53), (19, 45)], 4, 1, depth=1, cast=0, outline=0)    # belly
    A.form([(31, 46), (40, 44), (47, 49), (45, 57), (35, 58)], 4, 1, depth=1, cast=0, outline=0)
    im = Image.fromarray(A.a); dr = ImageDraw.Draw(im)                              # spiral
    dr.arc((21, 33, 35, 47), 30, 330, fill=5, width=2); dr.arc((25, 37, 31, 43), 200, 500, fill=5)
    A.a = np.array(im)
    A.form([(17, 37), (9, 31), (1, 21), (5, 15), (12, 23), (21, 30)], 1, 2, depth=3)   # raised paw
    for x in (2, 5, 8):
        A.line([(x, 20), (x + 1, 16)], 3)
    A.form([(17, 11), (21, 0), (27, 6), (33, 0), (37, 10)], 5, 1, depth=1, smooth=False, cast=0)   # crest
    A.line([(22, 3), (24, 9)], 3); A.line([(32, 3), (31, 9)], 3)
    A.form([(44, 14), (53, 9), (48, 22)], 2, 3, depth=1, smooth=False, cast=0)      # ear fins
    A.form([(8, 14), (0, 10), (4, 21)], 1, 2, depth=1, smooth=False, cast=0)
    A.form([(7, 18), (10, 9), (20, 5), (34, 5), (44, 10), (47, 20), (43, 29), (33, 33), (19, 33), (10, 28)], 1, 2, depth=4)  # head
    A.texture([(30, 6), (46, 10), (46, 22), (36, 18)], 1, 2, "fur")
    A.form([(16, 24), (20, 19), (32, 18), (37, 23), (36, 30), (27, 33), (18, 30)], 4, 1, depth=2, cast=0, outline=0)    # muzzle
    for x in (9, 31):                                                               # goggle eyes, glancing sideways
        A.form(oval(x + 5.5, 14.5, 6, 6), 4, None, cast=0)
        A.form(oval(x + 3.5, 15.5, 2.3, 2.6), 3, cast=0)
        A.dots([(x + 3, 14)], 4)
        A.line([(x + 1, 10), (x + 10, 9)], 3)
    A.form(oval(26, 22, 3.2, 2.2), 3, cast=0)
    A.line([(26, 24), (26, 27)], 3); A.line([(20, 28), (26, 30), (33, 27)], 3)      # smirk
    A.form([(30, 28), (33, 27), (32, 31)], 4, smooth=False, cast=0)
    for y0, y1 in ((24, 21), (27, 29)):
        A.line([(37, y0), (50, y1)], 3)
    A.dots([(18, 25), (20, 26), (19, 27)], 1)
    for cx, cy, r in ((56, 12, 4), (60, 22, 2), (8, 54, 3)):                        # bubbles
        A.form(oval(cx, cy, r, r), 4, 1, depth=0, cast=0)
    A.dots([(55, 10), (20, 8), (21, 7), (22, 7), (15, 31), (16, 30)], 4)
    return A.done()

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

# ---------------------------------------------------------------- back views
# What you see of your own PMON in battle: from behind, looking up and to the
# right at its opponent.
def boveen_back():
    A = Art()
    A.line([(14, 52), (6, 47), (4, 39)], 3, width=2)                                # tail and clover
    for cx, cy in ((5, 32), (2, 37), (9, 36)):
        A.form(oval(cx, cy, 3.4, 3.4), 1, 2, depth=1, cast=0)
    A.line([(5, 33), (6, 38)], 3)
    A.form([(48, 38), (56, 31), (59, 25), (63, 29), (60, 38), (52, 44)], 4, 1, depth=1)   # raised arm
    A.form(oval(60, 24, 4, 4), 2, 3, depth=1, cast=0)
    A.form([(12, 38), (24, 29), (40, 29), (50, 38), (52, 52), (45, 62), (18, 62), (10, 52)], 4, 1, depth=3)   # body
    A.form([(12, 38), (24, 29), (40, 29), (50, 38), (51, 47), (45, 52), (39, 47), (33, 53), (27, 47), (21, 53),
            (15, 47), (11, 50)], 1, 2, depth=4, cast=0)                             # moss mantle
    A.texture([(11, 30), (51, 30), (51, 53), (11, 53)], 1, 2, "speck")
    for x in (23, 29, 35):                                                          # grass along the spine
        A.form([(x, 36), (x + 2, 27), (x + 4, 34), (x + 6, 28), (x + 7, 37)], 1, 2, depth=1, smooth=False, cast=0)
    A.line([(20, 56), (31, 58), (42, 56)], 1)
    A.box(14, 59, 25, 62, 3); A.box(37, 59, 48, 62, 3)
    A.dots([(19, 59), (19, 60), (42, 59), (42, 60)], 1)
    A.form([(37, 11), (31, 7), (30, 0), (35, 1), (37, 5), (41, 8)], 1, 2, depth=1, cast=0)   # horns
    A.form([(51, 10), (57, 6), (62, 0), (58, 0), (54, 4), (48, 8)], 1, 2, depth=1, cast=0)
    A.line([(33, 3), (36, 7)], 3); A.line([(58, 3), (55, 7)], 3)
    A.form([(34, 19), (23, 15), (26, 23), (34, 25)], 1, 2, depth=1, smooth=False, cast=0)    # ears
    A.form([(55, 18), (63, 15), (62, 23), (55, 24)], 1, 2, depth=1, smooth=False, cast=0)
    A.line([(32, 21), (27, 19)], 3)
    A.form(oval(44, 19, 12, 11), 4, 1, depth=2)                                     # head
    A.form([(33, 15), (38, 9), (46, 7), (54, 10), (56, 16), (49, 14), (44, 18), (39, 14), (35, 18)],
           1, 2, depth=1, cast=0, outline=2)                                        # mossy crown
    A.form([(53, 22), (60, 21), (63, 25), (62, 30), (55, 31)], 5, None, cast=0)     # muzzle
    A.dots([(60, 25), (60, 26)], 3)
    A.line([(50, 20), (55, 21)], 3, width=2)
    A.dots([(36, 20), (37, 19), (38, 19), (15, 36), (16, 35), (17, 35)], 4)
    return A.done()

def ruakit_back():
    A = Art()
    A.form([(15, 51), (8, 41), (3, 28), (7, 14), (13, 3), (13, 15), (19, 11), (16, 23), (22, 23), (19, 35), (25, 44)],
           1, 2, depth=3, cast=0)                                                   # flame tail
    A.form([(14, 45), (8, 32), (10, 17), (13, 25), (17, 31), (18, 41)], 5, None, cast=0, outline=0)
    A.form([(13, 41), (10, 31), (11, 22), (13, 28), (15, 33), (16, 39)], 4, None, cast=0, outline=0)
    for pts in ([(20, 8), (21, 2), (24, 9)], [(1, 20), (0, 13), (4, 19)]):
        A.form(pts, 5, None, smooth=False, cast=0)
    A.form([(11, 55), (22, 53), (25, 62), (9, 62)], 2, 3, depth=1, cast=0)
    A.form([(13, 41), (24, 32), (38, 32), (48, 40), (51, 54), (45, 62), (18, 62), (11, 54)], 1, 2, depth=5)   # haunches
    A.line([(30, 37), (31, 60)], 2)                                                 # spine
    A.line([(16, 47), (21, 42), (27, 43)], 2); A.line([(46, 47), (41, 42), (35, 43)], 2)
    A.line([(19, 51), (27, 49)], 2); A.line([(43, 51), (36, 49)], 2)
    A.form([(39, 54), (50, 55), (53, 62), (37, 62)], 1, 2, depth=2)
    A.box(39, 60, 52, 62, 3); A.box(10, 60, 24, 62, 3)
    A.dots([(41, 60), (45, 60), (49, 60), (13, 60), (17, 60), (21, 60)], 1)
    A.form([(27, 31), (37, 22), (48, 24), (51, 34), (41, 39), (30, 38)], 1, 2, depth=3)   # shoulders
    A.line([(33, 31), (38, 27)], 2); A.line([(44, 28), (47, 33)], 2)
    for pts, core in (([(22, 39), (23, 26), (28, 37)], [(24, 35), (24, 30), (26, 35)]),
                      ([(27, 35), (29, 20), (34, 33)], [(29, 31), (30, 25), (32, 31)]),
                      ([(33, 31), (37, 16), (40, 30)], [(35, 28), (37, 22), (38, 28)])):
        A.form(pts, 5, 1, depth=1, smooth=False, cast=0)
        A.form(core, 4, None, smooth=False, cast=0, outline=0)
    A.form([(37, 16), (36, 0), (46, 10)], 1, 2, depth=2, smooth=False, cast=0)       # ears, seen from behind
    A.form([(50, 11), (58, 0), (60, 16)], 1, 2, depth=2, smooth=False, cast=0)
    A.dots([(36, 0), (36, 1), (37, 2), (58, 0), (58, 1), (57, 2)], 3)
    A.form([(34, 21), (37, 12), (46, 8), (55, 11), (60, 21), (56, 30), (44, 33), (36, 28)], 1, 2, depth=3)   # head
    A.line([(40, 17), (43, 21)], 2); A.line([(46, 14), (49, 19)], 2)
    A.form([(57, 20), (63, 21), (62, 25), (58, 27)], 1, 2, depth=1, cast=0)         # snout
    A.dots([(62, 22), (63, 22), (62, 23), (63, 23)], 3)
    A.form([(51, 26), (61, 27), (55, 31), (60, 37), (50, 33)], 4, 1, depth=1, smooth=False, cast=0)   # cheek fur
    A.line([(53, 17), (58, 19)], 3, width=2)
    A.dots([(39, 14), (40, 13), (41, 13), (17, 39), (18, 38), (19, 38)], 4)
    return A.done()

def dovran_back():
    A = Art()
    A.form([(17, 55), (7, 49), (2, 37), (0, 24), (6, 31), (8, 22), (13, 35), (19, 45)], 2, 3, depth=2, smooth=False, cast=0)
    A.line([(6, 44), (4, 32)], 1); A.line([(11, 46), (9, 32)], 1)                   # tail fluke
    A.form([(46, 38), (54, 33), (61, 26), (63, 33), (58, 40), (50, 44)], 1, 2, depth=2)   # raised paw
    for x in (58, 60, 62):
        A.line([(x, 29), (x + 1, 25)], 3)
    A.form([(13, 40), (24, 30), (40, 30), (48, 39), (51, 52), (45, 62), (18, 62), (11, 52)], 1, 2, depth=5)   # body
    A.form([(28, 32), (35, 32), (37, 46), (35, 60), (28, 60), (26, 46)], 2, None, cast=0, outline=0)          # dorsal stripe
    A.line([(17, 44), (22, 40)], 2); A.line([(45, 44), (41, 40)], 2)
    A.texture([(37, 32), (49, 39), (50, 56), (39, 58)], 1, 2, "fur")
    A.form([(10, 56), (21, 54), (24, 62), (9, 62)], 1, 2, depth=2)
    A.form([(40, 54), (51, 56), (53, 62), (38, 62)], 1, 2, depth=2)
    for x in (13, 16, 19, 43, 46, 49):
        A.line([(x, 59), (x, 62)], 3)
    A.form([(38, 11), (41, 0), (46, 6), (51, 0), (54, 11)], 5, 1, depth=1, smooth=False, cast=0)   # crest
    A.line([(42, 3), (43, 9)], 3); A.line([(50, 3), (49, 9)], 3)
    A.form([(31, 16), (22, 11), (26, 24)], 1, 2, depth=1, smooth=False, cast=0)     # ear fins
    A.form([(58, 14), (63, 9), (63, 22)], 2, 3, depth=1, smooth=False, cast=0)
    A.form([(28, 19), (33, 10), (45, 7), (56, 10), (61, 20), (57, 29), (45, 33), (33, 30)], 1, 2, depth=3)   # head
    A.form([(35, 10), (45, 7), (49, 11), (47, 31), (40, 32), (38, 13)], 2, None, cast=0, outline=0)
    A.form([(51, 25), (60, 23), (59, 30), (50, 32)], 4, 1, depth=1, cast=0, outline=2)   # cheek
    A.form(oval(57, 18, 3.6, 3.6), 4, None, cast=0)                                 # the edge of one eye
    A.dots([(58, 18), (59, 18), (58, 19), (59, 19)], 3)
    A.dots([(31, 14), (32, 13), (33, 13), (16, 38), (17, 37), (18, 37)], 4)
    return A.done()

def girrin_back():
    A = Art()
    A.form(oval(19, 59, 10, 4), 1, 2, depth=1, cast=0); A.form(oval(45, 59, 10, 4), 1, 2, depth=1, cast=0)
    A.form([(19, 39), (11, 35), (12, 30), (21, 34)], 1, 2, depth=1, cast=0)
    A.form(oval(9, 30, 5, 5), 1, 2, depth=2, cast=0)
    A.form([(45, 39), (54, 34), (52, 29), (43, 34)], 1, 2, depth=1, cast=0)
    A.form(oval(56, 28, 5, 5), 4, 1, depth=1, cast=0)
    A.form([(15, 37), (26, 28), (38, 28), (49, 37), (51, 51), (45, 60), (19, 60), (13, 51)], 1, 2, depth=5)
    A.form(oval(32, 52, 6.5, 6), 4, 1, depth=2)
    A.line([(24, 36), (28, 40)], 2); A.line([(40, 36), (36, 40)], 2)
    A.form([(26, 15), (21, 3), (25, 0), (31, 3), (33, 14)], 1, 2, depth=2, cast=0)
    A.form([(38, 14), (42, 3), (48, 0), (57, 7), (54, 10), (47, 6), (44, 15)], 1, 2, depth=1, cast=0)
    A.form([(20, 21), (23, 13), (33, 10), (44, 12), (49, 20), (47, 28), (36, 32), (24, 29)], 1, 2, depth=3)
    A.form([(44, 22), (50, 22), (49, 28), (43, 29)], 4, 1, depth=1, cast=0, outline=2)
    A.form(oval(46, 18, 3.4, 3.4), 4, None, cast=0)
    A.dots([(47, 18), (48, 18)], 3)
    A.dots([(24, 15), (25, 14), (26, 14), (18, 35), (19, 34)], 4)
    return A.done()

def spidge_back():
    A = Art()
    A.line([(26, 54), (23, 61)], 3, width=2); A.line([(38, 54), (41, 61)], 3, width=2)
    A.line([(18, 62), (28, 62)], 3); A.line([(36, 62), (46, 62)], 3)
    A.form([(21, 49), (8, 57), (5, 63), (22, 62), (29, 54)], 2, 3, depth=1, smooth=False, cast=0)
    A.line([(11, 60), (22, 53)], 3); A.line([(16, 62), (25, 55)], 3)
    A.form(oval(32, 36, 20, 21), 2, 3, depth=4)
    A.form([(13, 31), (24, 26), (29, 44), (21, 53), (11, 45)], 2, 3, depth=2)
    A.form([(51, 31), (40, 26), (35, 44), (43, 53), (53, 45)], 2, 3, depth=2)
    for y in (34, 39, 44):
        A.line([(15, y), (25, y + 3)], 3); A.line([(49, y), (39, y + 3)], 3)
    A.form([(27, 17), (29, 6), (32, 13), (36, 5), (38, 17)], 2, 3, depth=1, smooth=False, cast=0)
    A.form([(45, 21), (53, 23), (52, 32), (45, 31)], 1, 2, depth=1, cast=0, outline=0)
    A.form([(51, 22), (60, 25), (52, 28)], 4, None, smooth=False, cast=0)
    A.dots([(48, 21), (49, 21), (48, 22), (49, 22)], 3)
    A.dots([(22, 22), (23, 21), (24, 21)], 4); A.dots([(20, 24), (22, 26)], 1)
    return A.done()

def granog_back():
    A = Art()
    cx, cy = 30, 36
    for k in range(18):
        t = k * 2 * np.pi / 18
        bx, by = cx + 21 * np.cos(t), cy + 22 * np.sin(t)
        A.form([(bx - 5 * np.sin(t), by + 5 * np.cos(t)), (bx + 5 * np.sin(t), by - 5 * np.cos(t)),
                (cx + 30 * np.cos(t), cy + 31 * np.sin(t))], 2, 3, depth=1, smooth=False, cast=0)
    A.form(oval(cx, cy, 22, 23), 2, 3, depth=5, cast=0)
    A.texture(oval(cx, cy, 20, 21), 2, 3, "scales")
    A.form(oval(20, 60, 7, 3.5), 1, 2, depth=1, cast=0); A.form(oval(40, 60, 7, 3.5), 1, 2, depth=1, cast=0)
    A.form(oval(46, 23, 3.5, 3.5), 1, 2, depth=1, cast=0)
    A.form([(46, 27), (56, 28), (63, 34), (56, 40), (46, 40)], 1, 2, depth=2, cast=0)
    A.form(oval(61, 34, 2.4, 2.4), 3, cast=0)
    A.line([(50, 29), (56, 30)], 3, width=2); A.dots([(53, 32), (54, 32)], 3)
    A.dots([(16, 22), (17, 21), (18, 21)], 1)
    return A.done()

def gandal():           # flying: a white-fronted goose, wings up, honking
    A = Art()
    A.form([(19, 31), (5, 21), (0, 33), (5, 45), (19, 47)], 2, 3, depth=2, smooth=False, cast=0)   # far wing
    for y in (27, 33, 39):
        A.line([(4, y), (16, y + 4)], 3)
    A.form([(17, 46), (8, 53), (19, 55)], 2, 3, depth=1, smooth=False, cast=0)       # tail
    A.form([(24, 57), (22, 63), (32, 63), (30, 57)], 5, None, smooth=False, cast=0)  # feet
    A.form([(38, 57), (36, 63), (46, 63), (44, 57)], 5, None, smooth=False, cast=0)
    A.form([(18, 31), (30, 26), (44, 30), (51, 42), (47, 54), (32, 58), (20, 53), (16, 41)], 1, 2, depth=5)   # body
    A.form([(24, 44), (34, 42), (44, 46), (42, 54), (32, 57), (24, 52)], 4, 1, depth=1, cast=0, outline=0)
    for y in (46, 50, 54):                                                          # the belly bars of its kind
        A.line([(27, y), (40, y)], 2)
    A.form([(43, 31), (58, 19), (63, 31), (59, 45), (47, 47)], 1, 2, depth=3, smooth=False)   # near wing, raised
    for y in (26, 32, 38):
        A.line([(60, y), (48, y + 5)], 3)
    A.form([(29, 30), (26, 17), (29, 8), (37, 8), (39, 18), (41, 30)], 1, 2, depth=3)        # neck
    A.form([(27, 8), (31, 2), (40, 1), (45, 6), (41, 13), (31, 14)], 1, 2, depth=2, cast=0)  # head
    A.form([(39, 2), (44, 5), (42, 9), (38, 6)], 4, None, smooth=False, cast=0, outline=0)   # white front
    A.form([(43, 4), (55, 2), (46, 9)], 5, None, smooth=False, cast=0)               # bill, wide open
    A.form([(43, 10), (53, 13), (44, 14)], 5, None, smooth=False, cast=0)
    A.line([(31, 4), (37, 5)], 3, width=2)
    A.dots([(35, 7), (36, 7), (35, 8), (36, 8)], 3); A.dots([(35, 7)], 4)
    A.dots([(22, 34), (23, 33), (24, 33)], 4)
    return A.done()

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
         ("SODKICK", "GROUND", 40, 95, 0), ("NIP", "DARK", 40, 100, 0), ("SQUALL", "FLYING", 45, 95, 0)]
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
    ("GANDAL", "FLYING", gandal(), ["#f8f8f0", "#a89880", "#584838", "#181010"], (55, 55, 50, 50, 45), 90, 60,
     [(1, "PECK"), (1, "BELLOW"), (8, "SQUALL")]),
]
ACCENT = {"BOVEEN": "#f0a0b0", "RUAKIT": "#f8d038", "DOVRAN": "#f8c838", "GANDAL": "#f09030"}     # a second palette's extra colour

def encode_art(px):
    """Each 8x8 tile uses palette A, or palette B if it holds any accent pixels.
    Returns the 2bpp bytes, one mask byte per tile row (bit set = palette B), and
    the picture as colour roles 0 white, 1 hue, 2 shade, 3 line, 5 accent, as shown."""
    data, mask, shown = [], [], px.copy()
    for ty in range(8):
        bits = 0
        for tx in range(8):
            t = px[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8]
            if (t == 5).any():                      # palette B: the shade falls back to the plain hue
                bits |= 0x80 >> tx
                idx = np.select([t == 5, t == 1, t == 2, t == 3], [1, 2, 2, 3], 0)
                shown[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8] = np.where(t == 2, 1, t)
            else:
                idx = t
            data += to2bpp(idx.astype(np.uint8))
        mask.append(bits)
    return data, mask, shown

BACKS = {"BOVEEN": boveen_back(), "RUAKIT": ruakit_back(), "DOVRAN": dovran_back(),
         "GIRRIN": girrin_back(), "SPIDGE": spidge_back(), "GRANOG": granog_back()}
GESTURE = {"BOVEEN": 0, "RUAKIT": 1, "DOVRAN": 2, "GIRRIN": 0, "SPIDGE": 0, "GRANOG": 3, "FAOLAN": 1, "GANDAL": 0}
STARTERS = [(s[0], s[1], s[2], k) for s, k in zip(SPECIES[:3], (K_GRASS, K_FIRE, K_WATER))]
bar_tiles = []
for k in range(9):          # HP bar segments, 0..8 pixels filled
    t = np.zeros((8, 8), np.uint8); t[1, :] = 3; t[6, :] = 3; t[2:6, :] = 2; t[2:6, :k] = 1
    bar_tiles.append(t)
ICONS = [("SHAMROCK", shamrock(), K_GRASS), ("TURF FIRE", flame(), K_FIRE), ("RAINDROP", raindrop(), K_WATER)]

# ---------------------------------------------------------------- maps
PATHLIKE = set("=BQ")
def compile_map(rows, name, outdoor=1):
    global POOL
    h, w = len(rows), len(rows[0])
    assert all(len(r) == w for r in rows) and w <= 32 and h <= 32
    stamp, doors = {}, set()
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch in BUILDINGS and outdoor:
                b = BUILDINGS[ch]
                art_px = b["art"]() if b["art"] else H
                POOL = "x:" + name if b["own"] else "out"
                for j in range(3):
                    for i in range(b.get("w", 4)):
                        door = j == 2 and i in b["doors"]
                        stamp[(x + i, y + j)] = mt_id(art_px[j * 16:j * 16 + 16, i * 16:i * 16 + 16], b["pal"],
                                                      SOLID | (DOOR if door else 0))
                        if door: doors.add((x + i, y + j))
                POOL = "out"
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
    "ROUTE1": "ROUTE 1|North: the WEXFORD road. South: NEW ROSS.",
    "CALL": "RING RING! RING RING!|MOM: @, are you on the Wexford road? Did you bring a coat?|"
            "It's going to lash. It always does. Mind yourself, pet!",
    "ROUTE2": "ROUTE 2|WEXFORD TOWN, east. Shelter recommended.",
    "SLEEPER": "A GRANOG is curled up asleep across the path.|...It woke up. It is not pleased!",
    "CASH": "@ won %# for the win!",
    "NURSE": "NURSE: Welcome to the PMON CENTRE. Give me a moment with your team.",
    "CLERK": "CLERK: Welcome to the MART! What can I get you?",
    "BYE": "CLERK: Mind how you go!",
    "RIVER": "The BARROW runs deep here. No swimming.",
    "SLOBS": "THE SLOBS, east across the water. Ten thousand geese winter there.",
    "TERRACE": "The door is shut. Someone is practising the tin whistle inside.",
    "STASH": "Something glints among the flowers...|@ found 3 PBALLs!",
    "EMPTY": "Nothing but flowers now.",
    "HURL0": "CONOR: Hey! You walked right across my puck-out! Battle me!",
    "HURL1": "CONOR: Fair play to you. Mind the GRANOG up the road. It's cranky when it's woken.",
    "RUTH": "RUTH: @! Welcome to WEXFORD. ALEX said you'd be along. Here, I've sandwiches.|"
            "Listen. PMONs are going missing along the coast. ALEX has gone to HOOK HEAD to look.|"
            "Get your badge first. ORLA's gym has the gold roof. The red roof up ahead is the PMON CENTRE.",
    "WEXFORD": "WEXFORD TOWN|Loch Garman. One long street, and the sea beside it.",
    "ABBEY": "SELSKAR ABBEY|Eight hundred years old and still standing. Mostly.",
    "PIKEMAN": "THE BULLRING|A bronze pikeman keeps watch over the old market square.",
    "FISHER": "TOMAS: Best mussels in Ireland out of this harbour. The geese over on the SLOBS would agree.",
    "NORTH2": "The bridge north over the SLANEY is closed today.",
    "MAEVE0": "MAEVE: Off to face ORLA, are you? Take this. My own tonic: honey, lemon and something I won't name.|"
              "@ got 2 POTIONs!|MAEVE: Press START and then LEFT when one of yours is hurt. The MART sells more.",
    "MAEVE1": "MAEVE: Mind that tonic. It would wake the dead.",
    "KID": "CIAN: The geese fly here all the way from GREENLAND. I get tired walking to school.",
    "SINGER": "FIONNUALA: Every October half of Europe squeezes into this street for the opera.|"
              "They say a PMON once sang back to us from the harbour. A voice like the tide.",
    "HUSH": "Shh! She's warming up.",
    "POTION": "The POTION restored some HP.",
    "NOPOTION": "Nobody needs a POTION just now.",
    "SOUTH2": "The road south to ROSSLARE isn't finished yet.",
    "STATUE": "A statue of a goose in full flight.",
    "GYMT0": "AOIFE: Nobody gets to ORLA without ruffling my feathers first!",
    "GYMT1": "AOIFE: Grounded. The gate? The birds open it. Wake them from the lowest song to the highest.",
    "ORLA0": "ORLA: Welcome to WEXFORD GYM. Every winter the wild geese cross an ocean to get here.|"
             "Let's see if you have that kind of heart!",
    "ORLA1": "ORLA: You flew higher than I expected. Take the FEATHER BADGE.",
    "ORLA2": "ORLA: The next gym is in KILKENNY, once they reopen that bridge.",
    "DRUM": "SEAMUS: Hear that? Years back I played this bodhran on the quay at dusk...|"
            "...and something answered from the river. Big as a horse, and shining like the moon.|"
            "A mythical PMON, I'd swear to it. It never came again. But I keep playing.",
    "ALEX0": "ALEX: Well, look who finally got a PMON. $, is it? Cute.|"
             "Mom said to mind you. Let's see if you can mind yourself!",
    "ALEX1": "ALEX: ...Not bad. Don't let it go to your head.",
    "SOUTH": "The road south to HOOK HEAD isn't finished yet.",
    "EAST": "The road east to WEXFORD TOWN isn't finished yet.",
    "WEST": "The bridge to KILKENNY is closed for repairs.",
    "INTRO": "CIARA: Go on, @! Your pack is on the table.|The last card is always a shiny. "
             "I'd give anything to pull a good one!",
    "PACK": "",
    "PACK_AGAIN": "Open another pack? Your partner may change.|Press A to open it, or B to leave it.",
    "CARD": "@ pulled a shiny $ card!",
    "PROF0": "KNOCK KNOCK!|MOM: Professor O'DWYER! Come in, come in.",
    "PROF0B": "PROF: Jeannette! I was passing, and I smelt the kettle on.|MOM: You always do. Sit down, I'll wet the tea.",
    "PROF1": "PROF: And who's this? @! What have you there... a shiny $ card?|"
             "Well now. It so happens I have a real $ with me, and it needs a partner.|"
             "Would you look after it?    A: Yes    B: Not yet",
    "PROF_NO": "PROF: No rush. Open another pack and see what turns up.",
    "PROF2": "$ leapt out of its PBALL!|@ received $ from the PROFESSOR!",
    "PROF3": "PROF: Mind each other, the pair of you. And tell me about every PMON you meet. I'm making a great list.",
    "ITEM1": "@ found a POTION!",
    "ALEX2": "ALEX: Here. Don't waste it.",
    "ALEX3": "ALEX: WEXFORD is north, past ENNISCORTHY. The gym leader won't go easy on you either. Try and keep up!",
    "BLACKOUT2": "@ has no PMON left that can fight! @ was rushed back to the PMON CENTRE...",
    "BADGE": "@ received the FEATHER BADGE!",
    "ORLA3": "ORLA: Seven more gyms, and then the WORLD CUP. Don't stop now.",
    "GATE": "The gate is locked. A brass plate reads: THE LOWEST SONG FIRST.",
    "GATE_OPEN": "All three birds sang together. The gate swung open!",
    "CAGE_NO": "The bird ruffled its feathers and went quiet. Start again.",
    "GOTSODA": "@ got a CREAM SODA!|It raises a PMON by one level. Press START, then UP, to drink it.",
    "SODA": "The CREAM SODA fizzed. Your PMON grew to level #!",
    "NOSODA": "No PMON here to give it to.",
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

def npc(x, y, frame, pal, t0, t1=None, flip=0, wander=0, script=0, hide=0, anim=0, param=0, sight=0, need=0):
    """script: 1 Mom heals, 2 Alex battles, 3 plays the drum. hide: flag bit that removes them."""
    return (x, y, frame, flip, pal, t0, t1 or t0, wander, script, anim, param, sight, hide, need)

FLAG_BEAT_ALEX, FLAG_STASH, FLAG_SLEEPER, FLAG_HURLER, FLAG_GYM1, FLAG_BADGE, FLAG_CALL = 4, 8, 16, 32, 64, 128, 256
FLAG_PROF, FLAG_ITEM1, FLAG_GATE = 1024, 2048, 4096          # the Professor has called; the Route 1 potion is taken
BIT_MAEVE = 9                                   # flag bit set once Maeve has handed over her potions
# wild: (species, lowest level, highest level); edges/conn are in N, S, E, W order
MAPS = [
    # New Ross: the Barrow and the quay down the west side with the Dunbrody, the
    # old town round James's house, and a newer street of painted townhouses to the east.
    dict(name="TOWN", pals="bg_pals", outdoor=1, edges=(None, "SOUTH", "EAST", "WEST"),
         conn=("ROUTE1", None, None, None), wild=[("GIRRIN", 2, 3), ("GIRRIN", 2, 4), ("SPIDGE", 2, 3)], rows=[
        "~~~QTTTT==TTTTTTTTTTTTTT",
        "~~~Q....==.,,,,..TTTTTTT",
        "BBB=======.,,,,........T",
        "~~~QSF..==S.,,,..H++J++T",
        "~12QR+++==.......++++++T",
        "~34Q++++==.R+++..++++++T",
        "~56Q++++==.++++.=======T",
        "~abQ.=..==.++++.=......T",
        "~~~Q====================",
        "~~~Q.F..==..F...=..F...T",
        "~~~QWWW.==.U+++.=.TTTT.T",
        "~~~Q,,,.==.++++.=.T..T.T",
        "~~~Q,,,,==.++++.=.TTTT.T",
        "~~~Q,,,,=========......T",
        "~~~Q,,,,==..F..........T",
        "~~~Q....==....,,,,,....T",
        "~~~QS...==....,,,,,....T",
        "~~~Q....==.....,,,.....T",
        "~~~Q....==.............T",
        "~~~QTTTT==TTTTTTTTTTTTTT"],
        ints=[(10, 3, "TOWN"), (4, 3, "SHIP"), (4, 16, "RIVER"), (18, 5, "TERRACE"), (21, 5, "TERRACE")],
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
        npcs=[npc(8, 3, F_MOM, 4, "MOM0", "MOM1", script=1, param=1), npc(3, 5, F_GIRL, 2, "CIARA0", "CIARA1"),
              npc(6, 5, F_BOY, 3, "OISIN0", "OISIN1"),
              npc(7, 4, F_PROF, 2, "PROF_NO", "PROF3", need=FLAG_PROF, hide=2)],      # the Professor, once he has called in
        warps=[(4, 8, "TOWN", 12, 13)]),
    dict(name="ROUTE1", pals="bg_pals", outdoor=1, edges=(None, None, None, None),
         conn=("ROUTE2", "TOWN", None, None), wild=[("GIRRIN", 3, 5), ("SPIDGE", 3, 5), ("GRANOG", 3, 5)], rows=[
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
        npcs=[npc(8, 8, F_ALEX, 1, "ALEX0", script=2, param=0, hide=FLAG_BEAT_ALEX),
              npc(5, 11, F_ITEM, 5, "ITEM1", script=7, hide=FLAG_ITEM1)],          # a potion lying in a PBall
        warps=[]),
    # Route 2: rain, a trainer with a line of sight, a sleeper on the path (or a detour
    # through long grass), and a stash among the flowers.
    dict(name="ROUTE2", pals="rain_pals", outdoor=1, weather=1, edges=(None, None, None, None),
         conn=(None, "ROUTE1", ("WEXFORD", 1), None), wild=[("GRANOG", 5, 7), ("SPIDGE", 5, 7), ("GIRRIN", 5, 6)], rows=[
        "TTTTTTTTTTTTTTTT",
        "TT,,,,TTTTT,,,TT",
        "T,,,,,..FTT,,,,T",
        "T,,..===========",
        "T....==TTTT..S.T",
        "TTT..==TTTTT...T",
        "T~~~.==..TTTT.TT",
        "T~~~.==.,,,TTTTT",
        "T~~~TT=T,,,,..TT",
        "TT...==..,,,.F.T",
        "TTTT.==........T",
        "TT...==.TTTTTTTT",
        "TT...===.TTTTTTT",
        "TTTTTTT=TTTTTTTT",
        "TTTTTT==TTTTTTTT",
        "TTTTTT==TTTTTTTT"],
        ints=[(13, 4, "ROUTE2"), (13, 9, "STASH", 3, FLAG_STASH)],
        npcs=[npc(7, 11, F_BOY, 2, "HURL0", "HURL1", script=2, param=1, sight=3),
              npc(6, 8, F_SLEEP, 5, "SLEEPER", script=4, param=5, sight=8, hide=FLAG_SLEEPER, anim=2)],
        warps=[]),
    # Wexford: you arrive along the top street past the abbey ruins, the PMon Centre
    # and the Mart. Main Street runs down the east side beside the quay, boardwalk and
    # mussel boats. Between them: Maeve's cottage, the Bullring, and further south the
    # Opera House and the gym with open ground between them.
    dict(name="WEXFORD", pals="wex_pals", outdoor=1, edges=("NORTH2", "SOUTH2", None, None),
         conn=(None, None, None, ("ROUTE2", -1)), wild=[("SPIDGE", 5, 7)], rows=[
        "TTTTTTTTTTTTTTTTTT==TQB~~~",
        "T.xyx.9+++.0+++...==.QB~~~",
        "T.x.xS++++.++++.S.==.QB~78",
        "T.....++++.++++...==.QB~~~",
        "=====================QB~~~",
        "T.................==.QB~~~",
        "T.R+++..QQQQQ..H++==.QB~78",
        "T.++++..QQPQQ..+++==.QB~~~",
        "T.++++..QQQQQ..+++==.QB~~~",
        "T===================.QB~~~",
        "T.................==.QB~78",
        "T.O+++...G+++..J++==.QB~~~",
        "T.++++...++++..+++==.QB~~~",
        "T.++++...++++..+++==.QB~78",
        "T===================.QB~~~",
        "T.................==.QB~~~",
        "T..,,,,,..TTT.....==.QB~78",
        "T..,,,,,..T.T..S..==.QB~~~",
        "T..,,,,,..TTT.....==.QB~~~",
        "T.................==.QB~~~",
        "T.................==.QB~~~",
        "TTTTTTTTTTTTTTTTTT==TQB~~~"],
        ints=[(5, 2, "ABBEY"), (16, 2, "WEXFORD"), (10, 7, "PIKEMAN"), (15, 17, "SLOBS"),
              (16, 8, "TERRACE"), (16, 13, "TERRACE")],
        npcs=[npc(2, 5, F_GIRL, 1, "RUTH", script=1), npc(22, 7, F_OLD, 3, "FISHER")],
        warps=[(7, 3, "CENTRE", 4, 7), (12, 3, "MART", 4, 7), (3, 8, "HOUSEW", 4, 7),
               (3, 13, "OPERA", 4, 7), (4, 13, "OPERA", 4, 7), (10, 13, "GYM", 4, 7)]),
    dict(name="GYM", pals="in_pals", outdoor=0, edges=(None,) * 4, conn=(None,) * 4, wild=[], rows=[
        "^^^^^^^^^^",
        "##########",
        "s________s",
        "jjjjgjjjjj",
        "__________",
        "_A______A_",
        "______A___",
        "__________",
        "____m_____"],
        ints=[(0, 2, "STATUE"), (9, 2, "STATUE")],
        npcs=[npc(4, 2, F_GIRL, 4, "ORLA0", "ORLA2", script=2, param=3),
              npc(4, 5, F_BOY, 1, "GYMT0", "GYMT1", script=2, param=2, sight=2)],
        warps=[(4, 8, "WEXFORD", 10, 14)]),
    dict(name="HOUSEW", pals="in_pals", outdoor=0, edges=(None,) * 4, conn=(None,) * 4, wild=[], rows=[
        "^^^^^^^^^^",
        "#o##o##o##",
        "v______CK_",
        "__________",
        "___rrrr___",
        "___rttr___",
        "___rrrr___",
        "__________",
        "____m_____"],
        ints=[(0, 2, "TV"), (8, 2, "KETTLE"), (7, 2, "KETTLE")],
        npcs=[npc(6, 3, F_MOM, 1, "MAEVE0", "MAEVE1", script=5, param=2, sight=BIT_MAEVE),
              npc(2, 5, F_BOY, 2, "KID")],
        warps=[(4, 8, "WEXFORD", 3, 9)]),
    dict(name="OPERA", pals="in_pals", outdoor=0, edges=(None,) * 4, conn=(None,) * 4, wild=[], rows=[
        "^^^^^^^^^^",
        "#c######c#",
        "crrrrrrrrc",
        "__________",
        "_hh_hh_hh_",
        "__________",
        "_hh_hh_hh_",
        "__________",
        "____m_____"],
        ints=[],
        npcs=[npc(5, 2, F_GIRL, 4, "SINGER", script=3, param=1), npc(2, 6, F_OLD, 3, "HUSH")],
        warps=[(4, 8, "WEXFORD", 3, 14)]),
    # The PMon Centre and the Mart look the same in every town, so one interior serves
    # them all; leaving takes you back to the door you came in by.
    dict(name="CENTRE", pals="in_pals", outdoor=0, edges=(None,) * 4, conn=(None,) * 4, wild=[], rows=[
        "^^^^^^^^^^",
        "#o##o##o##",
        "__________",
        "_CCC_MCC_v",
        "__________",
        "_hh____hh_",
        "__________",
        "__________",
        "____m_____"],
        ints=[(9, 3, "TV")],
        npcs=[npc(4, 3, F_MOM, 1, "NURSE", script=1, param=2)],
        warps=[(4, 8, "BACK", 0, 0)]),
    dict(name="MART", pals="in_pals", outdoor=0, edges=(None,) * 4, conn=(None,) * 4, wild=[], rows=[
        "^^^^^^^^^^",
        "#o######o#",
        "__________",
        "_CCC_CCC__",
        "__________",
        "_kk___kk_k",
        "__________",
        "__________",
        "____m_____"],
        ints=[],
        npcs=[npc(4, 3, F_BOY, 3, "CLERK", script=6)],
        warps=[(4, 8, "BACK", 0, 0)]),
]
# trainers: name, team (species, level), text after winning, PBalls handed over, flag set on a win
TRAINERS = [
    dict(name="ALEX", mons=[("FAOLAN", 6)], win="ALEX1", prize=0x81, flag=FLAG_BEAT_ALEX, cash=120, pic=0, pal=1, song="SONG_RIVAL"),   # 0x80 + n: n Cream Sodas
    dict(name="CONOR", mons=[("GIRRIN", 6)], win="HURL1", flag=FLAG_HURLER, cash=60, pic=1, pal=2),
    dict(name="AOIFE", mons=[("SPIDGE", 7)], win="GYMT1", flag=FLAG_GYM1, cash=80, pic=1, pal=1),
    dict(name="ORLA", mons=[("SPIDGE", 8), ("GANDAL", 10)], win="ORLA1", flag=FLAG_BADGE, cash=300, pic=2, pal=4),
]
TR_ID = {t["name"]: i for i, t in enumerate(TRAINERS)}
MAP_ID = {m["name"]: i for i, m in enumerate(MAPS)}
SP_ID = {sp[0]: i for i, sp in enumerate(SPECIES)}
for m in MAPS:
    POOL = "out" if m["outdoor"] else "in"
    m["w"], m["h"], m["ids"] = compile_map(m["rows"], m["name"], m["outdoor"])
POOL = "out"
sizes = {k: len(t) for k, t in tiles.items()}
assert sizes["out"] <= 160 and sizes["in"] <= 160 and len(metatiles) <= 255, (sizes, len(metatiles))
assert all(n <= EXTRA_MAX for k, n in sizes.items() if k.startswith("x:")), sizes

TEXT_MAX = 420
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
     f"#define TILE_BASE {TILE_BASE}", f"#define N_TILES_OUT {len(tiles['out'])}", f"#define N_TILES_IN {len(tiles['in'])}",
     f"#define N_SPR_TILES {len(spr)}", f"#define SPARK_TILE {SPARK_TILE}", f"#define BFLY_TILE {BFLY_TILE}",
     f"#define F_GRASS_A {F_GRASS_A}", f"#define F_GRASS_B {F_GRASS_B}",
     f"#define F_WHIRL_A {F_WHIRL_A}", f"#define F_WHIRL_B {F_WHIRL_B}", f"#define F_BALL {F_BALL}",
     f"#define F_POTION {F_POTION}", f"#define F_ALEX {F_ALEX}", f"#define F_ALEX_U {F_ALEX_U}", f"#define F_TURN {F_TURN}", f"#define F_GIRL {F_GIRL}", f"#define F_OLD {F_OLD}",
     f"#define F_WAVE {F_WAVE}", f"#define F_FLAME {F_FLAME}", f"#define F_LEAF {F_LEAF}", f"#define F_DOT {F_DOT}", f"#define PIC_ME {PIC_ME}", "#define PIC_BANK 6",
     "extern const uint8_t trainer_pics[][784], badge_art[]; extern const palette_color_t badge_pal[], pic_pals[][4];", f"#define F_PROF {F_PROF}", f"#define F_PROF_U {F_PROF_U}", f"#define F_PROF_L {F_PROF_L}", f"#define F_SODA {F_SODA}", f"#define N_SPR2_TILES {len(spr2)}", "extern const uint8_t spr2_tiles[];", f"#define WATER_TILE {WATER_TILE}",
     f"#define F_SOLID {SOLID}", f"#define F_DOOR {DOOR}", f"#define F_GRASS {GRASS}",
     f"#define P_UI {P_UI}", "#define NO_TEXT 255"]
h += [f"#define K_{k} {v}" for k, v in dict(DARK=K_DARK, CARD=K_CARD, FOIL=K_FOIL, SHINY=K_SHINY).items()]
h += [f"#define FR_{k} {v}" for k, v in FR.items()] + [f"#define PK_{k} {v}" for k, v in PK.items()]
h += [f"#define TXT_{k} {i}" for k, i in TXT.items()] + [f"#define MAP_{k} {i}" for k, i in MAP_ID.items()]
h += ["typedef struct { uint8_t x, y, text, give; uint16_t flag; } interact_t;",
      "typedef struct { uint8_t x, y, frame, flip, pal, text0, text1, wander, script, anim, param, sight; uint16_t hide, need; } npc_t;",
      "typedef struct { char name[8]; uint8_t n, mons[3][2], text_win, prize, pic, pal, song; uint16_t flag, cash; } trainer_t;",
      "extern const trainer_t trainers[];",
      "typedef struct { uint8_t species, lo, hi; } wild_t;", f"#define FLAG_BEAT_ALEX {FLAG_BEAT_ALEX}", f"#define FLAG_PROF {FLAG_PROF}", f"#define FLAG_GATE {FLAG_GATE}", f"#define MT_CAGE {mt_char['A']}", f"#define MT_GATE {mt_char['g']}", f"#define MT_FLOOR {mt_char['_']}", f"#define FLAG_BADGE {FLAG_BADGE}", f"#define FLAG_CALL {FLAG_CALL}",
      "typedef struct { uint8_t x, y, map, tx, ty; } warp_t;",
      "typedef struct { uint8_t w, h, outdoor, tileset, weather; const palette_color_t *pals;",
      "  uint8_t n_int; const interact_t *ints; uint8_t n_npc; const npc_t *npcs;",
      "  uint8_t n_warp; const warp_t *warps; uint8_t edge[4], conn[4]; int8_t coff[4]; uint8_t n_wild; const wild_t *wild; } map_t;",
      "typedef struct { const char *name; const char *type; uint8_t pal; } card_t;",
      "extern const uint8_t bg_tiles_out[], bg_tiles_in[], spr_tiles[], water_anim[2][16];",
      "extern const uint8_t * const extra_tiles[]; extern const uint8_t extra_n[];",
      "#define DATA_BANK 3", "extern const uint8_t * const map_ptr[];", "#define MAP_MAX 1024", f"#define TEXT_MAX {TEXT_MAX}",
      "extern const uint8_t icon_art[3][256], bar_tiles[], type_chart[17][17];",
      "#define ART_BANK 2", "#define EXTRA_BANK 6", "extern const uint8_t species_art[][1024];",
      "typedef struct { char name[8]; uint8_t type, hp, atk, def, spd, spc, yield, rate, back, gesture; uint8_t learn[4][2]; } species_t;",
      "#define BACK_BANK 3", "#define NO_BACK 255", "extern const uint8_t species_back[][1024];", f"#define BALL_TILE {BALL_TILE}", f"#define BANG_TILE {BANG_TILE}", f"#define RAIN_TILE {RAIN_TILE}",
      "typedef struct { char name[8]; uint8_t type, power, acc, effect; } move_t;",
      "extern const species_t species[]; extern const move_t moves[]; extern const palette_color_t art_pals[][4], art_pals2[][4];",
      "extern const uint8_t art_mask[][8], back_mask[][8];",
      "extern const char * const type_names[]; extern const uint8_t type_special[];",
      "extern const card_t starter_cards[3], icon_cards[3];",
      "extern const palette_color_t bg_pals[], rain_pals[], wex_pals[], in_pals[], pack_pals[], obj_pals[];",
      "extern const uint8_t mt_tiles[][4], mt_attr[][4], mt_flags[], mt_sway[];",
      "extern const map_t maps[];", "extern const char * const texts[];",
      "#endif"]
c = ['#include "assets.h"', '#include "music_data.h"', pals("badge_pal", [BADGE_PAL]), "const palette_color_t pic_pals[][4] = {" + ",".join("{" + ",".join(str(rgb(c)) for c in p) + "}" for p in PIC_PALS) + "};",
     "const uint8_t water_anim[2][16] = {{" + ",".join(map(str, to2bpp(water[0:8, 0:8]))) +
     "},{" + ",".join(map(str, to2bpp(water_b))) + "}};",
     "const card_t starter_cards[3] = {" + ",".join('{"%s","%s",%d}' % (s[0], s[1], s[3]) for s in STARTERS) + "};",
     "const card_t icon_cards[3] = {" + ",".join('{"%s","ENERGY",%d}' % (s[0], s[2]) for s in ICONS) + "};",
     pals("bg_pals", BG_PALS), pals("rain_pals", RAIN_PALS), pals("wex_pals", WEX_PALS), pals("in_pals", IN_PALS), pals("pack_pals", PACK_PALS), pals("obj_pals", OBJ_PALS),
     "const uint8_t mt_tiles[][4] = {\n" + ",\n".join("  {%d,%d,%d,%d}" % tuple(m[0]) for m in metatiles) + "\n};",
     "const uint8_t mt_attr[][4] = {\n" + ",\n".join("  {%d,%d,%d,%d}" % tuple(m[1]) for m in metatiles) + "\n};",
     "const uint8_t mt_flags[] = {" + ",".join(str(m[2]) for m in metatiles) + "};",
     "const uint8_t mt_sway[] = {" + ",".join(str(sway_of.get(i, i)) for i in range(len(metatiles))) + "};"]
for i, m in enumerate(MAPS):
    ints = [(i_[0], i_[1], TXT[i_[2]]) + (tuple(i_[3:]) if len(i_) > 3 else (0, 0)) for i_ in m["ints"]]
    npcs = [n[:5] + (TXT[n[5]], TXT[n[6]]) + n[7:] for n in m["npcs"]]
    wild = [(SP_ID[sp], lo, hi) for sp, lo, hi in m["wild"]]
    warps = [(x, y, 255 if t == "BACK" else MAP_ID[t], tx, ty) for x, y, t, tx, ty in m["warps"]]
    c += [f"static const interact_t m{i}_int[] = {{" + rows_of("{%d,%d,%d,%d,%d}", ints) + "};",
          f"static const npc_t m{i}_npc[] = {{" + rows_of("{%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d}", npcs) + "};",
          f"static const wild_t m{i}_wild[] = {{" + rows_of("{%d,%d,%d}", wild) + "};",
          f"static const warp_t m{i}_warp[] = {{" + rows_of("{%d,%d,%d,%d,%d}", warps) + "};"]
    m["c"] = "{%d,%d,%d,%d,%d,%s,%d,m%d_int,%d,m%d_npc,%d,m%d_warp,{%s},{%s},{%s},%d,m%d_wild}" % (
        m["w"], m["h"], m["outdoor"], 0 if m["outdoor"] else 1, m.get("weather", 0), m["pals"], len(ints), i, len(npcs), i, len(warps), i,
        ",".join(str(TXT[e]) if e else "255" for e in m["edges"]),
        ",".join(str(MAP_ID[e[0] if isinstance(e, tuple) else e]) if e else "255" for e in m["conn"]),
        ",".join(str(e[1]) if isinstance(e, tuple) else "0" for e in m["conn"]), len(wild), i)
c += [*["extern const uint8_t map_cells%d[];" % i for i in range(len(MAPS))],
      "const uint8_t * const map_ptr[] = {" + ",".join("map_cells%d" % i for i in range(len(MAPS))) + "};",
      *["extern const uint8_t bg_tiles_x%d[];" % i for i, m in enumerate(MAPS) if "x:" + m["name"] in tiles],
      "const uint8_t * const extra_tiles[] = {" + ",".join(
          ("bg_tiles_x%d" % i) if "x:" + m["name"] in tiles else "0" for i, m in enumerate(MAPS)) + "};",
      "const uint8_t extra_n[] = {" + ",".join(str(len(tiles.get("x:" + m["name"], []))) for m in MAPS) + "};",
      "const map_t maps[] = {\n  " + ",\n  ".join(m["c"] for m in MAPS) + "\n};",
      "const trainer_t trainers[] = {\n" + ",\n".join(
          '  {"%s",%d,{%s},%d,%d,%d,%d,%s,%d,%d}' % (t["name"], len(t["mons"]),
              ",".join("{%d,%d}" % (SP_ID[a], l) for a, l in t["mons"] + [("BOVEEN", 0)] * (3 - len(t["mons"]))),
              TXT[t["win"]], t.get("prize", 0), t["pic"], t["pal"], t.get("song", "SONG_BATTLE"), t["flag"], t["cash"]) for t in TRAINERS) + "\n};"]
WRAPPED = [wrap(t) for t in TEXTS.values()]
assert max(len(w.replace("\\", "")) for w in WRAPPED) < TEXT_MAX, max(len(w) for w in WRAPPED)
def eff(a, dname):
    strong, weak, none = (set(x.split()) for x in CHART[a])
    return 20 if dname in strong else 5 if dname in weak else 0 if dname in none else 10
c += ["const uint8_t type_chart[17][17] = {\n" + ",\n".join(
          "  {" + ",".join(str(eff(a, dn)) for dn in TYPES) + "}" for a in TYPES) + "\n};",
      "const char * const type_names[] = {" + ",".join('"%s"' % t for t in TYPES) + "};",
      "const uint8_t type_special[] = {" + ",".join("1" if t in SPECIAL else "0" for t in TYPES) + "};",
      "const move_t moves[] = {" + ",".join('{"%s",%d,%d,%d,%d}' % (m[0], TYPES.index(m[1]), m[2], m[3], m[4]) for m in MOVES) + "};",
      "const palette_color_t art_pals[][4] = {" + ",".join("{" + ",".join(str(rgb(x)) for x in sp[3]) + "}" for sp in SPECIES) + "};",
      "const palette_color_t art_pals2[][4] = {" + ",".join("{" + ",".join(str(rgb(x)) for x in
          (sp[3][0], ACCENT.get(sp[0], sp[3][1]), sp[3][1], sp[3][3])) + "}" for sp in SPECIES) + "};",
      "const uint8_t art_mask[][8] = {" + ",".join("{" + ",".join(map(str, encode_art(sp[2])[1])) + "}" for sp in SPECIES) + "};",
      "const uint8_t back_mask[][8] = {" + ",".join("{" + ",".join(map(str, encode_art(b)[1])) + "}" for b in BACKS.values()) + "};"]
def learn(ls):
    ls = [(l, MOVE_ID[m]) for l, m in ls] + [(0, 0)] * (4 - len(ls))
    return "{" + ",".join("{%d,%d}" % x for x in ls) + "}"
c.append("const species_t species[] = {\n" + ",\n".join(
    '  {"%s",%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%s}' % ((sp[0], TYPES.index(sp[1])) + sp[4] + (sp[5], sp[6],
        list(BACKS).index(sp[0]) if sp[0] in BACKS else 255, GESTURE[sp[0]], learn(sp[7])))
    for sp in SPECIES) + "\n};")
h.insert(-1, f"#define N_SPECIES {len(SPECIES)}")
h[-1:-1] = [f"#define T_{t} {i}" for i, t in enumerate(TYPES)] + [f"#define SP_{sp[0]} {i}" for i, sp in enumerate(SPECIES)]
open(f"{OUT}/art.c", "w").write("\n".join([
    "// Graphics live in ROM bank 2; only bank 0 routines may read them.",
    "#pragma bank 2", '#include "assets.h"',
    "const uint8_t species_art[][1024] = {\n" + ",\n".join("{\n" + carr(encode_art(sp[2])[0]) + "\n}" for sp in SPECIES) + "\n};",
    "const uint8_t bg_tiles_out[] = {\n" + carr(v for t in tiles["out"] for v in to2bpp(t)) + "\n};",
    "const uint8_t bg_tiles_in[] = {\n" + carr(v for t in tiles["in"] for v in to2bpp(t)) + "\n};",
    "const uint8_t spr_tiles[] = {\n" + carr(v for t in spr for v in to2bpp(t)) + "\n};",
    "const uint8_t spr2_tiles[] = {\n" + carr(v for t in spr2 for v in to2bpp(t)) + "\n};",
    "const uint8_t icon_art[3][256] = {\n" + ",\n".join("{\n" + carr(tiles2bpp(s[1])) + "\n}" for s in ICONS) + "\n};",
    "const uint8_t bar_tiles[] = {\n" + carr(v for t in bar_tiles for v in to2bpp(t)) + "\n};"]) + "\n")
open(f"{OUT}/art_back.c", "w").write("// ROM bank 3: back views, map layouts and all dialogue.\n#pragma bank 3\n#include \"assets.h\"\n"
    "const uint8_t species_back[][1024] = {\n" + ",\n".join("{\n" + carr(encode_art(b)[0]) + "\n}" for b in BACKS.values()) + "\n};\n"
    + "".join("const uint8_t map_cells%d[] = {\n" % i + carr(m["ids"]) + "\n};\n" for i, m in enumerate(MAPS)) +
    "const char * const texts[] = {\n" + ",\n".join('  "%s"' % w for w in WRAPPED) + "\n};\n")
open(f"{OUT}/art_x.c", "w").write("// ROM bank 6: each town's landmark and townhouse tiles.\n#pragma bank 6\n#include \"assets.h\"\n"
    + "const uint8_t trainer_pics[][784] = {\n" + ",\n".join("{\n" + carr(tiles2bpp(p)) + "\n}" for p in PICS) + "\n};\n"
    + "const uint8_t badge_art[] = {\n" + carr(tiles2bpp(BADGE)) + "\n};\n" + "\n".join(
    "const uint8_t bg_tiles_x%d[] = {\n" % i + carr(v for t in tiles["x:" + m["name"]] for v in to2bpp(t)) + "\n};"
    for i, m in enumerate(MAPS) if "x:" + m["name"] in tiles) + "\n")
open(f"{OUT}/assets.h", "w").write("\n".join(h) + "\n")
open(f"{OUT}/assets.c", "w").write("\n".join(c) + "\n")

# preview sheet of the card art, for eyeballing
if len(sys.argv) > 2:
    sheet = Image.new("RGB", (64 * len(SPECIES), 128), "white")
    full = lambda sp: sp[3] + ["#000000", ACCENT.get(sp[0], sp[3][1])]
    cells = [(encode_art(sp[2])[2], full(sp), i, 0) for i, sp in enumerate(SPECIES)] + \
            [(encode_art(BACKS[sp[0]])[2], full(sp), i, 1) for i, sp in enumerate(SPECIES) if sp[0] in BACKS]
    for px, pal, i, row in cells:
        cols = [tuple(int(pal[v][j:j + 2], 16) for j in (1, 3, 5)) for v in range(6)]
        im = Image.fromarray(np.array(cols, np.uint8)[px])
        sheet.paste(im, (i * 64, row * 64))
    sheet.resize((64 * len(SPECIES) * 4, 512), 0).save(sys.argv[2])
print("landmark tiles:", {k[2:]: n for k, n in sizes.items() if k.startswith("x:")})
print(f"{len(tiles['out'])} outdoor + {len(tiles['in'])} indoor bg tiles, {len(metatiles)} metatiles, {len(spr)} sprite tiles")

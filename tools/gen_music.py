#!/usr/bin/env python3
"""Generates src/gen/music_data.c/.h: note table and songs for the sound driver.

Songs are written as text. Each token is NOTE[*LENGTH]; length is in song units
(default 1). '-' is a rest. Octave follows the note letter: d5, f#4. Three
tracks per song: lead (pulse), bass (wave), drums (noise: h = hat, k = kick).
"""
import sys
OUT = sys.argv[1] if len(sys.argv) > 1 else "src/gen"
NAMES = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}

def note(tok):
    if tok == "-": return 0
    if tok == "h": return 1
    if tok == "k": return 2
    if tok == "s": return 3
    n = NAMES[tok[0]]; rest = tok[1:]
    if rest[0] == "#": n += 1; rest = rest[1:]
    v = 12 * (int(rest) - 2) + n + 1          # 1 = C2
    assert 1 <= v <= 72, tok
    return v

def track(text):
    out, total, loop = [], 0, 0
    for tok in text.split():
        if tok == "|": continue
        if tok == "!": loop = len(out); continue
        name, _, ln = tok.partition("*")
        ln = int(ln) if ln else 1
        out += [note(name), ln]; total += ln
    return out + [255, 0], total, loop

# An original jig in D for New Ross: 6/8, one unit = an eighth note.
TOWN = dict(speed=11, lead_env=0xA2, lead="""
 d4 f#4 a4 d5 a4 f#4 | g4 b4 d5 e5 d5 b4 | a4 f#4 d4 f#4 a4 d5 | e5 c#5 a4 e5*2 - |
 f#5 e5 d5 b4 d5 b4 | a4 f#4 a4 d5*2 e5 | f#5 d5 f#5 e5 c#5 a4 | d5*3 d5*2 - |
 d4 f#4 a4 d5 a4 f#4 | g4 b4 d5 e5 d5 b4 | a4 f#4 d4 f#4 a4 d5 | e5 c#5 a4 e5*2 - |
 f#5 e5 d5 b4 d5 b4 | a4 f#4 a4 d5*2 e5 | f#5 d5 f#5 e5 c#5 a4 | d5*3 d5*2 - |
 f#5 a5 f#5 d5 f#5 a5 | g5 b5 g5 e5 g5 b5 | a5 f#5 d5 f#5 e5 d5 | e5 c#5 a4 a4*2 - |
 b4 d5 g5 f#5 d5 a4 | g4 b4 d5 e5*2 f#5 | g5 e5 c#5 d5 b4 a4 | d5*3 d5*2 - |
 f#5 a5 f#5 d5 f#5 a5 | g5 b5 g5 e5 g5 b5 | a5 f#5 d5 f#5 e5 d5 | e5 c#5 a4 a4*2 - |
 b4 d5 g5 f#5 d5 a4 | g4 b4 d5 e5*2 f#5 | g5 e5 c#5 d5 b4 a4 | d5*3 d5*2 - |
""", bass="""
 d3*2 a3 d3*2 a3 | g3*2 d4 g3*2 d4 | d3*2 a3 d3*2 a3 | a3*2 e4 a3*2 e4 |
 d3*2 a3 g3*2 d4 | d3*2 a3 d3*2 a3 | d3*2 a3 a3*2 e4 | d3*2 a3 d3*3 |
 d3*2 a3 d3*2 a3 | g3*2 d4 g3*2 d4 | d3*2 a3 d3*2 a3 | a3*2 e4 a3*2 e4 |
 d3*2 a3 g3*2 d4 | d3*2 a3 d3*2 a3 | d3*2 a3 a3*2 e4 | d3*2 a3 d3*3 |
 d3*2 a3 d3*2 a3 | g3*2 d4 e3*2 b3 | d3*2 a3 d3*2 a3 | a3*2 e4 a3*2 e4 |
 g3*2 d4 d3*2 a3 | g3*2 d4 a3*2 e4 | a3*2 e4 a3*2 e4 | d3*2 a3 d3*3 |
 d3*2 a3 d3*2 a3 | g3*2 d4 e3*2 b3 | d3*2 a3 d3*2 a3 | a3*2 e4 a3*2 e4 |
 g3*2 d4 d3*2 a3 | g3*2 d4 a3*2 e4 | a3*2 e4 a3*2 e4 | d3*2 a3 d3*3 |
""", drums="-*6 " * 32)

# A slow air in G for the house and the title: 3/4, one unit = a quarter note.
HOME = dict(speed=28, lead_env=0x84, lead="""
 b4 d5 g5 | f#5*2 d5 | e5 g5 e5 | d5*3 | c5 e5 a5 | g5*2 e5 | d5 b4 a4 | g4*3 |
 b4 d5 g5 | a5*2 f#5 | g5 e5 c5 | d5*3 | e5 g5 f#5 | e5*2 c5 | b4 a4 f#4 | g4*3 |
""", bass="""
 g3 b3 d4 | d3 f#3 a3 | c3 e3 g3 | g3 b3 d4 | a3 c4 e4 | c3 e3 g3 | d3 f#3 a3 | g3 b3 d4 |
 g3 b3 d4 | d3 f#3 a3 | c3 e3 g3 | g3 b3 d4 | c3 e3 g3 | a3 c4 e4 | d3 f#3 a3 | g3 d4 g4 |
""", drums="-*3 " * 16)

# The battle theme, in A minor: a two-bar run-up, then a driving loop over a
# pumping octave bass with kick, snare and hat. One unit = a sixteenth note.
# "!" marks where the tune loops back to (so the run-up plays only once).
BAR = "k - h - s - h - k k h - s - h h "
BATTLE = dict(speed=6, lead_env=0xB2, lead="""
 a4 c5 e5 a5 b4 d5 f5 b5 c5 e5 g5 c6 d5 f5 a5 d6 | e5 g#5 b5 e6 e5 g#5 b5 e6 e6*2 e6*2 e6*4 |
 ! a5*2 e5*2 a5*2 c6*2 b5*2 a5*2 g5*2 e5*2 | f5*2 c5*2 f5*2 a5*2 g5*2 f5*2 e5*2 c5*2 |
 g5*2 d5*2 g5*2 b5*2 a5*2 g5*2 f5*2 d5*2 | e5*2 g#5*2 b5*2 e6*2 d6*2 b5*2 g#5*2 e5*2 |
 a5 c6 a5 e5 a5 c6 a5 e5 c6*2 b5*2 a5*4 | d5 f5 a5 d6 a5 f5 d5 f5 a5*2 g5*2 f5*4 |
 e5 g#5 b5 e6 b5 g#5 e5 g#5 b5*2 d6*2 e6*4 | e6*2 d6*2 c6*2 b5*2 a5*2 g#5*2 a5*4 |
""", bass="""
 e2*4 e2*4 e2*4 e2*4 | e2*2 e2*2 e2*2 e2*2 e2*8 |
 ! a2*2 a3*2 a2*2 a3*2 a2*2 a3*2 a2*2 a3*2 | f2*2 f3*2 f2*2 f3*2 f2*2 f3*2 f2*2 f3*2 |
 g2*2 g3*2 g2*2 g3*2 g2*2 g3*2 g2*2 g3*2 | e2*2 e3*2 e2*2 e3*2 e2*2 e3*2 e2*2 e3*2 |
 a2*2 a3*2 a2*2 a3*2 a2*2 a3*2 a2*2 a3*2 | d3*2 d4*2 d3*2 d4*2 d3*2 d4*2 d3*2 d4*2 |
 e2*2 e3*2 e2*2 e3*2 e2*2 e3*2 e2*2 e3*2 | e2*2 e3*2 e2*2 e3*2 a2*2 a3*2 a2*4 |
""", drums="h - h - h - h - h - h - h - h - | s - s - s s s s k*2 k*2 s*4 | ! " + BAR * 8)

SONGS = {"TOWN": TOWN, "HOME": HOME, "BATTLE": BATTLE}
h = ["#ifndef MUSIC_DATA_H", "#define MUSIC_DATA_H", "#include <gb/gb.h>", "#define MUSIC_BANK 4",
     "typedef struct { uint8_t speed, lead_env; const uint8_t *track[3]; uint16_t loop[3]; } song_t;",
     "extern const uint16_t note_freq[], note_freq_b[];", "extern const song_t songs[];"]
freqs = [0] + [round(2048 - 131072 / (65.406 * 2 ** (i / 12))) for i in range(72)]
table = "{" + ",".join(map(str, freqs)) + "};"
# Songs live in ROM bank 4. The driver switches that bank in from its interrupt, so
# it needs its own copy of the pitch table there; sound effects use the fixed copy.
c = ["#pragma bank 4", '#include "music_data.h"', "const uint16_t note_freq_b[] = " + table]
rows = []
for i, (name, s) in enumerate(SONGS.items()):
    lens, loops = [], []
    for part in ("lead", "bass", "drums"):
        data, total, loop = track(s[part]); lens.append(total); loops.append(loop)
        c.append(f"static const uint8_t s{i}_{part}[] = {{" + ",".join(map(str, data)) + "};")
    assert len(set(lens)) == 1, (name, lens)       # all tracks must loop together
    rows.append(f"{{{s['speed']},{s['lead_env']},{{s{i}_lead,s{i}_bass,s{i}_drums}},{{{loops[0]},{loops[1]},{loops[2]}}}}}")
    h.append(f"#define SONG_{name} {i}")
c.append("const song_t songs[] = {" + ",".join(rows) + "};")
h.append("#endif")
open(f"{OUT}/music_data.h", "w").write("\n".join(h) + "\n")
open(f"{OUT}/music_data.c", "w").write("\n".join(c) + "\n")
open(f"{OUT}/music_freq.c", "w").write('#include "music_data.h"\nconst uint16_t note_freq[] = ' + table + "\n")
print("songs:", ", ".join(SONGS))

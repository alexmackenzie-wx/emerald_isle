#!/usr/bin/env python3
"""Headless test: swapping PMONs mid-battle, shared experience and the level-up panel."""
import re, sys
from pyboy import PyBoy
from PIL import Image

rom, out = sys.argv[1], sys.argv[2]
SYM = {k: int(v, 16) for k, v in re.findall(r"DEF (\S+) 0x([0-9A-F]+)", open(rom.replace(".gbc", ".noi")).read())}
pb = PyBoy(rom, window="null", cgb=True)
shots = []
def shot(name):
    im = pb.screen.image.convert("RGB").resize((320, 288), 0)
    im.save(f"{out}/{name}.png"); shots.append(im)
def tap(btn, wait=20):
    pb.button_press(btn); pb.tick(6); pb.button_release(btn); pb.tick(wait)
def pos():
    return pb.memory[SYM["_cur_id"]], pb.memory[SYM["_px"]], pb.memory[SYM["_py"]]
def talking():
    return bool(pb.memory[0xFF40] & 0x20)
def finish_talk():
    quiet = 0
    while quiet < 90:
        if talking(): tap("a", 12); quiet = 0
        else: pb.tick(1); quiet += 1
def walk(btn, tiles):
    for _ in range(tiles):
        before = pos()
        pb.button_press(btn); pb.tick(8); pb.button_release(btn); pb.tick(12)
        if talking(): finish_talk()                 # a battle or a message interrupted the walk
        elif pos() == before: print("  blocked going", btn, "at", before)
def flags():
    return pb.memory[SYM["_flags"]] | (pb.memory[SYM["_flags"] + 1] << 8)
def go(btn, target):
    """Walk until x (left/right) or y (up/down) reaches target, riding out any battles or messages."""
    axis = 1 if btn in ("left", "right") else 2
    stuck = 0
    start_map = pos()[0]
    while pos()[axis] != target and pos()[0] == start_map and stuck < 4:
        before = pos()
        pb.button_press(btn); pb.tick(8); pb.button_release(btn); pb.tick(12)
        if talking(): finish_talk(); stuck = 0
        elif pos() == before: stuck += 1
    if stuck >= 4: print("  stuck going", btn, "at", pos())

pb.tick(150); tap("start", 40); tap("start", 60); pb.tick(60); finish_talk()
tap("a", 60); tap("a", 80); tap("a", 60); tap("a", 60); tap("a", 30); pb.tick(150); tap("a", 30); finish_talk()
go("right", 8); go("up", 4); tap("up", 10); tap("a", 30); finish_talk()            # Mom
P = SYM["_party"]
pb.memory[P + 6] = 200                                                               # 16 XP short of level 6
Q = P + 14                                                                           # a second PMON: a level 3 Girrin, 2 XP short of level 4
for k, v in enumerate([3, 3, 14, 0, 14, 0, 62, 0, 0, 0, 1, 0, 0, 0]): pb.memory[Q + k] = v
pb.memory[SYM["_party_n"]] = 2
go("down", 7); go("left", 4); go("down", 99); pb.tick(40)
pb.button_press("left"); pb.tick(16 * 5 + 6); pb.button_release("left"); pb.tick(10)
n = 0
while pb.screen.image.convert("RGB").getpixel((2, 2)) != (248, 248, 248) and n < 300:
    pb.button_press("left" if n % 2 else "right"); pb.tick(17); pb.button_release("left" if n % 2 else "right"); pb.tick(4); n += 1
pb.tick(300); tap("a", 60); tap("a", 60); pb.tick(260)
frames = []
def film(): frames.append(pb.screen.image.convert("RGB").copy())
film()
tap("down", 10); film(); tap("a", 20); film()                                       # PMON menu
tap("right", 10); tap("a", 60); film(); tap("a", 60); pb.tick(240); film()          # swap to the Girrin
tap("a", 60); tap("a", 60); pb.tick(120)                                            # the foe's free hit
tap("down", 10); tap("a", 20); tap("a", 60); tap("a", 60); pb.tick(240)             # swap back
tap("a", 60); tap("a", 60); pb.tick(120)
for i in range(40):                                                                  # then fight it out
    tap("a", 45); film()
    if pb.screen.image.convert("RGB").getpixel((2, 2)) != (248, 248, 248): break
for who, base in (("first", P), ("second", Q)):
    print(who, "level", pb.memory[base + 1], "exp", pb.memory[base + 6] | (pb.memory[base + 7] << 8), "hp", pb.memory[base + 2])
film_im = Image.new("RGB", (165 * 10, 149 * ((len(frames) + 9) // 10)), "white")
for i, im in enumerate(frames):
    film_im.paste(im, ((i % 10) * 165, (i // 10) * 149))
film_im.save(f"{out}/xp.png")
pb.stop()

#!/usr/bin/env python3
"""Headless test: plays the opening, walks into long grass, people turning to face you, the Centre's healing machine, and waking up there after a defeat."""
import sys
from pyboy import PyBoy
from PIL import Image

rom, out = sys.argv[1], sys.argv[2]
pb = PyBoy(rom, window="null", cgb=True)
shots = []
def shot(name):
    im = pb.screen.image.convert("RGB").resize((320, 288), 0)
    im.save(f"{out}/{name}.png"); shots.append(im)
def tap(btn, wait=20):
    pb.button_press(btn); pb.tick(6); pb.button_release(btn); pb.tick(wait)
def hold(btn, frames):
    pb.button_press(btn); pb.tick(frames); pb.button_release(btn); pb.tick(2)
def in_battle():
    return pb.screen.image.convert("RGB").getpixel((2, 2)) == (248, 248, 248)

def talking():
    return bool(pb.memory[0xFF40] & 0x20) and pb.memory[0xFF4B] == 7          # the dialog window is showing
def finish_talk():
    quiet = 0
    while quiet < 70:                              # several messages can follow one another
        if talking(): tap("a", 12); quiet = 0
        else: pb.tick(1); quiet += 1

pb.tick(150); tap("start", 40); tap("start", 60); pb.tick(60)
finish_talk()                                      # Ciara's intro
tap("a", 60); tap("a", 80); tap("a", 60); tap("a", 60); tap("a", 30); pb.tick(150)   # open the pack
# the Professor's visit: keep pressing A until the PMON is handed over and he has finished talking
import re as _re
_S = {k: int(v, 16) for k, v in _re.findall(r"DEF (\S+) 0x([0-9A-F]+)", open(rom.replace(".gbc", ".noi")).read())}
while not pb.memory[_S["_party_n"]]: tap("a", 12)
for _ in range(2):
    for _ in range(600):
        if pb.memory[0xFF40] & 0x20 and pb.memory[0xFF4B] == 7: break
        pb.tick(1)
    finish_talk()
P = _S["_party"]
def pos(): return pb.memory[_S["_cur_id"]], pb.memory[_S["_px"]], pb.memory[_S["_py"]]
def go(btn, target):
    for _ in range(40):
        c = pos()
        if (c[1] if btn in ("left", "right") else c[2]) == target: return
        pb.button_press(btn); pb.tick(8); pb.button_release(btn); pb.tick(12)
        if pos() == c: print("stuck", btn, c); return
def jump(n):                                  # explore mode's map hop, then explore mode off again
    tap("start", 60); tap("select", 20)
    for k in range(n):
        tap("right", 60)
        if k != n - 1: tap("start", 60)
    tap("start", 60); tap("select", 20); tap("b", 60)
go("left", 3); tap("left", 10); tap("a", 30); shot("c0_ciara_turns"); finish_talk()      # Ciara turns to face you
jump(3); print("jumped to", pos())
go("right", 7); go("up", 99); pb.tick(60); print("in the Centre:", pos())
pb.memory[P + 2] = 3
go("up", 4); tap("up", 10); tap("a", 30)
for i in range(8):
    if talking(): tap("a", 12)
    pb.tick(25); shot("c1_machine%d" % i)
finish_talk(); print("healed hp", pb.memory[P + 2])
go("down", 99); pb.tick(60); print("outside:", pos())
jump(14); print("jumped to", pos())             # fifteen maps now: fourteen hops from Wexford wrap round to Route 2
assert pos()[0] == 3, "not on Route 2"
pb.memory[P + 1] = 1; pb.memory[P + 2] = 1
steps = 0
go("up", 3); go("left", 2)
while not in_battle() and steps < 300:
    pb.button_press("right" if steps % 2 else "left"); pb.tick(8); pb.button_release("right" if steps % 2 else "left"); pb.tick(12); steps += 1     # one tile at a time, staying in the grass
print("battle", in_battle())
n = 0
while pos()[0] != 8 and n < 80: tap("a", 40); n += 1
pb.tick(60); shot("c2_respawn"); print("after losing:", pos(), "hp", pb.memory[P + 2]); finish_talk()
assert pos()[0] == 8, "did not wake up in the PMon Centre"
go("down", 99); pb.tick(60); print("out the door:", pos()); shot("c3_outside")
pb.stop()
sheet = Image.new("RGB", (330 * 6, 298 * 2), "white")
for i, im in enumerate(shots): sheet.paste(im, ((i % 6) * 330, (i // 6) * 298))
sheet.save(f"{out}/centre.png")

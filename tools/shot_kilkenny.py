#!/usr/bin/env python3
"""Headless test: New Ross's lab and tree ring, the bridge west (shut, then open after the
showdown), and the wet wood on the road to Kilkenny. Explore mode."""
import sys, re
from pyboy import PyBoy
from PIL import Image

rom, out = sys.argv[1], sys.argv[2]
pb = PyBoy(rom, window="null", cgb=True)
SYM = {k: int(v, 16) for k, v in re.findall(r"DEF (\S+) 0x([0-9A-F]+)", open(rom.replace(".gbc", ".noi")).read())}
shots = []
def shot(name=""):
    shots.append(pb.screen.image.convert("RGB").resize((320, 288), 0))
def tap(btn, wait=20):
    pb.button_press(btn); pb.tick(6); pb.button_release(btn); pb.tick(wait)
def pos(): return pb.memory[SYM["_cur_id"]], pb.memory[SYM["_px"]], pb.memory[SYM["_py"]]
def talking(): return bool(pb.memory[0xFF40] & 0x20) and pb.memory[0xFF4B] == 7
def finish_talk():
    quiet = 0
    while quiet < 70:
        if talking(): tap("a", 12); quiet = 0
        else: pb.tick(1); quiet += 1
def go(btn, target):
    for _ in range(60):
        c = pos()
        if c[0] != start_map[0]: return
        if (c[1] if btn in ("left", "right") else c[2]) == target: return
        pb.button_press(btn); pb.tick(8); pb.button_release(btn); pb.tick(12)
        if pos() == c: print("  stuck going", btn, "at", c); return
start_map = [0]

pb.tick(200); tap("select", 120)
go("right", 16); go("down", 17); go("right", 18); pb.tick(10); shot("lab outside")
go("up", 10); pb.tick(60); print("in the lab:", pos()); assert pos()[0] == 13
start_map[0] = 13; shot("lab")
go("up", 4); tap("a", 60); shot("prof"); finish_talk()
go("down", 7); go("left", 2); go("up", 5); tap("a", 60); shot("machine"); finish_talk()      # (1,4) is the machine: face it from below
go("down", 7); go("right", 4); go("down", 9); pb.tick(60); print("outside:", pos()); assert pos()[0] == 0
start_map[0] = 0
go("right", 20); go("up", 13); pb.tick(10); shot("tree ring")           # under the ring of trees
go("left", 16); go("up", 13); go("left", 9); go("up", 2); go("left", 0); pb.tick(10); shot("bridge")
tap("left", 30); shot("bridge shut"); assert talking(), "the bridge should be shut before the showdown"
finish_talk(); assert pos()[0] == 0
pb.memory[SYM["_got"]] |= 0x20                                       # the showdown is over: the barrier is down
tap("left", 60); pb.tick(60); print("west of the bridge:", pos()); assert pos()[0] == 14
start_map[0] = 14; shot("forest east")
go("left", 20); go("up", 8); go("left", 13); pb.tick(10); shot("forest mid")
go("left", 12); go("up", 6); go("left", 6); go("up", 4); go("left", 1); pb.tick(10); shot("forest west")
go("left", 0); tap("left", 30); shot("road on"); assert talking(); finish_talk()
pb.stop()
sheet = Image.new("RGB", (330 * 5, 298 * ((len(shots) + 4) // 5)), "white")
for i, im in enumerate(shots): sheet.paste(im, ((i % 5) * 330, (i // 5) * 298))
sheet.save(f"{out}/kilkenny.png")

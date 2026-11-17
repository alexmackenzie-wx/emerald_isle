#!/usr/bin/env python3
"""Headless test of explore mode: start from the title with SELECT, walk through Alex,
past the hurler and the sleeper, through long grass, and jump between maps."""
import re, sys
from pyboy import PyBoy
from PIL import Image

rom, out = sys.argv[1], sys.argv[2]
SYM = {k: int(v, 16) for k, v in re.findall(r"DEF (\S+) 0x([0-9A-F]+)", open(rom.replace(".gbc", ".noi")).read())}
pb = PyBoy(rom, window="null", cgb=True)
shots = []
def shot():
    shots.append(pb.screen.image.convert("RGB").resize((320, 288), 0))
def tap(btn, wait=20):
    pb.button_press(btn); pb.tick(6); pb.button_release(btn); pb.tick(wait)
def pos():
    return pb.memory[SYM["_cur_id"]], pb.memory[SYM["_px"]], pb.memory[SYM["_py"]]
def talking():
    return bool(pb.memory[0xFF40] & 0x20) and pb.memory[0xFF4B] == 7
def in_battle():
    im = pb.screen.image.convert("RGB")           # two points well apart, so the white breeze sprite can't fool it
    return im.getpixel((2, 2)) == (248, 248, 248) and im.getpixel((84, 2)) == (248, 248, 248)
def go(btn, target):
    axis = 1 if btn in ("left", "right") else 2
    stuck, start_map = 0, pos()[0]
    while pos()[axis] != target and pos()[0] == start_map and stuck < 4:
        before = pos()
        pb.button_press(btn); pb.tick(8); pb.button_release(btn); pb.tick(12)
        assert not in_battle(), "a battle started in explore mode"
        assert not talking(), f"something spoke up unprompted at {pos()}"
        if pos() == before: stuck += 1
    if stuck >= 4: print("  stuck going", btn, "at", pos())

pb.tick(150); shot(); tap("select", 90); print("started at", pos()); shot()
go("left", 9); go("up", 99); pb.tick(40)                       # north to Route 1
go("left", 8); go("up", 14); go("left", 7); go("up", 9); go("right", 8)
go("up", 5); print("walked through Alex to", pos()); shot()
go("left", 7); go("up", 99); pb.tick(40); print("Route 2 (no phone call):", pos())
go("up", 12); print("past the hurler:", pos())
go("left", 6); go("up", 4); print("through the sleeper:", pos()); shot()
go("left", 2); go("up", 2)                                      # into the long grass
for _ in range(12): go("right", 4); go("left", 2)
print("paced the long grass with no encounter:", pos())
tap("start", 60); shot(); tap("right", 90); print("jumped to", pos()); shot()
tap("start", 60); tap("right", 90); print("jumped to", pos()); shot()
pb.stop()
sheet = Image.new("RGB", (330 * len(shots), 288), "white")
for i, im in enumerate(shots):
    sheet.paste(im, (i * 330, 0))
sheet.save(f"{out}/explore.png")

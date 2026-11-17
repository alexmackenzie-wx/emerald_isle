#!/usr/bin/env python3
"""Headless test of the enlarged towns: New Ross's townhouse street, Wexford's entrance,
the PMon Centre, buying in the Mart, and the Opera House and gym. Uses explore mode."""
import re, sys
from pyboy import PyBoy
from PIL import Image

rom, out = sys.argv[1], sys.argv[2]
SYM = {k: int(v, 16) for k, v in re.findall(r"DEF (\S+) 0x([0-9A-F]+)", open(rom.replace(".gbc", ".noi")).read())}
pb = PyBoy(rom, window="null", cgb=True)
shots = []
def shot(): shots.append(pb.screen.image.convert("RGB").resize((320, 288), 0))
def tap(btn, wait=20):
    pb.button_press(btn); pb.tick(6); pb.button_release(btn); pb.tick(wait)
def pos(): return pb.memory[SYM["_cur_id"]], pb.memory[SYM["_px"]], pb.memory[SYM["_py"]]
def talking(): return bool(pb.memory[0xFF40] & 0x20) and pb.memory[0xFF4B] == 7
def word(name): return pb.memory[SYM[name]] | (pb.memory[SYM[name] + 1] << 8)
def go(btn, target):
    axis = 1 if btn in ("left", "right") else 2
    stuck, start_map = 0, pos()[0]
    while pos()[axis] != target and pos()[0] == start_map and stuck < 4:
        before = pos()
        pb.button_press(btn); pb.tick(8); pb.button_release(btn); pb.tick(12)
        if pos() == before: stuck += 1
    if stuck >= 4: print("  stuck going", btn, "at", pos())
def finish_talk():
    quiet = 0
    while quiet < 60:
        if talking(): tap("a", 12); quiet = 0
        else: pb.tick(1); quiet += 1

pb.tick(150); tap("select", 90)
go("right", 16); go("up", 7); pb.tick(10); print("New Ross, townhouse street:", pos()); shot()
go("down", 8); go("right", 22); pb.tick(10); shot()
for _ in range(4): tap("start", 60); tap("right", 90)
print("Wexford entrance:", pos()); shot()
go("right", 7); go("up", 99); pb.tick(40); print("PMon Centre:", pos())
go("up", 4); tap("a", 60); shot(); finish_talk()
go("down", 99); pb.tick(40); print("back outside at", pos())
go("right", 12); shot(); go("up", 99); pb.tick(40); print("Mart:", pos())
pb.memory[SYM["_money"]] = 100
go("up", 4); tap("a", 90); tap("a", 40); shot()                       # the price list
tap("a", 20); tap("down", 10); tap("a", 20); tap("a", 20); pb.tick(10); shot()   # one PBall, two potions
print("after shopping: money", word("_money"), "pballs", pb.memory[SYM["_torcs"]], "potions", pb.memory[SYM["_potions"]])
tap("b", 60); finish_talk(); go("down", 99); pb.tick(40); print("back outside at", pos())
go("right", 18); go("down", 14); go("left", 8); pb.tick(10); print("between the Opera House and gym:", pos()); shot()
go("left", 7); go("up", 9); pb.tick(10); shot()
pb.stop()
sheet = Image.new("RGB", (330 * 4, 298 * ((len(shots) + 3) // 4)), "white")
for i, im in enumerate(shots):
    sheet.paste(im, ((i % 4) * 330, (i // 4) * 298))
sheet.save(f"{out}/towns.png")

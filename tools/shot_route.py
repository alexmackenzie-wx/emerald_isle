#!/usr/bin/env python3
"""Headless test: opening, the bodhran player, Route 1 and the battle with Alex."""
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
import re
SYM = {k: int(v, 16) for k, v in re.findall(r"DEF (\S+) 0x([0-9A-F]+)", open(rom.replace(".gbc", ".noi")).read())}
def pos():
    return pb.memory[SYM["_cur_id"]], pb.memory[SYM["_px"]], pb.memory[SYM["_py"]]
def walk(btn, tiles):                       # one press per tile, checked against the game's own position
    for _ in range(tiles):
        before = pos()
        pb.button_press(btn); pb.tick(8); pb.button_release(btn); pb.tick(12)
        if pos() == before: print("  blocked going", btn, "at", before)
def in_battle():
    return pb.screen.image.convert("RGB").getpixel((2, 2)) == (248, 248, 248)
def talking():
    return bool(pb.memory[0xFF40] & 0x20)
def finish_talk():
    quiet = 0
    while quiet < 70:
        if talking(): tap("a", 12); quiet = 0
        else: pb.tick(1); quiet += 1

pb.tick(150); tap("start", 40); tap("start", 60); pb.tick(60)
finish_talk()
tap("a", 60); tap("a", 80); tap("a", 60); tap("a", 60); tap("a", 30); pb.tick(150)
tap("a", 30); finish_talk()
walk("right", 4); walk("up", 3); tap("a", 30); finish_talk()          # Mom
walk("down", 3); walk("left", 4); walk("down", 1); pb.tick(40)       # out the door
walk("left", 3); walk("up", 11); walk("left", 3); tap("down", 10)    # to the quay
print("at the quay:", pos()); pb.tick(20); shot("r01_drummer")
tap("a", 200); shot("r02_drum_talk"); finish_talk()
walk("right", 3); walk("up", 3); pb.tick(60); shot("r03_route_south")
walk("left", 1); walk("up", 1); walk("left", 1); walk("up", 5); walk("right", 1); print("below Alex:", pos()); pb.tick(10); shot("r04_alex")
tap("up", 10); tap("a", 120); shot("r05_alex_talk"); finish_talk()
pb.tick(260); shot("r06_alex_battle")
n = 0
while in_battle() and n < 200:
    tap("a", 50); n += 1
    if n == 6: shot("r07_fight")
    if n == 30: shot("r08_fight_later")
print("battle ended after", n, "presses")
pb.tick(60); shot("r09_after"); finish_talk(); pb.tick(30); shot("r10_end")
# second attempt with a much stronger partner, to exercise the winning path
P = SYM["_party"]
pb.memory[P + 1] = 20; pb.memory[P + 2] = 60; pb.memory[P + 3] = 0; pb.memory[P + 4] = 60; pb.memory[P + 5] = 0
walk("down", 2); pb.tick(40); walk("left", 3); walk("up", 14); pb.tick(60)
walk("left", 1); walk("up", 1); walk("left", 1); walk("up", 5); walk("right", 1)
print("below Alex again:", pos())
tap("up", 10); tap("a", 60); finish_talk(); pb.tick(260)
n = 0
while in_battle() and n < 200:
    tap("a", 50); n += 1
print("second battle ended after", n, "presses")
pb.tick(90); shot("r11_alex_after"); finish_talk(); pb.tick(30); shot("r12_alex_gone")
walk("up", 2); print("walked past where Alex stood:", pos())
tap("start", 60); shot("r13_pause")
pb.stop()
sheet = Image.new("RGB", (330 * 4, 298 * ((len(shots) + 3) // 4)), "white")
for i, im in enumerate(shots):
    sheet.paste(im, ((i % 4) * 330, (i // 4) * 298))
sheet.save(f"{out}/route.png")

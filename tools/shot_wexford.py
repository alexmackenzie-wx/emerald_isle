#!/usr/bin/env python3
"""Headless test: New Ross -> Route 1 -> Route 2 (rain, trainer, sleeper) -> Wexford -> gym badge.
The starter is boosted so the battles can be won by pressing A."""
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
pb.memory[P + 1] = 25; pb.memory[P + 2] = 80; pb.memory[P + 4] = 80                 # a strong starter for the test
pb.memory[SYM["_flags"]] |= 4                                                        # Alex already beaten
go("down", 7); go("left", 4); go("down", 99); pb.tick(40)
print("New Ross:", pos())
go("left", 9); go("up", 99); pb.tick(40); print("Route 1:", pos())
go("left", 8); go("up", 14); go("left", 7); go("up", 9); go("right", 8); go("up", 5); go("left", 7); go("up", 99)
pb.tick(30); finish_talk(); print("Route 2 after Mom's call:", pos(), "flags", flags()); shot("w01_rain")
go("up", 14); pb.tick(3); shot("w02_spotted"); finish_talk(); print("after the hurler:", pos(), "flags", flags())
go("up", 12); go("left", 6); go("up", 9); shot("w03_sleeper")
tap("up", 10); tap("a", 30); pb.tick(40); finish_talk(); print("after the sleeper:", pos(), "flags", flags())
go("up", 3); go("right", 99); pb.tick(40); print("Wexford:", pos()); shot("w04_wexford")
go("right", 5); go("down", 5); tap("down", 10); tap("a", 60); shot("w05_ruth"); finish_talk()      # Ruth, by the Bullring
go("up", 4); go("right", 9); go("down", 8); go("left", 2); shot("w06_street")
go("up", 99); pb.tick(40); print("Maeve's house:", pos())
go("right", 6); go("up", 4); tap("up", 10); tap("a", 100); shot("w07_maeve"); finish_talk()
print("potions:", pb.memory[SYM["_potions"]])
go("down", 7); go("left", 4); go("down", 99); pb.tick(40)
go("right", 9); go("down", 12); go("left", 2); go("up", 99); pb.tick(40); print("Opera House:", pos())
go("left", 3); go("up", 3); go("right", 5); tap("up", 10); tap("a", 200); shot("w08_opera"); finish_talk()
go("left", 3); go("down", 7); go("right", 4); go("down", 99); pb.tick(40)
go("right", 6); shot("w09_gym_outside"); go("up", 99); pb.tick(40); print("gym:", pos())
go("up", 6); finish_talk(); print("after the gym trainer:", pos(), "flags", flags())
go("left", 3); go("up", 3); go("right", 4); tap("up", 10); tap("a", 100)
finish_talk(); print("after Orla:", pos(), "flags", flags())
tap("start", 60); shot("w10_pause"); tap("left", 120); shot("w11_potion"); finish_talk()
print("potions after using one:", pb.memory[SYM["_potions"]], "hp", pb.memory[P + 2], "/", pb.memory[P + 4])
pb.stop()
sheet = Image.new("RGB", (330 * 5, 298 * ((len(shots) + 4) // 5)), "white")
for i, im in enumerate(shots):
    sheet.paste(im, ((i % 5) * 330, (i // 5) * 298))
sheet.save(f"{out}/wexford.png")

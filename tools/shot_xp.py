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
pb.memory[P + 6] = 200                                                               # 16 XP short of level 6
print("before: level", pb.memory[P + 1], "exp", pb.memory[P + 6])
go("down", 7); go("left", 4); go("down", 99); pb.tick(40)
pb.button_press("left"); pb.tick(16 * 5 + 6); pb.button_release("left"); pb.tick(10)
n = 0
while pb.screen.image.convert("RGB").getpixel((2, 2)) != (248, 248, 248) and n < 300:
    pb.button_press("left" if n % 2 else "right"); pb.tick(17); pb.button_release("left" if n % 2 else "right"); pb.tick(4); n += 1
pb.tick(400)
frames = []
for i in range(30):                                                                  # press A through the battle, filming
    tap("a", 45); frames.append(pb.screen.image.convert("RGB").copy())
    if pb.screen.image.convert("RGB").getpixel((2, 2)) != (248, 248, 248): break
print("after: level", pb.memory[P + 1], "exp", pb.memory[P + 6] | (pb.memory[P + 7] << 8), "moves", [pb.memory[P + 10 + k] for k in range(4)])
film = Image.new("RGB", (165 * 10, 149 * ((len(frames) + 9) // 10)), "white")
for i, im in enumerate(frames):
    film.paste(im, ((i % 10) * 165, (i // 10) * 149))
film.save(f"{out}/xp.png")
pb.tick(60); tap("start", 60); shots.append(pb.screen.image.convert("RGB").resize((320, 288), 0)); shots[-1].save(f"{out}/xp_pause.png")
pb.stop()
sheet = Image.new("RGB", (330 * 5, 298 * ((len(shots) + 4) // 5)), "white")
for i, im in enumerate(shots):
    sheet.paste(im, ((i % 5) * 330, (i // 5) * 298))
sheet.save(f"{out}/xp_sheet.png")

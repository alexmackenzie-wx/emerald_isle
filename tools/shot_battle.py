#!/usr/bin/env python3
"""Headless test: plays the opening, walks into long grass, fights a wild battle, saves."""
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
hold("right", 66); hold("up", 50); tap("a", 30); shot("b01_mom"); finish_talk()      # Mom: heal + torcs
hold("down", 40); hold("left", 66); hold("down", 30); pb.tick(40)
hold("left", 16 * 5 + 6)
steps = 0
while not in_battle() and steps < 200:
    pb.button_press("right" if steps % 2 else "left"); pb.tick(8); pb.button_release("right" if steps % 2 else "left"); pb.tick(12); steps += 1     # one tile at a time, staying in the grass
print("battle after", steps, "steps:", in_battle())
strip = []                                  # film the entrances: wild PMON, then the PBall and my PMON
for i in range(72):
    pb.tick(5); strip.append(pb.screen.image.convert("RGB").copy())
    if i % 12 == 11: tap("a", 2)
film = Image.new("RGB", (165 * 12, 149 * 6), "white")
for i, im in enumerate(strip):
    film.paste(im, ((i % 12) * 165, (i // 12) * 149))
film.save(f"{out}/entrance.png")
pb.tick(60); shot("b02_appeared")
tap("a", 90); shot("b03_go")
tap("a", 60); shot("b04_menu")
tap("a", 40); shot("b05_moves")
tap("a", 100); shot("b06_used")
for i in range(4): tap("a", 110); shot(f"b07_turn{i}")
n = 0
while in_battle() and n < 120:
    tap("a", 60); n += 1
    if n == 12: shot("b08_later")
print("left battle:", not in_battle(), "after", n, "presses")
pb.tick(90); finish_talk(); shot("b09_after")
# second battle: throw torcs until something is caught
def find_battle():
    steps = 0
    while not in_battle() and steps < 300:
        pb.button_press("right" if steps % 2 else "left"); pb.tick(8); pb.button_release("right" if steps % 2 else "left"); pb.tick(12); steps += 1     # one tile at a time, staying in the grass
    pb.tick(150); tap("a", 90); tap("a", 60)
for attempt in range(3):
    find_battle()
    for throw in range(5):
        if not in_battle(): break
        tap("right", 10); tap("a", 20); tap("a", 240)
        if throw == 0 and attempt == 0: shot("b10_torc")
        for _ in range(8):
            if not in_battle(): break
            tap("a", 70)
    pb.tick(90); finish_talk()
    if pb.memory[0xFF40] is not None and not in_battle(): pass
tap("start", 60); shot("b11_pause")
for _ in range(4): tap("down", 8)
tap("a", 120); shot("b12_saved")
finish_talk(); tap("b", 60)
pb.stop()
sheet = Image.new("RGB", (330 * 4, 298 * ((len(shots) + 3) // 4)), "white")
for i, im in enumerate(shots):
    sheet.paste(im, ((i % 4) * 330, (i // 4) * 298))
sheet.save(f"{out}/battle.png")

# the save should survive a restart
pb = PyBoy(rom, window="null", cgb=True)
pb.tick(150); im1 = pb.screen.image.convert("RGB").resize((320, 288), 0)
tap("a", 120); im2 = pb.screen.image.convert("RGB").resize((320, 288), 0)
pb.stop()
both = Image.new("RGB", (650, 288), "white"); both.paste(im1, (0, 0)); both.paste(im2, (330, 0))
both.save(f"{out}/continue.png")

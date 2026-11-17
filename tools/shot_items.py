#!/usr/bin/env python3
"""Headless test: plays the opening, walks into long grass, uses a POTION from the ITEMS menu in a wild battle."""
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
P = _S["_party"]
pb.memory[P + 2] = 6                                 # hurt, with two potions in the bag
pb.memory[_S["_potions"]] = 2
steps = 0
while not in_battle() and steps < 200:
    hold("left" if steps % 2 else "right", 17); pb.tick(4); steps += 1
pb.tick(420); tap("a", 90); tap("a", 200); shot("i01_menu")
tap("right", 10); tap("a", 30); shot("i02_items")
tap("down", 10); shot("i03_potion"); tap("a", 60); shot("i04_used")
hp, pots = pb.memory[P + 2], pb.memory[_S["_potions"]]
print("after the potion: hp", hp, "potions", pots)
assert pots == 1 and hp > 6
tap("a", 150); shot("i05_foe_turn"); finish_talk() if not in_battle() else None
for _ in range(4): tap("a", 60)
shot("i06_menu_again")
tap("right", 10); tap("a", 30); tap("right", 10); tap("a", 30); shot("i07_back")
pb.stop()
sheet = Image.new("RGB", (330 * 4, 298 * 2), "white")
for i, im in enumerate(shots):
    sheet.paste(im, ((i % 4) * 330, (i // 4) * 298))
sheet.save(f"{out}/items.png")

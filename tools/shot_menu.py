#!/usr/bin/env python3
"""Headless test: plays the opening, walks into long grass, the START menu and its screens: PMON (with a swap), ITEMS, the trainer card, SAVE."""
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
Q = P + 14                                       # a second PMON, hurt, so there is something to swap and a low bar to see
for k, v in enumerate([3, 4, 5, 0, 16, 0, 70, 0, 0, 0, 1, 4, 0, 0]): pb.memory[Q + k] = v
pb.memory[_S["_party_n"]] = 2
pb.memory[_S["_potions"]] = 2; pb.memory[_S["_money"]] = 250; pb.memory[_S["_tms"]] = 1
first = pb.memory[P]
tap("start", 60); shot("m0_menu")
tap("a", 60); shot("m1_party")
tap("a", 30); shot("m2_party_held"); tap("down", 10); tap("a", 40); shot("m3_party_swapped")
assert pb.memory[P] == 3 and pb.memory[Q] == first, "the two PMON did not swap"
tap("a", 20); tap("up", 10); tap("a", 40)        # and back again
assert pb.memory[P] == first
tap("b", 80); shot("m4_menu_again")
tap("down", 10); tap("a", 60); shot("m5_items"); tap("down", 10); tap("down", 10); tap("down", 10); shot("m6_items_tm")
tap("up", 10); tap("up", 10); tap("up", 10); tap("a", 100); shot("m7_potion_used"); finish_talk(); shot("m8_items_after")
print("potions", pb.memory[_S["_potions"]], "second hp", pb.memory[Q + 2]); assert pb.memory[_S["_potions"]] == 1 and pb.memory[Q + 2] == 16
tap("b", 80)
tap("down", 10); tap("down", 10); tap("a", 60); shot("m9_card"); tap("b", 80)
tap("down", 10); tap("a", 100); shot("m10_saved"); finish_talk(); pb.tick(20); shot("m11_menu_after_save")
tap("b", 40); shot("m12_closed")
pb.stop()
sheet = Image.new("RGB", (330 * 5, 298 * ((len(shots) + 4) // 5)), "white")
for i, im in enumerate(shots): sheet.paste(im, ((i % 5) * 330, (i // 5) * 298))
sheet.save(f"{out}/menu.png")

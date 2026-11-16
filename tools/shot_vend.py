#!/usr/bin/env python3
"""Headless test: plays the opening, walks into long grass, the card machine in New Ross: buying booster packs and the card collection."""
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
    return bool(pb.memory[0xFF40] & 0x20)          # the dialog window is showing
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
        if pb.memory[0xFF40] & 0x20: break
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
def m16(n): return pb.memory[_S[n]] | (pb.memory[_S[n] + 1] << 8)
go("down", 8); pb.tick(60); print("outside:", pos())
go("right", 21); go("down", 18); tap("right", 10); pb.tick(10); shot("v0_machine")
print("at the machine:", pos(), "money", m16("_money"))
assert m16("_money") == 0, "the game should start with no money"
tap("a", 40); finish_talk(); pb.tick(30)                       # nothing in your pocket: no pack
assert m16("_money") == 0 and not pb.memory[_S["_shiny_cards"]]
print("no money, no pack: ok")
pb.memory[_S["_money"]] = 150
for pack in range(3):
    tap("a", 40)
    if pack == 0: shot("v1_offer")
    n = 0
    while m16("_money") == 150 - 50 * pack and n < 40: tap("a", 14); n += 1
    pb.tick(60)
    if m16("_money") != 150 - 50 * (pack + 1):
        print("pack", pack, "not bought, money", m16("_money")); break
    if pack == 0: shot("v2_pack")
    tap("a", 80)
    for i in range(4):
        pb.tick(60 if i < 3 else 150)
        shot("v3_p%d_card%d" % (pack, i))
        tap("a", 60)
    pb.tick(60); shot("v4_p%d_total" % pack); finish_talk()
    print("pack", pack, "money", m16("_money"), "cards", bin(pb.memory[_S["_cards"]]), "shiny", bin(pb.memory[_S["_shiny_cards"]]))
tap("a", 40); finish_talk(); pb.tick(20); shot("v5_broke")
tap("start", 60); shot("v6_pause")
assert m16("_money") == 0 and pb.memory[_S["_shiny_cards"]]
pb.stop()
sheet = Image.new("RGB", (330 * 6, 298 * ((len(shots) + 5) // 6)), "white")
for i, im in enumerate(shots): sheet.paste(im, ((i % 6) * 330, (i // 6) * 298))
sheet.save(f"{out}/vend.png")

#!/usr/bin/env python3
"""Headless test: the New Ross showdown - Team Balor round the Professor, two grunts beaten,
their captain too strong, Alex's battle watched, and the gang running for it."""
import sys, re
from pyboy import PyBoy
from PIL import Image

rom, out = sys.argv[1], sys.argv[2]
pb = PyBoy(rom, window="null", cgb=True)
SYM = {k: int(v, 16) for k, v in re.findall(r"DEF (\S+) 0x([0-9A-F]+)", open(rom.replace(".gbc", ".noi")).read())}
shots = []
def shot(name=""):
    shots.append(pb.screen.image.convert("RGB").copy())
def tap(btn, wait=20):
    pb.button_press(btn); pb.tick(6); pb.button_release(btn); pb.tick(wait)
def pos(): return pb.memory[SYM["_cur_id"]], pb.memory[SYM["_px"]], pb.memory[SYM["_py"]]
def got(): return pb.memory[SYM["_got"]] | (pb.memory[SYM["_got"] + 1] << 8)
def go(btn, target):
    for _ in range(40):
        c = pos()
        if (c[1] if btn in ("left", "right") else c[2]) == target: return
        pb.button_press(btn); pb.tick(8); pb.button_release(btn); pb.tick(12)
        if pos() == c: return

pb.tick(200); tap("select", 120)                 # explore mode, for a party without playing the opening
pb.memory[SYM["_got"]] = 0x1C                    # pickaxe, wall down, Mom has rung
tap("start", 60); tap("a", 60); tap("b", 80)     # in and out of a menu page redraws the town with the scene set
tap("select", 20); tap("b", 60)                  # explore off again: these battles are for real
P = SYM["_party"]
pb.memory[P + 1] = 22; pb.memory[P + 2] = 70; pb.memory[P + 3] = 0; pb.memory[P + 4] = 70; pb.memory[P + 5] = 0    # strong enough for grunts only
for k, v in enumerate((10648).to_bytes(4, "little")): pb.memory[P + 6 + k] = v            # and the experience of a level 22, not a level 100
nx = [pb.memory[SYM["_nx"] + i] for i in range(7)]
print("town people:", nx); assert nx[2] != 255 and nx[5] != 255 and nx[6] == 255
go("left", 10); pb.tick(10); shot()
pb.tick(8); shot()
go("up", 12)                                     # into range: the scene takes over
n = 0
while not got() & 32 and n < 1500:
    tap("a", 22); n += 1
    if n % 14 == 0: shot()
print("taps", n, "got", hex(got()), "hp", pb.memory[P + 2], "level", pb.memory[P + 1], "species", pb.memory[P])
assert got() & 32, "the showdown did not finish"
assert pb.memory[P + 1] < 40 and pb.memory[P] == 6, "the player's own PMON should be back in place"
for _ in range(30): tap("a", 14)
pb.tick(60); shot()
nx = [pb.memory[SYM["_nx"] + i] for i in range(7)]
print("town people after:", nx); assert nx[2] == 255 and nx[5] == 255
pb.stop()
cols = 10
sheet = Image.new("RGB", (165 * cols, 149 * ((len(shots) + cols - 1) // cols)), "white")
for i, im in enumerate(shots): sheet.paste(im, ((i % cols) * 165, (i // cols) * 149))
sheet.save(f"{out}/showdown.png")

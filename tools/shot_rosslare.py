#!/usr/bin/env python3
"""Headless test: Rosslare Strand in explore mode - footprints in the sand, the shallows,
and choosing to battle both trainers with the level 100 stand-in."""
import sys, re
from pyboy import PyBoy
from PIL import Image

rom, out = sys.argv[1], sys.argv[2]
pb = PyBoy(rom, window="null", cgb=True)
SYM = {k: int(v, 16) for k, v in re.findall(r"DEF (\S+) 0x([0-9A-F]+)", open(rom.replace(".gbc", ".noi")).read())}
shots = []
def shot(name):
    im = pb.screen.image.convert("RGB").resize((320, 288), 0)
    im.save(f"{out}/{name}.png"); shots.append(im)
def tap(btn, wait=20):
    pb.button_press(btn); pb.tick(6); pb.button_release(btn); pb.tick(wait)
def pos(): return pb.memory[SYM["_cur_id"]], pb.memory[SYM["_px"]], pb.memory[SYM["_py"]]
def flags(): return pb.memory[SYM["_flags"]] | (pb.memory[SYM["_flags"] + 1] << 8)
def talking(): return bool(pb.memory[0xFF40] & 0x20)
def finish_talk():
    quiet = 0
    while quiet < 70:
        if talking(): tap("a", 12); quiet = 0
        else: pb.tick(1); quiet += 1
def go(btn, target):
    for _ in range(40):
        c = pos()
        if (c[1] if btn in ("left", "right") else c[2]) == target: return
        pb.button_press(btn); pb.tick(8); pb.button_release(btn); pb.tick(12)
        if pos() == c: print("  stuck going", btn, "at", c); return
def text(): return bytes(pb.memory[SYM["_text_buf"] + i] for i in range(12))
def fight():                                    # talk, accept the explore-mode offer, press A to the end
    tap("a", 30)
    n = 0
    while text() != b"EXPLORE MODE" and n < 30: tap("a", 14); n += 1
    finish_talk(); pb.tick(300)
    n = 0
    while n < 150:
        tap("a", 40); n += 1
        if not talking() and pb.screen.image.convert("RGB").getpixel((2, 2)) != (248, 248, 248) and n > 8: break
    finish_talk()

pb.tick(200); tap("select", 120)
print("party level", pb.memory[SYM["_party"] + 1]); assert pb.memory[SYM["_party"] + 1] == 100
tap("start", 60); shot("s0_pause")
for k in range(10):
    tap("right", 60)
    if k != 9: tap("start", 60)
print("jumped to", pos()); assert pos()[0] == 10
pb.tick(30); shot("s1_arrive")
go("down", 5); go("left", 6); go("down", 8); go("right", 9); pb.tick(10); shot("s2_footprints")
go("down", 11); pb.tick(10); shot("s3_shallows")
go("left", 5); pb.tick(10); shot("s4_finn"); fight()
print("after Finn: flags", flags()); assert flags() & 16384
shot("s5_after_finn")
go("up", 9); go("right", 15); pb.tick(20); finish_talk(); pb.tick(20)       # Sadhbh spots nobody in explore mode
go("up", 7); pb.tick(10); shot("s6_sadhbh"); fight()
print("after Sadhbh: flags", flags()); assert flags() & 32768
go("left", 8); go("up", 6); pb.tick(10); tap("a", 60); shot("s7_comber"); finish_talk()
go("left", 9); go("up", 0); pb.tick(30); go("up", 20); pb.tick(60); print("north of the strand:", pos()); shot("s8_wexford")
assert pos()[0] == 4
pb.stop()
sheet = Image.new("RGB", (330 * 5, 298 * ((len(shots) + 4) // 5)), "white")
for i, im in enumerate(shots): sheet.paste(im, ((i % 5) * 330, (i // 5) * 298))
sheet.save(f"{out}/rosslare.png")

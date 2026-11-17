#!/usr/bin/env python3
"""Headless test: the Supersoak TM on Rosslare Strand and the ITEMS screen, then Route 3
(the fisher, the bridge, the meadow, the gap, a pickup) and the cave at its end, all in explore mode."""
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
def talking(): return bool(pb.memory[0xFF40] & 0x20) and pb.memory[0xFF4B] == 7
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

P = SYM["_party"]
def got(): return pb.memory[SYM["_got"]] | (pb.memory[SYM["_got"] + 1] << 8)
def jump(n):
    for k in range(n):
        tap("start", 60); tap("right", 60)
pb.tick(200); tap("select", 120)
jump(10); print("jumped to", pos()); assert pos()[0] == 10
go("down", 8); go("right", 12); go("down", 9); pb.tick(10); shot("t0_tm_ball")
tap("a", 40); shot("t1_tm_found"); finish_talk()
print("tms", pb.memory[SYM["_tms"]], "got", got()); assert pb.memory[SYM["_tms"]] & 1 and got() & 1
tap("start", 60); shot("t2_pause"); tap("left", 40); shot("t3_items")
tap("down", 10); tap("down", 10); tap("down", 10); tap("a", 100); shot("t4_taught"); finish_talk(); tap("b", 40); tap("b", 60)
moves = [pb.memory[P + 10 + i] for i in range(4)]
print("moves", moves); assert 13 in moves
jump(1); print("jumped to", pos()); assert pos()[0] == 11
pb.tick(30); shot("t5_route3")
def fight():
    n = 0
    while text() != b"EXPLORE MODE" and n < 30: tap("a", 14); n += 1
    finish_talk(); pb.tick(300)
    n = 0
    while n < 150:
        tap("a", 40); n += 1
        if not talking() and pb.screen.image.convert("RGB").getpixel((2, 2)) != (248, 248, 248) and n > 8: break
    finish_talk()
def beaten(): return pb.memory[SYM["_beaten"]] | (pb.memory[SYM["_beaten"] + 1] << 8)
go("right", 8); go("down", 23); go("up", 22)   # face Tadhg, who stands on the road
tap("a", 30); fight(); print("beaten", beaten()); assert beaten() & 64
go("up", 18); go("left", 6); pb.tick(10); shot("t6_fisher"); tap("a", 30); fight()
print("beaten", beaten()); assert beaten() & 256
go("right", 9); go("up", 15); pb.tick(10); shot("t7_bridge")
go("right", 10); go("up", 13); pb.tick(10); shot("t8_meadow"); go("up", 10)
go("right", 11); pb.tick(10); shot("t9_niamh"); tap("a", 30); fight()
print("beaten", beaten()); assert beaten() & 128
go("left", 2)
tap("start", 60); tap("select", 20); tap("b", 60)             # explore off, so the PBall is solid and can be faced
tap("up", 10); shot("t10_pickup"); tap("a", 40); finish_talk()
tap("start", 60); tap("select", 20); tap("b", 60)
print("potions", pb.memory[SYM["_potions"]], "got", got()); assert got() & 2
go("right", 6); go("up", 6); pb.tick(10); shot("t11_gap"); go("up", 2); pb.tick(10); shot("t12_cave_mouth"); go("up", 0); pb.tick(60)
print("in the cave:", pos()); assert pos()[0] == 12
shot("t13_cave"); go("up", 3); go("right", 6); tap("a", 60); shot("t14_miner"); finish_talk()
go("left", 4); go("down", 9); pb.tick(60); print("back out:", pos()); shot("t15_out"); assert pos()[0] == 11
pb.stop()
sheet = Image.new("RGB", (330 * 6, 298 * ((len(shots) + 5) // 6)), "white")
for i, im in enumerate(shots): sheet.paste(im, ((i % 6) * 330, (i // 6) * 298))
sheet.save(f"{out}/route3.png")

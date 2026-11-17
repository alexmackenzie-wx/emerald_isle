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
pb.tick(20); shot("t5_start")
go("up", 26); go("right", 17); pb.tick(10); shot("t6_pond"); go("up", 21); go("left", 5)
go("up", 20); go("right", 8); pb.tick(10); shot("t7_fisher"); tap("a", 30); fight()        # Eamon, on the south bank
print("beaten", beaten()); assert beaten() & 256
go("left", 5); go("up", 17); pb.tick(10); shot("t8_bridge"); go("up", 16); go("right", 20)
go("up", 13); pb.tick(10); shot("t9_meadow"); go("up", 9); go("left", 13); pb.tick(10); shot("t10_trees")
go("left", 9); go("up", 6); pb.tick(10); shot("t11_gap"); go("up", 2); go("right", 10); pb.tick(10); shot("t12_cave_mouth")
go("up", 0); pb.tick(60); print("in the cave:", pos()); assert pos()[0] == 12
shot("t13_cave")
tap("start", 60); tap("select", 20); tap("b", 60)             # explore off: people and rock are solid again
go("down", 4); go("left", 3); tap("left", 10); tap("a", 40); shot("t14_riddle")
def to_choices():                                   # press A through the riddle until the box closes and reopens as a list
    for _ in range(80):
        pb.button_press("a"); pb.tick(6); pb.button_release("a")
        for _ in range(14):
            pb.tick(1)
            if not talking(): break
        if not talking(): break
    for _ in range(120):
        if talking(): break
        pb.tick(1)
    pb.tick(20)
to_choices(); shot("t15_choices")
tap("a", 60); shot("t16_wrong"); finish_talk()                  # the first answer is wrong
assert not got() & 4
tap("a", 40); to_choices()
tap("down", 10); tap("a", 60); shot("t17_right"); finish_talk()
print("got", got()); assert got() & 4
go("up", 2); go("right", 6); go("up", 1); tap("up", 10); pb.tick(10); shot("t18_soft_rock")
tap("a", 120); shot("t19_chip"); finish_talk(); pb.tick(420); shot("t20_gallan")
assert pb.screen.image.convert("RGB").getpixel((2, 2)) == (248, 248, 248), "no battle after the pickaxe"
n = 0
while n < 150:
    tap("a", 40); n += 1
    if not talking() and pb.screen.image.convert("RGB").getpixel((2, 2)) != (248, 248, 248) and n > 8: break
finish_talk(); shot("t21_after")
def strike():                                       # swing the pickaxe, then fight whatever wakes
    tap("up", 10); tap("a", 120); finish_talk(); pb.tick(420)
    assert pb.screen.image.convert("RGB").getpixel((2, 2)) == (248, 248, 248), "no battle after the pickaxe"
    n = 0
    while n < 150:
        tap("a", 40); n += 1
        if not talking() and pb.screen.image.convert("RGB").getpixel((2, 2)) != (248, 248, 248) and n > 8: break
    finish_talk()
assert not got() & 8
strike(); assert not got() & 8
strike(); print("got", got()); assert got() & 8, "the wall should be down after the third blow"
pb.tick(20); shot("t22_wall_down")
tap("up", 10); tap("a", 60); shot("t23_carving"); finish_talk()
go("down", 7); go("left", 4); go("down", 9); pb.tick(120); print("back out:", pos()); assert pos()[0] == 11
shot("t24_call"); finish_talk()
print("got", got()); assert got() & 16, "Mom should have rung"
tap("start", 60); tap("select", 20)                             # explore back on, and hop round to Route 1
for k in range(6):                              # cave, lab, forest, New Ross, home, Route 1
    tap("right", 60)
    if k != 5: tap("start", 60)
print("jumped to", pos()); assert pos()[0] == 2
nx = [pb.memory[SYM["_nx"] + i] for i in range(4)]
print("route 1 people:", nx); assert nx[2] != 255 and nx[3] != 255, "the grunts should be on the road"
go("left", 7); go("up", 9); go("right", 8); go("up", 7); go("left", 7); go("up", 5); pb.tick(10); shot("t25_grunt")
tap("a", 30); shot("t26_grunt_talk"); fight()
print("beaten", beaten()); assert beaten() & 512
nx = [pb.memory[SYM["_nx"] + i] for i in range(4)]
print("route 1 people:", nx); assert nx[2] == 255 and nx[3] != 255, "the beaten grunt should clear off, the other stay"
shot("t27_grunt_gone")
pb.stop()
sheet = Image.new("RGB", (330 * 6, 298 * ((len(shots) + 5) // 6)), "white")
for i, im in enumerate(shots): sheet.paste(im, ((i % 6) * 330, (i // 6) * 298))
sheet.save(f"{out}/route3.png")

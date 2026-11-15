#!/usr/bin/env python3
"""Headless test: the Professor's visit, the four-frame walk, the potion on Route 1,
a thud against a wall, and Alex's Cream Soda."""
import sys, re
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
SYM = {k: int(v, 16) for k, v in re.findall(r"DEF (\S+) 0x([0-9A-F]+)", open(rom.replace(".gbc", ".noi")).read())}
def m(name): return pb.memory[SYM[name]] + (pb.memory[SYM[name] + 1] << 8 if name == "_flags" else 0)
def pos(): return m("_cur_id"), m("_px"), m("_py")
def talking(): return bool(pb.memory[0xFF40] & 0x20)
def finish_talk():
    quiet = 0
    while quiet < 70:
        if talking(): tap("a", 12); quiet = 0
        else: pb.tick(1); quiet += 1
def go(btn, target):                         # walk until a coordinate is reached
    for _ in range(40):
        c = pos()
        if (c[1] if btn in ("left", "right") else c[2]) == target: return
        pb.button_press(btn); pb.tick(8); pb.button_release(btn); pb.tick(12)
        if pos() == c: print("  stuck going", btn, "at", c); return
def in_battle():
    return pb.screen.image.convert("RGB").getpixel((2, 2)) == (248, 248, 248)

pb.tick(150); tap("start", 40); tap("start", 60); pb.tick(60)
finish_talk()
tap("a", 60); tap("a", 80)                                   # the pack: open it, then card by card
for i in range(3): tap("a", 60)
pb.tick(150); shot("p01_shiny")
def until_talk():
    n = 0
    while not talking() and n < 600: pb.tick(1); n += 1
def talk_b():
    quiet = 0
    while quiet < 70:
        if talking(): tap("b", 12); quiet = 0
        else: pb.tick(1); quiet += 1
tap("a", 40); shot("p02_card_text")
while not (m("_flags") & 1024): tap("a", 12)
pb.tick(40); shot("p04_prof_enters"); pb.tick(50); shot("p05_prof_walks")
until_talk(); pb.tick(40); shot("p05b_greets_mom")
def text(): return bytes(pb.memory[SYM["_text_buf"] + i] for i in range(14))
while text() != b"PROF: And who'": tap("a", 12)
pb.tick(60); shot("p06_offer")
talk_b(); shot("p07_declined")
print("declined: starter", m("_starter"), "party", m("_party_n"))
assert m("_party_n") == 0 and m("_starter") == 255
tap("a", 60); tap("a", 80)                                   # a second pack
for i in range(3): tap("a", 60)
pb.tick(150); tap("a", 40); tap("a", 60); pb.tick(60); shot("p08_second_offer")
n = 0
while not m("_party_n") and n < 40: tap("a", 12); n += 1
pb.tick(50); shot("p09_ball"); pb.tick(40); shot("p10_burst"); pb.tick(60); shot("p11_gesture"); pb.tick(120); shot("p12_received")
finish_talk(); pb.tick(30); shot("p13_home_after")
print("accepted: starter", m("_starter"), "party", m("_party_n"), "level", pb.memory[SYM["_party"] + 1])
assert m("_party_n") == 1
tap("a", 30); shot("p14_pack_done"); finish_talk()
# the walk cycle, frame by frame
pb.button_press("right")
for i in range(4): pb.tick(4); shot(f"p15_walk{i}")
pb.button_release("right"); pb.tick(30)
go("right", 8); go("up", 4); tap("a", 30); finish_talk()      # Mom heals and hands over PBalls
print("pballs", m("_torcs"))
go("down", 7); go("left", 4); go("down", 8); pb.tick(60)
print("outside:", pos())
go("left", 9); go("up", 0); pb.tick(20); go("up", 14); pb.tick(60)
print("route 1:", pos()); shot("p17_route1")
go("left", 7); go("up", 11); go("left", 6); pb.tick(10); shot("p18_item")
tap("left", 10); tap("a", 30); shot("p19_item_rise"); pb.tick(30); shot("p20_item_text"); finish_talk()
print("potions", m("_potions"), "flags", m("_flags"))
assert m("_potions") == 1
shot("p21_item_gone")
P = SYM["_party"]
pb.memory[P + 1] = 20; pb.memory[P + 2] = 60; pb.memory[P + 3] = 0; pb.memory[P + 4] = 60; pb.memory[P + 5] = 0
go("right", 7); go("up", 9); go("right", 8); pb.tick(10); print("below Alex:", pos()); shot("p22_alex")
tap("up", 10); tap("a", 60); shot("p23_alex_talk"); finish_talk(); pb.tick(260)
n = 0
while in_battle() and n < 200: tap("a", 50); n += 1
print("battle ended after", n, "presses")
for i in range(40):
    tap("a", 14)
    if m("_sodas"): break
pb.tick(40); shot("p24_soda"); finish_talk()
print("sodas", m("_sodas"))
assert m("_sodas") == 1
tap("start", 60); shot("p25_pause")
lv = pb.memory[P + 1]
tap("up", 120); shot("p26_soda_used"); finish_talk(); pb.tick(40); shot("p27_pause_after")
print("level", lv, "->", pb.memory[P + 1], "sodas", m("_sodas"))
assert pb.memory[P + 1] == lv + 1 and m("_sodas") == 0
pb.stop()
sheet = Image.new("RGB", (330 * 5, 298 * ((len(shots) + 4) // 5)), "white")
for i, im in enumerate(shots):
    sheet.paste(im, ((i % 5) * 330, (i // 5) * 298))
sheet.save(f"{out}/prof.png")

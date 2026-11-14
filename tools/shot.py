#!/usr/bin/env python3
"""Headless smoke test: boots the ROM in PyBoy, plays the opening, saves screenshots."""
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

pb.tick(150); shot("01_title")
tap("start", 40); shot("02_name")
tap("b"); tap("b"); tap("right"); tap("a"); shot("03_name_edit")
tap("start", 60)
pb.tick(200); shot("04_home_intro")
for _ in range(5): tap("a", 150)
shot("05_home")
tap("a", 60); shot("06_pack")
tap("a", 80); shot("07_card1")
tap("a", 60); shot("08_card2")
tap("a", 60); tap("a", 30); pb.tick(60); shot("09_shiny")
pb.tick(23); shot("10_shiny_b")
tap("a", 150); shot("11_got")
tap("a", 100); tap("a", 80)
hold("down", 22); pb.tick(40); shot("12_town")
hold("up", 12); pb.tick(60)
hold("right", 66); hold("up", 60); hold("a", 6); pb.tick(200); shot("13_mom")
tap("a", 150); tap("a", 150); tap("a", 150); tap("a", 60)
hold("left", 66); hold("up", 20); hold("a", 6); pb.tick(260); shot("14_pack_again")
pb.stop()

sheet = Image.new("RGB", (330 * 5, 298 * ((len(shots) + 4) // 5)), "white")
for i, im in enumerate(shots):
    sheet.paste(im, ((i % 5) * 330, (i // 5) * 298))
sheet.save(f"{out}/sheet.png")

#!/usr/bin/env python3
"""Headless smoke test: boots the ROM in PyBoy, plays a script, saves screenshots."""
import sys
from pyboy import PyBoy

rom, out = sys.argv[1], sys.argv[2]
pb = PyBoy(rom, window="null", cgb=True)
n = 0
def shot(name):
    pb.screen.image.resize((480, 432), 0).save(f"{out}/{name}.png")
def hold(btn, frames):
    pb.button_press(btn); pb.tick(frames); pb.button_release(btn); pb.tick(2)

pb.tick(150); shot("1_title")
hold("start", 5); pb.tick(30); shot("2_home")
hold("up", 4); pb.tick(20); hold("a", 3); pb.tick(60); shot("3_door")
hold("a", 3); pb.tick(20)
hold("left", 16 * 3); hold("up", 16 * 4); pb.tick(20); shot("4_street")
hold("left", 16 * 5); pb.tick(10); hold("up", 16 * 4); pb.tick(10); shot("5_quay")
hold("a", 3); pb.tick(120); shot("6_ship")
pb.stop()

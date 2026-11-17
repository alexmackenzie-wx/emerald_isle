#!/usr/bin/env python3
"""Headless test: films the battle transition and the PBall throw, and records the battle music."""
import re, sys
import numpy as np
from pyboy import PyBoy
from PIL import Image

rom, out = sys.argv[1], sys.argv[2]
pb = PyBoy(rom, window="null", cgb=True, sound_emulated=True)
audio = []
def tick(n=1):
    for _ in range(n):
        pb.tick(1, True, True); audio.append(np.array(pb.sound.ndarray)[:, 0].astype(float).copy())
def tap(btn, wait=20):
    pb.button_press(btn); tick(6); pb.button_release(btn); tick(wait)
def talking():
    return bool(pb.memory[0xFF40] & 0x20) and pb.memory[0xFF4B] == 7
def finish_talk():
    quiet = 0
    while quiet < 90:
        if talking(): tap("a", 12); quiet = 0
        else: tick(1); quiet += 1
def in_battle():
    return pb.screen.image.convert("RGB").getpixel((2, 2)) == (248, 248, 248)
def hold(btn, n):
    pb.button_press(btn); tick(n); pb.button_release(btn); tick(2)

tick(150); tap("start", 40); tap("start", 60); tick(60); finish_talk()
tap("a", 60); tap("a", 80); tap("a", 60); tap("a", 60); tap("a", 30); tick(150); # the Professor's visit: keep pressing A until the PMON is handed over and he has finished talking
import re as _re
_S = {k: int(v, 16) for k, v in _re.findall(r"DEF (\S+) 0x([0-9A-F]+)", open(rom.replace(".gbc", ".noi")).read())}
while not pb.memory[_S["_party_n"]]: tap("a", 12)
for _ in range(2):
    for _ in range(600):
        if pb.memory[0xFF40] & 0x20 and pb.memory[0xFF4B] == 7: break
        pb.tick(1)
    finish_talk()
hold("down", 40); hold("left", 2); tick(40); hold("left", 16 * 5 + 6)
frames, n = [], 0
while not in_battle() and n < 3000:                # pace in the grass, filming every 5th frame
    if n % 21 == 0: pb.button_press("left" if (n // 21) % 2 else "right")
    if n % 21 == 17: pb.button_release("left"); pb.button_release("right")
    tick(1); n += 1
    if n % 5 == 0: frames.append(pb.screen.image.convert("RGB").copy())
pb.button_release("left"); pb.button_release("right")
frames = frames[-36:]
tick(260)                                          # the wild PMON arrives
for i in range(60):                                # dismiss the messages while filming every 3rd frame
    if i in (0, 14): pb.button_press("a")
    if i in (2, 16): pb.button_release("a")
    tick(3); frames.append(pb.screen.image.convert("RGB").copy())
film = Image.new("RGB", (165 * 12, 149 * ((len(frames) + 11) // 12)), "white")
for i, im in enumerate(frames):
    film.paste(im, ((i % 12) * 165, (i // 12) * 149))
film.save(f"{out}/intro.png")
mark = sum(len(a) for a in audio)
tick(60 * 12)                                      # let the battle theme play
a = np.concatenate(audio)[mark:]
sr = pb.sound.sample_rate
w = int(sr * 0.002); env = np.sqrt(((a[:len(a) // w * w] - a.mean()) ** 2).reshape(-1, w).mean(axis=1))
print("battle music: level range", a.min(), a.max(), "silent" if a.max() == a.min() else "playing")
seg = a[sr * 3:sr * 3 + sr // 2]; seg = seg - seg.mean()
sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))); fr = np.fft.rfftfreq(len(seg), 1 / sr)
print("strongest pitches (Hz):", sorted(set(round(float(fr[i])) for i in np.argsort(sp)[-8:])))
pb.stop()

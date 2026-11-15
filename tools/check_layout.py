#!/usr/bin/env python3
"""Checks the ROM layout after a build.

Bank 0 is always mapped. Bank 1 holds the overworld code and is mapped by default.
Routines that switch banks must sit in bank 0, the fixed code must not run past the
end of bank 1, and everything the battle code (bank 5) calls or reads must be in
bank 0 or RAM, because bank 1 is switched out while a battle runs."""
import re, sys
sym = dict(re.findall(r"DEF (\S+) 0x([0-9A-F]+)", open(sys.argv[1]).read()))
v = {k: int(x, 16) for k, x in sym.items()}
home_end = max(v[f"s_{a}"] + v[f"l_{a}"] for a in ("_HOME", "_BASE", "_GSINIT", "_INITIALIZER", "_LIT", "_CODE_0"))
code_end = v["s__CODE"] + v["l__CODE"]
print(f"bank 0 (shared core): {0x4000 - code_end} bytes free")
for n in (1, 2, 3, 4, 5):
    if f"l__CODE_{n}" in v: print(f"bank {n}: {0x4000 - v[f'l__CODE_{n}']} bytes free")
assert home_end <= v["s__CODE"], "home area overlaps the main code: raise -Wl-b_CODE in the Makefile"
assert code_end <= 0x4000, "the shared core no longer fits in bank 0: move something into a bank"
assert all(v.get(f"l__CODE_{n}", 0) <= 0x4000 for n in range(1, 8)), "a bank is over 16 KB"
for fn in ("_bank_copy", "_load_gfx", "_load_text", "_music_isr", "_music_play", "_set_bkg_data", "_set_sprite_data"):
    assert v[fn] < 0x4000, f"{fn} must be in bank 0: it runs while another bank is switched in"
if len(sys.argv) > 2:
    text = open(sys.argv[2], errors="replace").read()
    refs = set(re.findall(r"^S (\S+) Ref", text, re.M)) - set(re.findall(r"^S (\S+) Def", text, re.M))
    bad = sorted((n, v[n]) for n in refs if n in v and 0x4000 <= v[n] < 0x8000 and not n.startswith(("s_", "l_", "b_", ".")))
    highest = max((v[n] for n in refs if n in v and v[n] < 0x4000), default=0)
    print(f"battle bank: {len(refs)} outside references, highest in bank 0 at {highest:#06x}")
    assert not bad, "the battle bank uses things that sit in bank 1: " + ", ".join(f"{n} at {a:#06x}" for n, a in bad)

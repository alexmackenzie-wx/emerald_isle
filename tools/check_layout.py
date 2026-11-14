#!/usr/bin/env python3
"""Checks the ROM layout after a build. The art loader switches ROM banks, so it
must sit in bank 0, and the fixed code must not run past the end of bank 1."""
import re, sys
sym = dict(re.findall(r"DEF (\S+) 0x([0-9A-F]+)", open(sys.argv[1]).read()))
v = {k: int(x, 16) for k, x in sym.items()}
home_end = max(v[f"s_{a}"] + v[f"l_{a}"] for a in ("_HOME", "_BASE", "_GSINIT", "_INITIALIZER", "_LIT", "_CODE_0"))
code_end = v["s__CODE"] + v["l__CODE"]
print(f"fixed code: home ends {home_end:#06x}, main code {v['s__CODE']:#06x}-{code_end:#06x} ({0x8000 - code_end} bytes free)")
assert home_end <= v["s__CODE"], "home area overlaps the main code: raise -Wl-b_CODE in the Makefile"
assert code_end <= 0x8000, "fixed code no longer fits in banks 0 and 1: move code or data into a bank"
for fn in ("_bank_copy", "_load_gfx", "_set_bkg_data", "_set_sprite_data"):
    assert v[fn] < 0x4000, f"{fn} must be in bank 0: it runs while bank 2 is switched in"

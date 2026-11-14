# Emerald Isle

An original creature-collecting RPG for the Game Boy Color, set in Ireland. Written in C with GBDK-2020.

- `emerald-isle.gbc` is the latest built ROM.
- `web/emerald-isle-play.html` is a playable browser page (ROM plus a JavaScript emulator).
- `src/main.c` is the game; `tools/gen_assets.py` holds all art, maps and text and generates `src/gen/`.

## Build

```bash
make GBDK=/path/to/gbdk
```

```bash
make web V=v0.3
```

`python3 tools/shot.py build/emerald-isle.gbc shots` plays the opening in PyBoy and saves screenshots.

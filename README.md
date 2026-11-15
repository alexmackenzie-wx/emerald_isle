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
make web V=v0.14
```

## Layout

The ROM is an MBC5 cartridge with battery RAM for saves. Code and small data sit in banks 0 and 1; creature art and tile sets are in bank 2 (`src/gen/art.c`); back views, map layouts and all dialogue are in bank 3 (`src/gen/art_back.c`). `tools/check_layout.py` runs after each build and fails it if the fixed code outgrows its space.

- `src/battle.c`: wild battles, catching, experience.
- `src/sound.c`: music driver; songs are written as text in `tools/gen_music.py` and stored in bank 4.

## Tests

`python3 tools/shot.py build/emerald-isle.gbc shots` plays the opening in PyBoy and saves screenshots.
`python3 tools/shot_battle.py build/emerald-isle.gbc shots` goes on to fight, catch, save and reload.
`python3 tools/shot_wexford.py build/emerald-isle.gbc shots` plays from New Ross through Route 2 to the Wexford gym badge.
`python3 tools/shot_route.py build/emerald-isle.gbc shots` covers the bodhrán player, Route 1 and both outcomes of the Alex battle.

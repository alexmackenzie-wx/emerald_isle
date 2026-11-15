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

The ROM is an MBC5 cartridge with battery RAM for saves, split into 16 KB banks:

| Bank | Holds |
|---|---|
| 0 | Always mapped. GBDK's library, the shared engine core (`src/core.c`), the music driver (`src/sound.c`) and the game data tables. |
| 1 | The overworld (`src/main.c`): maps, characters, the card pack, saving, pause and title screens. Mapped whenever a battle is not running. |
| 2 | Creature art and tile sets (`src/gen/art.c`). |
| 3 | Back views, map layouts and all dialogue (`src/gen/art_back.c`). |
| 4 | Music (`src/gen/music_data.c`). |
| 5 | The battle system (`src/battle.c`). |

While a battle runs, bank 5 replaces bank 1, so battle code may only use what is in bank 0. `tools/check_layout.py` runs after every build and fails it if that rule is broken or a bank overflows.

## Explore mode

For testing. Press SELECT on the title screen to start in New Ross with no opening, or SELECT on the pause screen to toggle it. While it is on there are no wild encounters or trainer battles, you can walk through people, and RIGHT on the pause screen jumps to the next map. It is never saved.

## Tests

`python3 tools/shot.py build/emerald-isle.gbc shots` plays the opening in PyBoy and saves screenshots.
`python3 tools/shot_battle.py build/emerald-isle.gbc shots` goes on to fight, catch, save and reload.
`python3 tools/shot_wexford.py build/emerald-isle.gbc shots` plays from New Ross through Route 2 to the Wexford gym badge.
`python3 tools/shot_explore.py build/emerald-isle.gbc shots` checks explore mode.
`python3 tools/shot_route.py build/emerald-isle.gbc shots` covers the bodhrán player, Route 1 and both outcomes of the Alex battle.

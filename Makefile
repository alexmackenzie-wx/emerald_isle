GBDK ?= /home/user/tools/gbdk
LCC  = $(GBDK)/bin/lcc
ROM  = build/emerald-isle.gbc

# Link order matters: the first files land in bank 0, where the battle bank can reach them.
SRC = src/gen/assets.c src/gen/music_freq.c src/sound.c src/core.c src/main.c src/cards.c src/battle.c src/gen/music_data.c src/gen/art.c src/gen/art_back.c src/gen/art_b8.c src/gen/art_b9.c src/gen/art_b10.c src/gen/art_b4.c src/gen/art_x.c
# MBC5 cartridge with battery-backed RAM: 16 ROM banks (256 KB), 1 RAM bank for saves
CART = -Wl-yt0x1B -Wl-yo16 -Wl-ya1
# Put the always-mapped "home" routines first (bank 0) and the rest after them;
# tools/check_layout.py verifies this still holds after every build.
LAYOUT = -Wl-j -Wl-b_HOME=0x200 -Wl-b_CODE=0x14A0
$(ROM): $(SRC) src/sound.h src/game.h src/core.h
	@mkdir -p build
	$(LCC) -Wm-yC -Wm-yn"EMERALDISLE" $(CART) $(LAYOUT) -o $@ $(SRC)
	$(LCC) -c -o build/battle.o src/battle.c
	python3 tools/check_layout.py build/emerald-isle.noi build/battle.o

src/gen/art.c src/gen/art_back.c src/gen/art_x.c: src/gen/assets.c

src/gen/music_data.c src/gen/music_freq.c: tools/gen_music.py
	@mkdir -p src/gen
	python3 tools/gen_music.py src/gen

src/gen/assets.c: tools/gen_assets.py
	@mkdir -p src/gen
	python3 tools/gen_assets.py src/gen

clean:
	rm -rf build src/gen

.PHONY: clean

# Playable browser page (ROM + JS emulator in one HTML file)
web: $(ROM)
	python3 tools/build_web.py $(ROM) $(V)
.PHONY: web

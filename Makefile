GBDK ?= /home/user/tools/gbdk
LCC  = $(GBDK)/bin/lcc
ROM  = build/emerald-isle.gbc

SRC = src/main.c src/battle.c src/sound.c src/gen/assets.c src/gen/music_data.c src/gen/art.c
# MBC5 cartridge with battery-backed RAM: 4 ROM banks (64 KB), 1 RAM bank for saves
CART = -Wl-yt0x1B -Wl-yo4 -Wl-ya1
# Put the always-mapped "home" routines first (bank 0) and the rest after them;
# tools/check_layout.py verifies this still holds after every build.
LAYOUT = -Wl-j -Wl-b_HOME=0x200 -Wl-b_CODE=0x1200
$(ROM): $(SRC) src/sound.h src/game.h
	@mkdir -p build
	$(LCC) -Wm-yC -Wm-yn"EMERALDISLE" $(CART) $(LAYOUT) -o $@ $(SRC)
	python3 tools/check_layout.py build/emerald-isle.noi

src/gen/art.c: src/gen/assets.c

src/gen/music_data.c: tools/gen_music.py
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

GBDK ?= /home/user/tools/gbdk
LCC  = $(GBDK)/bin/lcc
ROM  = build/emerald-isle.gbc

# -yC: Game Boy Color only
SRC = src/main.c src/sound.c src/gen/assets.c src/gen/music_data.c
$(ROM): $(SRC) src/sound.h
	@mkdir -p build
	$(LCC) -Wm-yC -Wm-yn"EMERALDISLE" -o $@ $(SRC)

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

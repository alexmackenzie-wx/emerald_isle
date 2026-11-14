GBDK ?= /home/user/tools/gbdk
LCC  = $(GBDK)/bin/lcc
ROM  = build/tirbeo.gbc

# -yC: Game Boy Color only
$(ROM): src/main.c src/gen/assets.c
	@mkdir -p build
	$(LCC) -Wm-yC -Wm-yn"TIRBEO" -o $@ src/main.c src/gen/assets.c

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

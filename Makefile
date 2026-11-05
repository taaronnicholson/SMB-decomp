# Build: make   Verify: make verify   Regenerate sources from ROM: make regen
CA65 ?= ca65
LD65 ?= ld65
TARGET = build/game.nes
SRCS = $(wildcard src/*.s)

all: $(TARGET)

build/main.o: $(SRCS)
	@mkdir -p build
	$(CA65) -I src -o $@ src/main.s

$(TARGET): build/main.o nes.cfg
	$(LD65) -C nes.cfg -o $@ build/main.o

SHA1 = c1bc357fce0aee0973e8d1f7aac75a68d52bea02

verify: $(TARGET)
	@echo "$(SHA1)  $(TARGET)" | sha1sum -c -
	@if [ -f rom/game.nes ]; then cmp $(TARGET) rom/game.nes && echo "OK: identical to rom/game.nes"; fi

regen:
	python3 -I tools/gen_sound_hints.py
	python3 -I tools/gen_ppu_hints.py
	python3 -I tools/gen_text_hints.py
	python3 -I tools/gen_gfx_hints.py
	python3 -I tools/gen_area_hints.py
	python3 -I tools/gen_palette_hints.py
	python3 -I tools/gen_spawn_hints.py
	python3 -I tools/gen_anim_hints.py
	python3 -I tools/gen_player_hints.py
	python3 -I tools/gen_gamestate_hints.py
	python3 -I tools/gen_map_hints.py
	python3 -I tools/gen_entity_hints.py
	python3 -I tools/decomp.py
	python3 -I tools/summarize_handlers.py
	python3 -I tools/summarize_player.py
	python3 -I tools/list_open_items.py

tables:
	python3 -I tools/gen_table_hints.py
	python3 -I tools/decomp.py

check: regen tables verify
	@git diff --exit-code --stat -- src tools docs README.md >/dev/null && echo "OK: regeneration reproduces the committed sources" || (echo "regeneration changed tracked files"; git diff --stat; exit 1)

clean:
	rm -rf build
.PHONY: all verify regen tables check clean

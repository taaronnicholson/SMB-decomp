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

verify: $(TARGET)
	@cmp $(TARGET) rom/game.nes && echo "OK: build matches rom/game.nes" && sha1sum $(TARGET)

regen:
	python3 -I tools/gen_sound_hints.py
	python3 -I tools/decomp.py

clean:
	rm -rf build
.PHONY: all verify regen clean

CC = cc
CPPFLAGS = -Isrc
CFLAGS = -std=c11 -O2 -g -Wall -Wextra -Wpedantic -Werror
LDFLAGS =
LDLIBS =

.PHONY: all test clean

all: build/kcc

build:
	mkdir -p build

build/kcc: src/main.c | build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/main.c $(LDFLAGS) $(LDLIBS) -o $@

build/test_support: tests/test_support.c src/source.c src/arena.c src/diagnostic.c src/source.h src/arena.h src/diagnostic.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_support.c src/source.c src/arena.c src/diagnostic.c $(LDFLAGS) $(LDLIBS) -o $@

test: build/kcc build/test_support
	python3 tests/test_cli.py
	./build/test_support

clean:
	rm -rf build

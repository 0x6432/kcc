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

test: build/kcc
	python3 tests/test_cli.py

clean:
	rm -rf build

CC = cc
CPPFLAGS = -Isrc
CFLAGS = -std=c11 -O2 -g -Wall -Wextra -Wpedantic -Werror
LDFLAGS =
LDLIBS =
FUZZ_CC = clang
FUZZ_SECONDS = 10

LEX_SOURCES = src/lex.c src/source.c src/diagnostic.c
HEADERS = $(wildcard src/*.h)

.PHONY: all test clean fuzz-lex

all: build/kcc

build:
	mkdir -p build

build/kcc: src/main.c $(LEX_SOURCES) $(HEADERS) | build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/main.c $(LEX_SOURCES) $(LDFLAGS) $(LDLIBS) -o $@

build/test_support: tests/test_support.c src/source.c src/arena.c src/diagnostic.c src/source.h src/arena.h src/diagnostic.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_support.c src/source.c src/arena.c src/diagnostic.c $(LDFLAGS) $(LDLIBS) -o $@

build/test_lex: tests/test_lex.c $(LEX_SOURCES) $(HEADERS) | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_lex.c $(LEX_SOURCES) $(LDFLAGS) $(LDLIBS) -o $@

build/fuzz_lex: tests/fuzz_lex.c $(LEX_SOURCES) $(HEADERS) | build
	$(FUZZ_CC) $(CPPFLAGS) -std=c11 -O1 -g -Wall -Wextra -Wpedantic -Werror -fsanitize=fuzzer,address,undefined -fno-omit-frame-pointer tests/fuzz_lex.c $(LEX_SOURCES) -o $@

fuzz-lex: build/fuzz_lex
	mkdir -p build/corpus-lex build/fuzz-artifacts
	cp tests/corpus/lex/* build/corpus-lex/
	./build/fuzz_lex build/corpus-lex -max_total_time=$(FUZZ_SECONDS) -max_len=4096 -timeout=5 -rss_limit_mb=512 -artifact_prefix=build/fuzz-artifacts/

test: build/kcc build/test_support build/test_lex
	python3 tests/test_cli.py
	./build/test_support
	./build/test_lex

clean:
	rm -rf build

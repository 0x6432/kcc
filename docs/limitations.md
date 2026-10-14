# Implementation limitations

## M00

- No lexing, parsing, semantic analysis, preprocessing or code generation.
- Only `--help` and `--version` are accepted; C filenames are rejected.
- Tests cover driver behavior and deterministic random CLI arguments.
- Coverage-guided compiler fuzzing starts at M02; CLI random tests are not
  presented as parser/lexer fuzzing.
- CI is configured but a local test pass does not prove a GitHub run passed.
- No claim of C23 conformance or a provided C standard library.

Update this file at every milestone. Separate unsupported features from bugs
in features claimed as implemented. Document impact on other stages.

## M01

Source loading, locations, diagnostics and arenas are implemented and tested.
The driver still does not compile C input. Sources are limited to 16 MiB and
locations are byte-based, not Unicode display-width based. Line splicing and
encoding normalization belong to later translation-phase work. Source creation
requires a fresh or destroyed struct; initialization failure leaves it empty.
Arenas provide max_align_t alignment, not arbitrary over-alignment.

## M02

On-demand lexing handles ASCII identifiers, int/void/return keywords, decimal
integers, initial punctuation, whitespace and comments. No C compilation yet.
Other keywords are ordinary identifier tokens until their feature milestone.
String/character literals, preprocessing, splicing, Unicode identifiers,
nondecimal/suffixed/floating literals and most punctuation are unsupported.
The debug token dump may contain partial output on lexical errors; this is
not compiler IL output. Lexical errors always consume bytes; EOF is stable.
One-token cache keeps parsing independent of whole-file tokenization.

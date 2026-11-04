# Bounded `#line` support

The preprocessor accepts `#line` with a macro-expanded decimal line number
between 1 and 2147483647 and an optional ordinary string filename without
embedded NUL. It remaps subsequent `__LINE__` and `__FILE__` expansions; a
directive without a filename retains the current logical filename. Remappings
are per physical source and apply from the following line. Directives in
inactive conditional groups have no effect.

Diagnostic locations continue to use physical source locations. Directives are
limited to 1024 preprocessing tokens and location lookups share the existing
64 MiB cumulative scanning budget. Filename spelling and macro expansion
remain subject to the existing preprocessor limits.

Regression cases have been added but not run. This is a bounded implementation,
not a claim of full preprocessing conformance.
# Translation clock macros

`__DATE__` and `__TIME__` are predefined string-literal macros. Their values
are captured once when preprocessing begins and remain stable across expansions
and included files. The clock is rendered in UTC using the standard English
month abbreviations, `"Mmm dd yyyy"` and `"hh:mm:ss"` formats; if the clock
cannot be represented, question marks are used.

The implementation currently reads the host clock and does not honor
`SOURCE_DATE_EPOCH`, so builds using these macros are not reproducible.
The implementation has been built; the added regression coverage has not run.
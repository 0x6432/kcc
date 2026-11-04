# Translation clock macros

`__DATE__` and `__TIME__` are predefined string-literal macros. Their values
are captured once when preprocessing begins and remain stable across expansions
and included files. The clock is rendered in UTC using the standard English
month abbreviations, `"Mmm dd yyyy"` and `"hh:mm:ss"` formats; if the clock
cannot be represented, question marks are used.

For reproducible builds, `SOURCE_DATE_EPOCH` can supply a nonnegative decimal
Unix timestamp through 9999-12-31 23:59:59 UTC, subject to the host `time_t`
range. An invalid value is diagnosed when either macro is expanded. Without
the environment variable, the host clock is used.
The implementation has been built; the added regression coverage has not run.
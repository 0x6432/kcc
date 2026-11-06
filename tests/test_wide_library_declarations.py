"""Compile coverage for the bounded fallback wide library declarations."""
import os
import subprocess
import tempfile
from pathlib import Path

compiler = Path(os.environ.get('KCC', Path(__file__).resolve().parents[1] / 'build' / 'kcc'))
body = r'''
#include <time.h>
int formatted(FILE *f, wchar_t *buf, const wchar_t *fmt, va_list ap) {
    return vfwprintf(f,fmt,ap) + vswprintf(buf,32,fmt,ap);
}
int use_wide(FILE *f, wchar_t *s, const wchar_t *fmt, struct tm *t) {
    wchar_t *end=0, *save=0;
    size_t n=wcsftime(s,32,fmt,t) + wcscspn(s,fmt) + wcsspn(s,fmt);
    wcstok(s,fmt,&save); fputws(s,f);
    return (int)(n + wcstol(s,&end,10) + wcstod(s,&end) + fwprintf(f,fmt,42));
}
'''
with tempfile.TemporaryDirectory(prefix='kcc-wide-library-') as directory:
    source = Path(directory) / 'test.c'
    for headers in ('#include <wchar.h>\n#include <stdio.h>\n',
                    '#include <stdio.h>\n#include <wchar.h>\n'):
        source.write_text(headers + body)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0 and not result.stderr, result.stderr
        for symbol in ('wcsftime', 'wcstol', 'wcstod', 'wcstok', 'fwprintf', 'vfwprintf'):
            assert '$' + symbol in result.stdout, symbol
print('wide library declarations compile checks completed')

"""Bounded _Pragma processing, including argument prescans."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
with tempfile.TemporaryDirectory(prefix='kcc-pragma-') as directory:
    path = Path(directory)
    source = path / 'test.c'
    (path / 'once.h').write_text('PASS(_Pragma(L"once"))\nint only;\n')
    source.write_text(r'''
#define DO_PRAGMA(x) _Pragma(#x)
#define PASS(x) x
#include "once.h"
#include "once.h"
_Pragma("vendor \"quoted\"")
PASS(_Pragma(L"vendor wide"))
_Pragma(u"vendor utf16")
_Pragma(U"vendor utf32")
_Pragma(u8"vendor utf8")
DO_PRAGMA(vendor example)
int f(void) { _Pragma("vendor nothing") return 42; }
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert result.stdout.count('data $only') == 1, result.stdout
    for text in ('_Pragma(', '_Pragma(42)', '_Pragma("one" "two")',
                 '_Pragma("pack(1)")', '_Pragma("STDC FENV_ACCESS ON")'):
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode != 0 and result.stderr, text
print('pragma operator checks completed')

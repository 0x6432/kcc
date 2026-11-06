"""Bounded UTF-16, UTF-32, and target-wide literal support."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')
with tempfile.TemporaryDirectory(prefix='kcc-wide-') as directory:
    path = Path(directory)
    source = path / 'test.c'
    source.write_text(r'''
#include <uchar.h>
static_assert(sizeof(u"A😀") == 8 && sizeof(U"A😀") == 12 && sizeof(L"A😀") == 12);
static_assert(_Generic(u"x", char16_t *: 1, default: 0));
static_assert(_Generic(U"x", char32_t *: 1, default: 0));
static_assert(_Generic(L"x", int *: 1, default: 0));
char16_t a[] = "😀" u"x";
char16_t b[3] = { u"A😀" };
char32_t c[] = U"\u00e9\U0001f600";
int d[] = L"x" "y";
char16_t escaped[] = u"\xffff\0";
int main(void) {
  char16_t local[] = u"x😀";
  if (sizeof a != 8 || a[0] != 0xd83d || a[1] != 0xde00 || a[2] != 'x' || a[3]) return 1;
  if (sizeof b != 6 || b[0] != 'A' || b[1] != 0xd83d || b[2] != 0xde00) return 2;
  if (sizeof c != 12 || c[0] != 0xe9 || c[1] != 0x1f600 || c[2]) return 3;
  if (sizeof d != 12 || d[0] != 'x' || d[1] != 'y' || d[2]) return 4;
  if (escaped[0] != 65535 || escaped[1] || escaped[2]) return 5;
  if (local[0] != 'x' || local[1] != 0xd83d || local[2] != 0xde00 || local[3]) return 6;
  return 42;
}
''', encoding='utf-8')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    if qbe:
        il, asm, exe = (path / n for n in ('test.ssa', 'test.s', 'test'))
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), '-o', str(exe)], check=True)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
    for literal in (b'u"\\x10000"', b'U"\\x100000000"', b'L"\\x80000000"',
                    b'u"\\uD800"', b'U"\\U00110000"', b'L"\xed\xa0\x80"',
                    b'u"x" U"y"', b'L"x" u8"y"'):
        source.write_bytes(b'int main(void) { ' + literal + b'; return 0; }\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode != 0 and result.stderr, literal
print('wide string literal checks completed')

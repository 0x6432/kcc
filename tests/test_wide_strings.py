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

    # Range checking happens after adjacent fragments choose their encoding.
    # Cover both orders, macro expansion, fragment escape boundaries and
    # ordinary UTF-8 source characters on either side of a wide numeric escape.
    cases = []
    for prefix, typename, values in (
        ('u', 'char16_t', (0xff, 0x100, 0x1ff, 0xffff)),
        ('U', 'char32_t', (0xff, 0x100, 0xffff, 0x10000, 0xffffffff)),
        ('L', 'int', (0xff, 0x100, 0xffff, 0x10000, 0x7fffffff)),
    ):
        for value in values:
            for literal in (f'"\\x{value:x}" {prefix}""',
                            f'{prefix}"" "\\x{value:x}"',
                            f'{prefix}"A" "\\x{value:x}" "é"'):
                expected = [value] if '"A"' not in literal else [65, value, 0xe9]
                cases.append((typename, literal, expected))
    lines = ['#include <uchar.h>', '#define LARGE "\\x100"',
             'char16_t macro_value[] = LARGE u"";',
             'char16_t boundary[] = u"" "\\x1" "00" "\\400";',
             'int main(void) {']
    for i, (typename, literal, expected) in enumerate(cases):
        lines.append(f'  {typename} s{i}[] = {literal};')
        checks = [f'sizeof s{i} != {len(expected) + 1} * sizeof({typename})']
        checks += [f's{i}[{j}] != {value}u' for j, value in enumerate(expected)]
        checks.append(f's{i}[{len(expected)}] != 0')
        lines.append(f'  if ({" || ".join(checks)}) return 1;')
    lines += ['  if (macro_value[0] != 256 || macro_value[1]) return 2;',
              '  if (boundary[0] != 1 || boundary[1] != 48 || boundary[2] != 48 ||'
              ' boundary[3] != 256 || boundary[4]) return 3;', '  return 42;', '}']
    source.write_text('\n'.join(lines), encoding='utf-8')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    native = path / 'native'
    subprocess.run([host, '-std=c2x', str(source), '-o', str(native)], check=True)
    assert subprocess.run([str(native)], timeout=5).returncode == 42
    if qbe:
        il, asm, exe = (path / n for n in ('mixed.ssa', 'mixed.s', 'mixed'))
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), '-o', str(exe)], check=True)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
    for literal in (b'u"\\x10000"', b'U"\\x100000000"', b'L"\\x80000000"',
                    b'u"\\uD800"', b'U"\\U00110000"', b'L"\xed\xa0\x80"',
                    b'u"x" U"y"', b'L"x" u8"y"',
                    b'u"" "\\x10000"', b'"\\x10000" u""',
                    b'U"" "\\x100000000"', b'L"" "\\x80000000"',
                    b'u8"" "\\x100"', b'"\\x100" u8""',
                    b'"" "\\x100"', b'"\\400"'):
        source.write_bytes(b'int main(void) { ' + literal + b'; return 0; }\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode != 0 and result.stderr, literal
    source.write_bytes(b'[[deprecated("\\x100")]] int f(void); int main(void) { return 0; }\n')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode != 0 and b'exceeds one byte' in result.stderr.encode(), result.stderr
print('wide string literal checks completed')

"""Unicode 15.1 identifier, normalization, preprocessing and native ABI tests."""
import ctypes
import os
import random
import subprocess
import tempfile
import unicodedata
from pathlib import Path

root = Path(__file__).resolve().parents[1]
kcc = Path(os.environ.get('KCC', root / 'build/kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')

with tempfile.TemporaryDirectory(prefix='kcc-unicode-') as td:
    d = Path(td)
    source = d / 'main.c'
    il, asm, exe = (d / n for n in ('main.ssa', 'main.s', 'program'))
    source.write_text(r'''
#define μα(χ) ((χ)+1)
#define JOIN(a,b) a##b
#define STR(a) #a
#define λ 7
#if !defined(\u03bb) || \u03bb != 7
#error Unicode macro mismatch
#endif
typedef int τύπος;
struct Δ { int μέλος; };
extern int \u03bd;
extern int \u03b1(int);
extern int native_call(void);
int κ(int x) { return x + ν; }
int *address = &\u03bd;
int (*callback)(int) = \u03b1;
int \u03c6(void) {
  static_assert(sizeof __func__ == 3);
  return (unsigned char)__func__[0] == 0xcf && (unsigned char)__func__[1] == 0x86 && !__func__[2];
}
int main(void) {
  τύπος JOIN(π,λη) = 8;
  struct Δ s = { .\u03bcέλος = μα(πλη) };
  char *t = STR(\u03bb);
  int A̸ = 1;
  if ((unsigned char)t[0] != 0xce || (unsigned char)t[1] != 0xbb || t[2]) return 1;
  if (s.μέλος != 9 || *address != 13 || callback(2) != 15) return 2;
  if (!φ() || native_call() != 18 || A̸ != 1) return 3;
  goto \u03b6;
  return 4;
ζ:
  return 42;
}
''', encoding='utf-8')
    native = d / 'native.c'
    native.write_text('int ν=13; int α(int x){return x+ν;} extern int κ(int); int native_call(void){return κ(5);}\n', encoding='utf-8')
    result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0 and not result.stderr, result.stderr
    if qbe:
        il.write_text(result.stdout, encoding='utf-8')
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True, timeout=20)
        subprocess.run([host, str(asm), str(native), '-o', str(exe)], check=True, timeout=20)
        assert subprocess.run([str(exe)], timeout=10).returncode == 42
        # Reversed linkage: a native caller references KCC-defined UTF-8 names.
        source.write_text('int café=11; int λ(int x){return x+café;}\n', encoding='utf-8')
        result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=20)
        assert result.returncode == 0 and not result.stderr, result.stderr
        il.write_text(result.stdout, encoding='utf-8')
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        native.write_text('extern int café; extern int λ(int); int main(void){return λ(20)+café;}\n', encoding='utf-8')
        subprocess.run([host, str(asm), str(native), '-o', str(exe)], check=True)
        assert subprocess.run([str(exe)], timeout=10).returncode == 42
    invalid = [
        'int a\u0301;', 'int é\u0327;', 'int \u1100\u1161;', # non-NFC
        'int 😀;', 'int \u0301a;', 'int \\u0061;', 'int \\uD800;',
        'int \\U00110000;', 'int \\u12zz;', 'int x; int \\u0078;',
        'int f(void){int é=1; int \\u00e9=2; return 0;}', # duplicate same-scope definition
    ]
    for program in invalid:
        source.write_text(program, encoding='utf-8')
        result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode != 0 and result.stderr, program
    for data in (b'int \xff;', b'int \xc0\x80;', b'int \xed\xa0\x80;', b'int \xf4\x90\x80\x80;'):
        source.write_bytes(data)
        result = subprocess.run([str(kcc), str(source)], capture_output=True, timeout=10)
        assert result.returncode != 0 and result.stderr, data
    # QBE definition names use a bounded buffer; local names do not.
    good = 'α' * 37 + 'abc'   # 77 UTF-8 bytes, plus quotes and NUL
    bad = 'α' * 39           # 78 bytes
    source.write_text(f'int {good}=42; int main(void){{return {good};}}', encoding='utf-8')
    result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    if qbe:
        il.write_text(result.stdout, encoding='utf-8')
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), '-o', str(exe)], check=True)
        assert subprocess.run([str(exe)], timeout=10).returncode == 42
    source.write_text(f'int {bad};', encoding='utf-8')
    result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode != 0 and 'QBE name limit' in result.stderr
    local = 'α' * 100
    source.write_text(f'int main(void){{int {local}=42; return {local};}}', encoding='utf-8')
    result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    local = 'α' * 4096
    source.write_text(f'int main(void){{int {local}=42; return {local};}}', encoding='utf-8')
    result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    source.write_text('int main(void){int ' + 'α' * 4097 + '=42; return 0;}', encoding='utf-8')
    result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode != 0 and 'identifier length limit' in result.stderr
    source.write_text('int main(void){int a' + '\u0315' * 512 + '\u0323' * 512 + ';}', encoding='utf-8')
    result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode != 0 and 'normalization work limit' in result.stderr

    source.write_text(r'''
struct Ω {int λ;};
struct \u03a9 {int \u03bb;};
enum Θ { μ=3, ν=4 };
enum \u0398 { \u03bc=3, \u03bd=4 };
int main(void) { struct \u03a9 x={.λ=35}; return x.\u03bb + μ + \u03bd; }
''', encoding='utf-8')
    result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    if qbe:
        il.write_text(result.stdout, encoding='utf-8')
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), '-o', str(exe)], check=True)
        assert subprocess.run([str(exe)], timeout=10).returncode == 42

    # Query the actual lexer against Python's independent Unicode 15.1 data.
    # Other Python UCD versions run the stable focused cases above, without
    # claiming to compare two different Unicode revisions.
    if unicodedata.unidata_version == '15.1.0':
        wrapper = d / 'wrapper.c'
        wrapper.write_text('''#include "lex.h"
int check(const unsigned char *s,size_t n) {
 struct source src={.name="test",.data=(unsigned char *)s,.length=n,.prepared=true};
 struct diagnostics d={0}; struct pp_lexer l; pp_lexer_init(&l,&src,&d);
 struct pp_token t=pp_lexer_next(&l);
 return t.kind==pp_identifier && t.length==n && !d.errors && pp_lexer_next(&l).kind==pp_eof;
}
''')
        library = d / 'lexer.so'
        subprocess.run([host, '-std=c11', '-O2', '-fPIC', '-shared', '-I'+str(root/'src'),
                        str(wrapper), str(root/'src/lex.c'), str(root/'src/source.c'),
                        str(root/'src/diagnostic.c'), '-o', str(library)], check=True, timeout=60)
        check = ctypes.CDLL(str(library)).check
        check.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
        check.restype = ctypes.c_int
        randomizer = random.Random(7021)
        for _ in range(50000):
            cp = randomizer.randrange(0x110000)
            if 0xd800 <= cp <= 0xdfff: continue
            for prefix in ('', 'A'):
                name = prefix + chr(cp)
                expected = name.isidentifier() and unicodedata.normalize('NFC', name) == name
                encoded = name.encode('utf-8')
                assert bool(check(encoded, len(encoded))) == expected, (ascii(name), expected)
        marks = [chr(i) for i in range(0x110000) if unicodedata.combining(chr(i)) and ('A'+chr(i)).isidentifier()]
        starts = [chr(i) for i in range(128, 0x3000) if chr(i).isidentifier()]
        for _ in range(10000):
            name = randomizer.choice(starts) + ''.join(randomizer.choice(marks) for _ in range(randomizer.randrange(1, 5)))
            expected = name.isidentifier() and unicodedata.normalize('NFC', name) == name
            encoded = name.encode('utf-8')
            assert bool(check(encoded, len(encoded))) == expected, (ascii(name), expected)
print('Unicode identifiers: preprocessing, NFC, lookup and limits passed' +
      ('; QBE/native ABI and runtime passed' if qbe else '; QBE/runtime not run'))

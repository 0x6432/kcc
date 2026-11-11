"""Attribute reasons survive parsing, binding and diagnostics in supported scopes."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
qbe = os.environ.get('QBE', 'qbe')
cases = [
    ('[[deprecated("use " "new")]] int old; int f(void){return old;}', ['use of deprecated declaration: use new']),
    ('int a [[deprecated("A")]], b [[deprecated("B")]]; int f(void){return a+b;}', ['use of deprecated declaration: A', 'use of deprecated declaration: B']),
    ('[[deprecated("old")]] int x; int x; int f(void){return x;}', ['use of deprecated declaration: old']),
    ('int x; int f(void){[[deprecated("local")]] extern int x; extern int x; return x;} int g(void){return x;}', ['use of deprecated declaration: local']),
    ('[[deprecated("outside")]] int x; int f(void){int x=1; return x;}', []),
    ('int f(void){for([[deprecated("loop")]] int i=0;i<1;i++){} return 0;}', ['use of deprecated declaration: loop'] * 2),
    ('[[deprecated("alias")]] typedef int T; typedef int T; T x;', ['use of deprecated typedef: alias']),
    ('typedef int T; typedef int T [[deprecated("later")]]; T x;', ['use of deprecated typedef: later']),
    ('int f([[deprecated("parameter")]] int x){return x;}', ['use of deprecated declaration: parameter']),
    ('int f([[deprecated("prototype")]] int n, int a[n]){return n+a[0];}', ['use of deprecated declaration: prototype'] * 2),
    ('struct S { int a [[deprecated("field")]]; }; struct S x={.a=2}; int f(void){return x.a+__kcc_offsetof(struct S,a);}', ['use of deprecated member: field'] * 3),
    ('struct S { struct { int a [[deprecated("nested")]]; }; }; struct S x={.a=1}; int f(void){return x.a;}', ['use of deprecated member: nested'] * 2),
    ('enum [[deprecated("enum type")]] E { A [[deprecated("enum value")]]=1, B=A }; enum E x; int f(void){return A;}', ['use of deprecated enumerator: enum value'] * 2 + ['use of deprecated enum type: enum type']),
    ('enum E { A=1 }; enum E { A [[deprecated("new enum")]]=1 }; int f(void){return A;}', ['use of deprecated enumerator: new enum']),
    ('struct [[deprecated("record")]] S {int x;}; struct S x;', ['use of deprecated record type: record']),
    ('[[nodiscard("check result")]] int f(void); void g(void){f(); (void)f();}', ['discarded result of nodiscard function: check result']),
    ('int f(void) [[nodiscard("suffix")]]; int f(void); void g(void){f(), f();}', ['discarded result of nodiscard function: suffix'] * 2),
    ('int f(void); void g(void){[[nodiscard("local")]] int f(void); int f(void); f();} void h(void){f();}', ['discarded result of nodiscard function: local']),
    ('enum [[nodiscard("enum result")]] E { A }; enum E f(void); void g(enum E (*p)(void)){f(); p(); (void)f();}', ['discarded result of function returning nodiscard enum: enum result'] * 2),
    ('struct [[nodiscard("record result")]] S {int x;}; struct S f(void); void g(struct S (*p)(void)){f(); p();}', ['discarded result of function returning nodiscard record: record result'] * 2),
    ('#define WHY "macro " "expanded"\n[[deprecated(WHY)]] int x; int f(void){return x;}', ['use of deprecated declaration: macro expanded']),
    (r'[[deprecated("line\nnull\0end\x7f")]] int x; int f(void){return x;}', [r'use of deprecated declaration: line\x0anull\x00end\x7f']),
    (r'[[deprecated("bad\xff\xc0\x80")]] int x; int f(void){return x;}', [r'use of deprecated declaration: bad\xff\xc0\x80']),
    ('[[deprecated("世界")]] int x; int f(void){return x;}', ['use of deprecated declaration: 世界']),
    ('[[deprecated]] int x; int f(void){return x;}', ['use of deprecated declaration']),
    ('[[nodiscard("ignored")]] int f(void); int g(void){return sizeof((f(),1));}', []),
]
with tempfile.TemporaryDirectory(prefix='kcc-attribute-messages-') as directory:
    directory = Path(directory)
    source = directory / 'test.c'
    def compile(text):
        source.write_text(text, encoding='utf-8')
        return subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=20)
    for text, expected in cases:
        result = compile(text)
        assert result.returncode == 0, (text, result.stderr)
        warnings = [line.split('warning: ', 1)[1] for line in result.stderr.splitlines() if 'warning: ' in line]
        assert sorted(warnings) == sorted(expected), (text, warnings, expected, result.stderr)
        assert len(result.stderr.splitlines()) == len(warnings), result.stderr
    for length in (4096, 4097):
        result = compile('[[deprecated("' + 'x' * length + '")]] int x; int f(void){return x;}')
        assert (result.returncode == 0) == (length == 4096), (length, result.stderr[:200])
        if length == 4096:
            assert 'use of deprecated declaration: ' + 'x' * length in result.stderr
        else:
            assert 'attribute message exceeds 4096 bytes' in result.stderr
    result = compile('[[deprecated(' + '""' * 256 + ')]] int x;')
    assert result.returncode != 0 and 'attribute limit exceeded' in result.stderr
    result = compile('[[deprecated("old")]] int x=40; [[nodiscard("result")]] int f(void){return 2;} int main(void){f();return x+f();}')
    assert result.returncode == 0 and 'old' in result.stderr and 'result' in result.stderr, result.stderr
    il, asm, exe = directory / 'test.ssa', directory / 'test.s', directory / 'test'
    il.write_text(result.stdout)
    subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True, timeout=20)
    subprocess.run([os.environ.get('HOST_CC', 'cc'), '-o', str(exe), str(asm)], check=True, timeout=20)
    assert subprocess.run([str(exe)], timeout=20).returncode == 42
print(f'Attribute messages: {len(cases)} diagnostic cases, byte/fragment bounds and QBE runtime passed')

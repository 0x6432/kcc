"""Object alignment across linkage, storage duration, lists, and record layout."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root / 'build' / 'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')

accepted = [
    ('alignas(16) int x;', 'export data $x = align 16'),
    ('extern alignas(16) int x; alignas(16) int x=3;', 'export data $x = align 16'),
    ('alignas(16) int x; extern int x;', 'export data $x = align 16'),
    ('extern int x; alignas(16) int x=3; extern alignas(16) int x;', 'export data $x = align 16'),
    ('alignas(0) alignas(8) alignas(16) int x=3; extern alignas(16) int x;', 'export data $x = align 16'),
    ('int x=1; extern alignas(0) int x;', 'export data $x = align 4'),
    ('static alignas(16) int x=3;', 'data $x = align 16'),
    ('thread_local alignas(16) int x=3;', 'thread data $x = align 16'),
    ('extern thread_local alignas(16) int x; thread_local alignas(16) int x=3;', 'thread data $x = align 16'),
    ('alignas(16) int a=1,b=2;', 'export data $b = align 16'),
    ('typedef int T; alignas(16) T a=1;', 'export data $a = align 16'),
    ('int f(void) { static alignas(16) int x=3; return x; }', 'align 16'),
    ('int f(void) { static thread_local alignas(16) int x=3; return x; }', 'thread data'),
    ('int x; int f(void) { alignas(sizeof x) char x,y; return sizeof y; }', 'alloc4 1'),
    ('int x; int f(void) { extern alignas(16) int x; return x; } alignas(16) int x=3;', 'data $x = align 16'),
    ('struct S { char c; alignas(16) int x,y; }; static_assert(sizeof(struct S)==48); static_assert(alignof(struct S)==16);', ''),
    ('union U { char c; _Alignas(16) int x; }; static_assert(sizeof(union U)==16); static_assert(alignof(union U)==16);', ''),
    ('struct S { char c; alignas(16) int x; }; struct T { char q; struct S a[2]; }; static_assert(sizeof(struct T)==80); static_assert(alignof(struct T)==16);', ''),
    ('struct S { alignas(16) int x; }; struct S a[2];', 'data $a = align 16'),
]
rejected = [
    ('extern alignas(8) int x; extern alignas(16) int x;', 'alignment conflicts'),
    ('alignas(16) int x=1; extern alignas(8) int x;', 'alignment conflicts'),
    ('extern alignas(16) int x; int x=1;', 'alignment conflicts'),
    ('int x=1; extern alignas(16) int x;', 'alignment conflicts'),
    ('extern alignas(16) int x; int f(void) { extern alignas(8) int x; return x; }', 'alignment conflicts'),
    ('thread_local alignas(16) int x; extern thread_local alignas(8) int x;', 'alignment conflicts'),
    ('extern alignas(2) int x;', 'weaken'),
    ('struct S; extern alignas(16) struct S x;', 'known natural alignment'),
    ('typedef int F(void); alignas(16) F f;', 'object type'),
    ('struct S { alignas(2) int x; };', 'weaken'),
    ('struct S { alignas(3) char x; };', 'supported alignments'),
    ('struct S { alignas(16) struct { int x; }; };', 'anonymous member'),
    ('struct S { int alignas(16) x; };', 'must precede'),
]
runtime = '''int aligned(void *p, int n); int check_record(void *p);
struct S { char c; alignas(16) int x; char d; };
alignas(16) int global=7;
thread_local alignas(16) int tls=9;
struct S obj;
int main(void) {
    static alignas(16) char local_static=3;
    static thread_local alignas(16) int local_tls=4;
    alignas(16) int a=1,b=2;
    struct S s; s.c=3; s.x=7; s.d=5;
    if (sizeof(struct S)!=32 || alignof(struct S)!=16 || !check_record(&s)) return 1;
    if (!aligned(&global,16) || !aligned(&tls,16) || !aligned(&local_static,16) ||
        !aligned(&local_tls,16) || !aligned(&a,16) || !aligned(&b,16) || !aligned(&obj,16)) return 2;
    if (global!=7 || tls!=9 || local_static!=3 || local_tls!=4 || a+b!=3) return 3;
    return 42;
}'''
with tempfile.TemporaryDirectory(prefix='kcc-aligned-storage-') as directory:
    d = Path(directory)
    source, il, assembly, helper, obj, exe = [d / n for n in
        ('source.c', 'source.ssa', 'source.s', 'helper.c', 'helper.o', 'program')]
    def compile_source(text):
        source.write_text(text + '\n')
        return subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    for text, expected in accepted:
        result = compile_source(text)
        assert result.returncode == 0 and not result.stderr and expected in result.stdout, (text, result.stderr, result.stdout)
    for text, expected in rejected:
        result = compile_source(text)
        assert result.returncode == 1 and not result.stdout and expected in result.stderr, (text, result.stderr)
    result = compile_source(runtime)
    assert result.returncode == 0 and not result.stderr, result.stderr
    if qbe:
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
        helper.write_text('''#include <stdint.h>
int aligned(void *p, int n) { return (uintptr_t)p % (unsigned)n == 0; }
struct S { char c; _Alignas(16) int x; char d; };
int check_record(void *p) { struct S *s=p; return sizeof(*s)==32 && s->c==3 && s->x==7 && s->d==5 && aligned(&s->x,16); }
''')
        subprocess.run([host, '-std=c11', '-c', str(helper), '-o', str(obj)], check=True, timeout=10)
        subprocess.run([host, str(assembly), str(obj), '-o', str(exe)], check=True, timeout=10)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
print('Aligned storage and record checks passed' + (' with QBE/native runtime' if qbe else ' (QBE runtime not requested)'))

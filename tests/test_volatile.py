"""Bounded runtime-backed scalar volatile access."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
qbe = os.environ.get('QBE')
with tempfile.TemporaryDirectory(prefix='kcc-volatile-') as directory:
    path = Path(directory)
    source = path / 'test.c'
    source.write_text(r'''
volatile int global=1;
volatile signed char narrow=-2;
volatile double real=1.5;
volatile int *target=&global;
volatile int array[2]={1,2};
typedef int row[2];
volatile row via_typedef;
static_assert(_Generic(&global, volatile int *: 1, default: 0));
int f(volatile int n) {
    volatile int x={1};
    volatile int empty={};
    volatile double floating={2.0};
    int * volatile ptr={};
    volatile int local_array[2]; local_array[0]=3;
    array[1]++; via_typedef[0]=local_array[0];
    (void)empty; (void)floating; (void)ptr;
    (void)(volatile int){3};
    x += n; x++;
    (void)global;
    narrow++; real += 0.5;
    *target=x;
    return global==4 && narrow==-1 && real==2.0 ? 42 : 1;
}
int main(void) { return f(2); }
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    for name in ('__kcc_volatile_load_1', '__kcc_volatile_store_1',
                 '__kcc_volatile_load_4', '__kcc_volatile_store_4',
                 '__kcc_volatile_load_8', '__kcc_volatile_store_8'):
        assert name in result.stdout, name
    if qbe:
        il, asm, exe = (path / n for n in ('test.ssa', 'test.s', 'test'))
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        subprocess.run([os.environ.get('HOST_CC', 'cc'), str(asm), str(root / 'build' / 'libkccrt.a'),
                        '-o', str(exe)], check=True)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
    for text in ('int f(void){volatile int a[2]={1}; return 0;}',
                 'int f(int n){volatile int a[n]={}; return 0;}',
                 'struct S { volatile int member; };',
                 'struct S { int x; }; typedef struct S A[2]; volatile A a;',
                 '_Atomic volatile int x;',
                 'int f(void){volatile int x=1; int *p=&x; return 0;}'):
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode != 0 and result.stderr, text
print('volatile scalar checks completed')

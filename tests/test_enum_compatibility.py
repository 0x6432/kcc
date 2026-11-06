"""C23 compatible completed tagged enums in nested scopes.

No host oracle: older C compilers do not necessarily implement C23 tag rules.
"""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
kcc = root / 'build/kcc'
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')

program = '''enum E { A=1, B=2 };
enum W { W1=2147483648L, W2=-1 };
enum F : unsigned short { F1=4, F2=5 };
enum Self { SELF_POINTER_SIZE=sizeof(enum Self *) };
enum Fixed : int { FIXED_VALUE=(enum Fixed)3 };
typedef enum E Outer;
int main(void) {
    enum E e=A; enum W w=W1; enum F f=F1;
    { enum E { B=2, A=1 }; enum E *p=&e; *p=2;
      if (!_Generic(p, Outer *: 1, default: 0)) return 1; }
    { enum W { W2=-1, W1=2147483648L }; enum W *p=&w; *p=W1; }
    { enum F : unsigned short { F2=5, F1=4 }; enum F *p=&f; *p=F1; }
    return e==2 && w==2147483648L && f==4 ? 42 : 2;
}'''
invalid = [
    'enum E { A=(enum E)0 };',
    'enum E { A=sizeof((enum E)0) };',
    'enum E { A=1 }; int f(void) { enum E x; { enum E { A=2 }; enum E *p=&x; } return 0; }',
    'enum E { A=1 }; int f(void) { enum E x; { enum E { B=1 }; enum E *p=&x; } return 0; }',
    'enum E { A=1 }; int f(void) { enum E x; { enum E { A=1, B=2 }; enum E *p=&x; } return 0; }',
    'enum E { A=1 }; int f(void) { enum E x; { enum Other { A=1 }; enum Other *p=&x; } return 0; }',
    'enum E : int { A=1 }; int f(void) { enum E x; { enum E { A=1 }; enum E *p=&x; } return 0; }',
    'enum E : int { A=1 }; int f(void) { enum E x; { enum E : long { A=1 }; enum E *p=&x; } return 0; }',
    'enum E { A=1 }; typedef enum E Outer; int f(void) { enum E { A=1 }; '
    'return _Generic((enum E *)0, Outer *: 1, enum E *: 2); }',
]
with tempfile.TemporaryDirectory(prefix='kcc-enum-compat-') as d:
    source, il, assembly, executable = [Path(d) / n for n in ('test.c', 'test.ssa', 'test.s', 'test')]
    source.write_text(program + '\n')
    result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    if qbe:
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
        subprocess.run([host, str(assembly), '-o', str(executable)], check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42
    for text in invalid:
        source.write_text(text + '\n')
        result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 1 and not result.stdout, (text, result.stderr)
print('enum compatibility checks complete' + (' with QBE runtime' if qbe else ' (QBE runtime not requested)'))

"""Fixed-enum value, layout, forward-tag and scalar ABI fixtures.

Host comparison is conditional on the host implementing C23 fixed enum syntax.
Only these defined programs are executed; this is not an exhaustive ABI oracle.
"""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
kcc = Path(os.environ.get('KCC', root / 'build/kcc'))
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')

programs = [
    'enum U : unsigned short; enum U saved; '
    'enum U : unsigned short { ZERO=0, LAST=65535, WRAP=(unsigned short)(LAST+1), OK=42 }; '
    '_Static_assert(sizeof(enum U)==2 && sizeof(OK)==2 && WRAP==0,"layout"); '
    'enum U f(enum U x) { return x; } '
    'int main(void) { saved=OK; return f(saved); }',
    'enum S : signed char { MIN=-128, NEXT, ANSWER=42 }; '
    '_Static_assert(sizeof(MIN)==1 && MIN==-128 && NEXT==-127,"constant"); '
    'enum S f(enum S x) { return x; } '
    'int main(void) { enum S x=MIN; return x==-128 && f(ANSWER)==42 ? 42 : 1; }',
    'enum W : unsigned long long { MAX=18446744073709551615ULL, WRAP=MAX+1, ANSWER=42 }; '
    '_Static_assert(sizeof(MAX)==8 && MAX>0 && WRAP==0,"wide"); '
    'enum W f(enum W x) { return x; } '
    'int main(void) { enum W x=ANSWER; return f(x)==42 ? 42 : 1; }',
    'enum T : int { OUTER=1 }; int main(void) { enum T : long; '
    'enum T : long { INNER=42 }; return sizeof(enum T)==8 && OUTER==1 ? INNER : 1; }',
    'typedef unsigned short U; enum T : U; enum T : typeof((unsigned short)0) { ANSWER=42 }; '
    'int main(void) { enum T x=ANSWER; return sizeof x==2 ? x : 1; }',
    'enum T : const int; enum T : int { ANSWER=42 }; enum T value; '
    'int main(void) { value=ANSWER; return value; }',
]

probe = subprocess.run([host, '-std=c2x', '-pedantic-errors', '-x', 'c', '-fsyntax-only', '-'],
                       input='enum E : unsigned short; enum E : unsigned short { X=1 }; _Static_assert(sizeof(X)==sizeof(enum E),"type");\n', capture_output=True,
                       text=True, timeout=10).returncode == 0

with tempfile.TemporaryDirectory(prefix='kcc-fixed-enums-') as directory:
    directory = Path(directory)
    source, il, assembly, executable = [directory / name for name in ('test.c', 'test.ssa', 'test.s', 'test')]
    for text in programs:
        source.write_text(text + '\n')
        result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=15)
        assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
            subprocess.run([host, str(assembly), '-o', str(executable)], check=True, timeout=10)
            assert subprocess.run([str(executable)], timeout=5).returncode == 42, text
        if probe:
            subprocess.run([host, '-std=c2x', '-pedantic-errors', str(source), '-o', str(executable)],
                           capture_output=True, text=True, check=True, timeout=10)
            assert subprocess.run([str(executable)], timeout=5).returncode == 42, text
print('fixed enum runtime fixtures complete' + ('' if probe else ' (host syntax unsupported)'))

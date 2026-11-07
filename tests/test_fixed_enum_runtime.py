"""Fixed-enum value, layout, forward-tag and scalar ABI fixtures.

Host comparison is conditional on the host implementing C23 fixed enum syntax.
Only these defined programs are executed; this is not an exhaustive ABI oracle.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
kcc = Path(os.environ.get('KCC', root / 'build/kcc'))
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')

programs = [
    'enum U : unsigned char; enum U { A=41, ANSWER, SIZE=sizeof(enum U) }; '
    'enum U { SIZE=1, ANSWER=42, A=41 }; '
    '_Static_assert(sizeof(ANSWER)==1 && _Generic(ANSWER,unsigned char:1,default:0),"base"); '
    'int main(void) { enum U x=ANSWER; return x; }',
    'enum B : bool; enum B { NO=0, YES }; '
    'int main(void) { enum B x=YES; return sizeof(x)==1 && x==1 ? 42 : 1; }',
    'enum T : int { OUTER=1 }; int main(void) { enum T : unsigned short; '
    'enum T { INNER=42 }; return sizeof(enum T)==2 && OUTER==1 ? INNER : 1; }',
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

# Fixed-enum syntax support does not imply support for inheriting the base
# when a later definition omits it. Probe that exact feature independently.
# A failed probe is a host capability gap, never a native runtime agreement.
inherited = False
if probe:
    result = subprocess.run([host, '-std=c2x', '-pedantic-errors', '-x', 'c', '-fsyntax-only', '-'],
                            input='enum E : int; enum E { A=1 };\n',
                            capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        assert not result.stdout and not result.stderr, (result.stdout, result.stderr)
        inherited = True
    else:
        errors = re.findall(r'(?<!fatal )error: ([^\n]+)', result.stderr)
        expected = (
            "enumeration previously declared with fixed underlying type",
            "'enum' declared with but defined without fixed underlying type",
        )
        normalized = [message.replace('‘', "'").replace('’', "'") for message in errors]
        assert (result.returncode == 1 and not result.stdout and normalized in [[value] for value in expected]
                and 'fatal error:' not in result.stderr and 'internal compiler error' not in result.stderr.lower()), (
                    'unexpected fixed-enum inheritance probe failure', result.returncode, result.stderr)

with tempfile.TemporaryDirectory(prefix='kcc-fixed-enums-') as directory:
    directory = Path(directory)
    source, il, assembly, executable = [directory / name for name in ('test.c', 'test.ssa', 'test.s', 'test')]
    host_agreements = host_gaps = 0
    for index, text in enumerate(programs):
        source.write_text(text + '\n')
        result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=15)
        assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
            subprocess.run([host, str(assembly), '-o', str(executable)], check=True, timeout=10)
            assert subprocess.run([str(executable)], timeout=5).returncode == 42, text
        if probe:
            # These originals all define a prior fixed tag without repeating
            # its underlying type. The first also exercises redefinition.
            if not inherited and index in (0, 1, 2):
                host_gaps += 1
                continue
            native = subprocess.run([host, '-std=c2x', '-pedantic-errors', str(source), '-o', str(executable)],
                                    capture_output=True, text=True, timeout=10)
            assert native.returncode == 0, (index, text, native.stdout, native.stderr)
            assert subprocess.run([str(executable)], timeout=5).returncode == 42, text
            host_agreements += 1
print(f'fixed enum runtime fixtures complete: {host_agreements} native runtime agreements; '
      f'{host_gaps if probe else len(programs)} host capability gaps (NOT agreements)')

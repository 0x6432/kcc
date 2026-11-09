"""Ordinary enum successor types during processing, including bounded BitInt."""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
kcc = root / 'build/kcc'
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')

programs = [
    '''enum Narrow { A=(unsigned _BitInt(31))2147483648U, B };
    static_assert(A==0 && B==1);
    int main(void) { return A==0 && B==1 ? 42 : 1; }''',
    '''enum Small {
        A=(unsigned _BitInt(32))7, B,
        T=_Generic(A, int: 1, default: 0),
        U=_Generic(B, int: 1, default: 0)
    };
    static_assert(T==1 && U==1 && B==8 && sizeof(B)==sizeof(int));
    int main(void) { return B==8 ? 42 : 1; }''',
    '''enum E {
        A=(unsigned _BitInt(32))2147483648U,
        B, B_TYPE=_Generic(B, unsigned int: 1, unsigned _BitInt(32): 2, default: 3),
        C=(unsigned _BitInt(32))4294967294U, D,
        D_TYPE=_Generic(D, unsigned int: 1, unsigned _BitInt(32): 2, default: 3),
        MAX=(unsigned _BitInt(32))4294967295U, NEXT,
        NEXT_TYPE=_Generic(NEXT, unsigned long: 1, default: 0)
    };
    static_assert(B_TYPE==1 && D_TYPE==1 && NEXT_TYPE==1);
    static_assert(B==2147483649UL && D==4294967295UL && NEXT==4294967296UL);
    int main(void) { enum E v=NEXT; return v==4294967296UL ? 42 : 1; }''',
    '''enum E {
        A=2147483647, B,
        T=_Generic(B, long: 1, default: 0),
        C=4294967295U, D,
        U=_Generic(D, unsigned long: 1, default: 0)
    };
    static_assert(T==1 && U==1 && B==2147483648L && D==4294967296UL);
    int main(void) { return B==2147483648L && D==4294967296UL ? 42 : 1; }''',
    '''enum E {
        A=(_BitInt(64))(-2147483649LL), B,
        T=_Generic(B, _BitInt(64): 1, default: 0),
        C=(unsigned _BitInt(64))2147483648UL, D,
        U=_Generic(D, unsigned _BitInt(64): 1, default: 0)
    };
    static_assert(T==1 && U==1 && B==-2147483648LL && D==2147483649UL);
    int main(void) { enum E x=B; return x==-2147483648LL && D==2147483649UL ? 42 : 1; }''',
    '''enum Fixed : unsigned int { FIXED=2147483648U };
    enum E {
        A=FIXED, B,
        T=_Generic(B, unsigned int: 1, default: 0)
    };
    static_assert(T==1 && B==2147483649UL);
    int main(void) { enum E x=B; return x==2147483649UL ? 42 : 1; }''',
]
invalid = [
    ('enum E { A=(unsigned _BitInt(64))18446744073709551615ULL, B };', 'range'),
    ('enum E { A=(_BitInt(64))9223372036854775807LL, B };', 'range'),
    ('enum E { A=-1, B=(unsigned _BitInt(64))9223372036854775808ULL };', 'range'),
    ('enum E : unsigned _BitInt(32) { A };', 'fixed enum underlying type'),
]
with tempfile.TemporaryDirectory(prefix='kcc-enum-successors-', dir=root / 'build') as d:
    source, il, assembly, executable = [Path(d) / name for name in ('test.c', 'test.ssa', 'test.s', 'test')]
    for text in programs:
        source.write_text(text + '\n')
        result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
            subprocess.run([host, str(assembly), '-o', str(executable)], check=True, timeout=10)
            assert subprocess.run([str(executable)], timeout=5).returncode == 42, text
    for text, message in invalid:
        source.write_text(text + '\n')
        result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)
print('ordinary enum successor type checks passed' + (' with QBE runtime' if qbe else ' (QBE not requested)'))

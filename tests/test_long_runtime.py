"""LP64 long models, mixed-rank conversions and high-only-bit truth contexts."""
import os
import random
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root/'build'/'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
mask = (1 << 64)-1


def signed_literal(value):
    return '(-9223372036854775807L-1L)' if value == -(1 << 63) else f'({value}L)'


cases = [('2147483648', 2147483648), ('4294967296U', 4294967296),
         ('-2147483648', -2147483648), ('0xffffffffffffffff', mask),
         ('0xffffffffffffffffL', mask), ('18446744073709551615UL', mask),
         ('-1L<1U', 1), ('-1<1UL', 0), ('0xffffffff>-1L', 1),
         ('2147483648>-1', 1), ('0x80000000>-1', 0),
         ('(long)0xffffffff', 4294967295), ('(long)(int)0xffffffff', -1),
         ('(unsigned long)-1', mask), ('(unsigned long)(unsigned)-1', 4294967295),
         ('(int)4294967295L', -1), ('(unsigned)0xffffffffffffffffUL', 4294967295),
         ('(long)0xffffffffffffffffUL', -1), ('(-9223372036854775807L-1L)>>63', -1),
         ('1UL<<63L', 1 << 63), ('0xffffffffffffffffUL>>63UL', 1),
         ('(1UL<<63)>>63L', 1), ('-1L/2L', 0), ('-7L%3L', -1),
         ('!4294967296L', 0), ('!0L', 1), ('(int)4294967338L', 42),
         ('1<<3L', 8), ('0xffffffffU>>31UL', 1)]
rng = random.Random(1205)
for _ in range(10):
    a, b = [rng.randrange(1 << 64) for _ in range(2)]
    count = rng.randrange(64)
    cases += [(f'{a}UL+{b}UL', (a+b)&mask), (f'{a}UL-{b}UL', (a-b)&mask),
              (f'{a}UL*{b}UL', (a*b)&mask), (f'{a}UL/{b or 1}UL', a//(b or 1)),
              (f'{a}UL%{b or 1}UL', a%(b or 1)), (f'{a}UL<<{count}', (a << count)&mask),
              (f'{a}UL>>{count}L', a >> count)]
    x, y = rng.randrange(-1000000000, 1000000000), rng.randrange(1, 1000000)
    quotient = (abs(x)//y) * (-1 if x < 0 else 1)
    cases += [(f'{signed_literal(x)}*{signed_literal(y)}', x*y),
              (f'{signed_literal(x)}/{signed_literal(y)}', quotient),
              (f'{signed_literal(x)}%{signed_literal(y)}', x-quotient*y)]
programs = [f'int main(void) {{ unsigned long value={expression}; if(value=={value & mask}UL) return 42; return 1; }}'
            for expression, value in cases]
programs += [
    'int main(void) { long x=1L<<40; if(x) return 42; return 1; }',
    'int main(void) { unsigned long x=1UL<<63; return (x&&x)+41; }',
    'int main(void) { long x=1L<<40; return (0L||x)+41; }',
    'int main(void) { int n=0; long x=1L<<40; while(x) { n=n+1; x=0; } return n+41; }',
    'int main(void) { int n=0; long x=1L<<40; do { n=n+1; if(n==2) x=0; } while(x); return n+40; }',
    'int main(void) { int n=0; for(long x=1L<<40;x;x=0) n=n+1; return n+41; }',
    'long fact(long n) { if(n<2) return 1; return n*fact(n-1); } int main(void) { if(fact(20)==2432902008176640000L) return 42; return 1; }',
    'int main(void) { unsigned long x=0; long y=-1; x=y; if(x==0xffffffffffffffffUL) return 42; return 1; }',
    'long unsigned int f(int long unsigned x) { return x; } int main(void) { return (int)f(42); }',
]
with tempfile.TemporaryDirectory(prefix='kcc LP64 runtime ') as directory:
    directory = Path(directory)
    source, il, assembly, executable = [directory/name for name in ('p.c', 'p.ssa', 'p.s', 'p')]
    for text in programs:
        source.write_text(text+'\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
            subprocess.run([host, str(assembly), '-o', str(executable)], check=True, timeout=10)
            assert subprocess.run([str(executable)], timeout=5).returncode == 42, text
        subprocess.run([host, '-std=c2x', str(source), '-o', str(executable)],
                       capture_output=True, check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, text
    rejected = [('long main(void) { return 0; }', 'main must return int'),
                ('long f(void); int f(void);', 'incompatible function'),
                ('int f(long); int f(unsigned);', 'incompatible function'),
                ('int main(void) { return 9223372036854775808; }', 'implemented integer type'),
                ('int main(void) { return 9223372036854775808L; }', 'implemented integer type'),
                ('int main(void) { return 18446744073709551616UL; }', 'exceeds 64-bit'),
                ('long long f(void);', 'long long is not supported'),
                ('int main(void) { return 42LL; }', 'unsupported numeric'),
                ('long unsigned signed f(void);', 'conflicting integer type')]
    for text, message in rejected:
        source.write_text(text+'\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, result.stderr
print(f'Long runtime passed ({len(programs)} full-width model/host programs; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

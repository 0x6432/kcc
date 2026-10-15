"""Distinct long-long rank, valid suffixes and same-width signature constraints."""
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
cases = [('0LL', 0), ('42ll', 42), ('42uLL', 42), ('42LLu', 42),
         ('0xffffffffffffffffLL', mask), ('18446744073709551615ULL', mask),
         ('-1LL<1UL', 0), ('-1LL<1U', 1), ('-1L<1ULL', 0),
         ('-1ULL', mask), ('~0ULL', mask), ('1ULL<<63LL', 1 << 63),
         ('(-9223372036854775807LL-1LL)>>63', -1), ('-7LL/3LL', -2), ('-7LL%3LL', -1),
         ('(long long)(unsigned)-1', 4294967295), ('(unsigned long long)-1', mask),
         ('(int)(long long)4294967295ULL', -1), ('0xffffffffffffffffULL>>63', 1)]
rng = random.Random(1206)
for _ in range(10):
    a, b = [rng.randrange(1 << 64) for _ in range(2)]
    count = rng.randrange(64)
    cases += [(f'{a}ULL+{b}ULL', (a+b)&mask), (f'{a}ULL-{b}ULL', (a-b)&mask),
              (f'{a}ULL*{b}ULL', (a*b)&mask), (f'{a}ULL/{b or 1}ULL', a//(b or 1)),
              (f'{a}ULL%{b or 1}ULL', a%(b or 1)), (f'{a}ULL<<{count}', (a << count)&mask),
              (f'{a}ULL>>{count}LL', a >> count)]
programs = [f'int main(void) {{ unsigned long long value={expression}; if(value=={value & mask}ULL) return 42; return 1; }}'
            for expression, value in cases]
programs += [
    'long long f(unsigned long x) { return x+1LL; } int main(void) { return (int)f(41UL); }',
    'long long signed int f(int long signed long x) { return x; } int main(void) { return f(42LL); }',
    'int main(void) { long long x=1LL<<40; int n=0; while(x) { n=n+1; x=0; } return n+41; }',
    'int main(void) { unsigned long long x=1ULL<<63; return (x||0LL)+41; }',
]
with tempfile.TemporaryDirectory(prefix='kcc long long ') as directory:
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
    rejected = [('long f(void); long long f(void);', 'incompatible function'),
                ('int f(unsigned long); int f(unsigned long long);', 'incompatible function'),
                ('long long main(void) { return 0; }', 'main must return int'),
                ('long long long f(void);', 'too many long'),
                ('unsigned long signed long f(void);', 'conflicting integer type'),
                ('int main(void) { return 9223372036854775808LL; }', 'implemented integer type'),
                ('int main(void) { return 42lL; }', 'unsupported numeric'),
                ('int main(void) { return 42LLL; }', 'unsupported numeric'),
                ('int main(void) { return 18446744073709551616ULL; }', 'exceeds 64-bit')]
    for text, message in rejected:
        source.write_text(text+'\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, result.stderr
print(f'Long long passed ({len(programs)} full-width model/host programs; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

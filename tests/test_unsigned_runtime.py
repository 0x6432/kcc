"""Int/uint conversion contexts, full-bit unsigned model and signature constraints."""
import os
import random
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root/'build'/'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
mask = (1 << 32)-1
expressions = [
    ('0xffffffff', mask), ('4294967295U', mask), ('0x80000000', 1 << 31),
    ('-1U', mask), ('~0U', mask), ('4294967295U + 1', 0), ('0U-1', mask),
    ('0xffffffff/2', 2147483647), ('0xffffffff%2', 1), ('0xffffffff>>31', 1),
    ('1U<<31', 1 << 31), ('0x80000000<<1', 0), ('-1<1U', 0), ('1U>-1', 0),
    ('-1==0xffffffff', 1), ('-1<=0U', 0), ('0xffffffff>=-1', 1), ('~0U!=0', 1),
    ('-4 >> 1U', -2 & mask), ('0xffffffff >> 1', 2147483647),
    ('!0U', 1), ('!1U', 0), ('0U || 1U', 1), ('0xffffffff && 1', 1),
]
rng = random.Random(1203)
for _ in range(12):
    a, b = [rng.randrange(1 << 32) for _ in range(2)]
    count = rng.randrange(32)
    expressions += [(f'{a}U+{b}U', (a+b)&mask), (f'{a}U-{b}U', (a-b)&mask),
                    (f'{a}U*{b}U', (a*b)&mask), (f'{a}U^{b}U', a ^ b),
                    (f'{a}U<<{count}', (a << count)&mask), (f'{a}U>>{count}U', a >> count),
                    (f'{a}U/{b or 1}U', a//(b or 1)), (f'{a}U%{b or 1}U', a%(b or 1))]
programs = [f'int main(void) {{ unsigned x={expression}; if(x=={value}U) return 42; return 1; }}'
            for expression, value in expressions]
programs += [
    'int main(void) { unsigned x=-1; int y=x; if(y==-1) return 42; return 1; }',
    'unsigned f(unsigned x) { return x+1; } int main(void) { return f(41); }',
    'int f(unsigned x) { return x; } int main(void) { if(f(0xffffffff)==-1) return 42; return 1; }',
    'unsigned f(int x) { return x; } int main(void) { if(f(-1)==0xffffffff) return 42; return 1; }',
    'int main(void) { unsigned x=0; int y=-1; x=y; if((y=x)==-1) return 42; return 1; }',
    'int main(void) { unsigned x=0; for(unsigned i=1;i<64;i=i<<1) x=x|i; return x&42; }',
    'int main(void) { unsigned x=0; 0U && (x=1); 1U || (x=2); return x+42; }',
    'unsigned f(unsigned); unsigned int f(unsigned int x) { return x; } int main(void) { return f(42); }',
    'signed f(int unsigned x) { int signed y=x; return y; } signed int main(void) { return f(42); }',
    'int main(void) { unsigned x=1; { unsigned x=42; return x; } }',
]
with tempfile.TemporaryDirectory(prefix='kcc unsigned runtime ') as directory:
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
    rejected = [
        ('unsigned main(void) { return 0; }', 'main must return int'),
        ('int f(unsigned); int f(int);', 'incompatible function declaration'),
        ('unsigned f(void); int f(void);', 'incompatible function declaration'),
        ('unsigned signed f(void);', 'conflicting integer type'),
        ('int int f(void);', 'conflicting integer type'),
        ('int main(void) { unsigned unsigned x; return 0; }', 'conflicting integer type'),
        ('int main(void) { unsigned x=missing; return 0; }', 'undeclared'),
        ('unsigned f(unsigned x) { int x; return 0; }', 'redeclaration'),
        ('int main(void) { return 1.5; }', 'unsupported numeric'),
        ('int main(void) { return 1U + '+'+ '*126+'1; }', 'typed expression exceeds depth'),
        ('int main(void) { return '+'~'*127+'1U; }', 'typed expression exceeds depth'),
    ]
    for text, message in rejected:
        source.write_text(text+'\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)
print(f'Unsigned runtime passed ({len(programs)} full-value model/host programs; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

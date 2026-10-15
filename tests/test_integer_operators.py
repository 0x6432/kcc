"""Signed 32-bit operators: independent models and defined host/QBE execution."""
import os
import random
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root/'build'/'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')


def literal(value):
    return '(-2147483647-1)' if value == -(1 << 31) else f'({value})'


def signed(value):
    value &= (1 << 32)-1
    return value-(1 << 32) if value >= 1 << 31 else value


cases = [('~0', -1), ('~(-2147483647-1)', 2147483647), ('~2147483647', -(1 << 31)),
         ('1 << 30', 1 << 30), ('0 << 31', 0), ('2147483647 >> 31', 0),
         ('(-2147483647-1) >> 31', -1), ('-7 >> 1', -4), ('32 >> 1 >> 2', 4),
         ('1 << 2 << 1', 8), ('1 << 2+1', 8), ('32 >> 1+2', 4),
         ('1 | 2 ^ 3 & 4', 3), ('2 & 3 == 3', 0), ('2 ^ 3 == 3', 3),
         ('1 | 2 && 0', 0), ('0 || 2 & 3', 1), ('4 < 1 << 3', 1),
         ('8 >> 1 == 4', 1), ('~1 * 2', -4), ('!(~0)', 0), ('~~~42', -43)]
random_source = random.Random(1201)
for _ in range(12):
    a, b = [random_source.randrange(-(1 << 31), 1 << 31) for _ in range(2)]
    count = random_source.randrange(32)
    positive = random_source.randrange((2147483647 >> count)+1)
    cases += [(f'{literal(a)} & {literal(b)}', signed(a & b)),
              (f'{literal(a)} ^ {literal(b)}', signed(a ^ b)),
              (f'{literal(a)} | {literal(b)}', signed(a | b)),
              (f'~{literal(a)}', signed(~a)),
              (f'{literal(a)} >> {count}', a >> count),
              (f'{positive} << {count}', positive << count)]
programs = [f'int main(void) {{ int value={expression}; if(value=={literal(value)}) return 42; return 1; }}'
            for expression, value in cases]
programs += [
    'int main(void) { int x=42; return x=x&63; }',
    'int main(void) { int x=0; int y=2; x=y<<4|10; return x; }',
    'int main(void) { int x=0; 0 && (x=1<<2); 1 || (x=3&7); return x+42; }',
    'int main(void) { int x=0; int v=0 & (x=1); return v+x+41; }',
    'int main(void) { int x=0; int v=1 | (x=0); return v+x+41; }',
    '#define C(a,b) a##b\nint main(void) { return 21 C(<,<) 1; }',
    'int f(int x) { return (x<<1)^2; } int main(void) { return f(20); }',
    'int main(void) { int x=0; for(int i=0;i<6;i=i+1) x=x|1<<i; return (x&42); }',
]

with tempfile.TemporaryDirectory(prefix='kcc integer operators ') as directory:
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
        subprocess.run([host, '-std=c2x', '-Wall', '-Wextra', str(source), '-o', str(executable)],
                       capture_output=True, check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, text
    for expression, message in [('~', 'integer literal'), ('1 <<', 'integer literal'),
                                ('1 >> >> 2', 'integer literal'), ('1 | | 2', 'integer literal'),
                                ('1 & missing', 'undeclared'), ('~missing', 'undeclared'),
                                ('(1&2)=3', 'modifiable lvalue')]:
        source.write_text(f'int main(void) {{ return {expression}; }}\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, result.stderr
    for expression in ('~'*128+'0', '0|'*128+'0', '(0|'*128+'0'+')'*128):
        source.write_text(f'int main(void) {{ return {expression}; }}\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and 'limit (128)' in result.stderr, result.stderr
print(f'Integer operators passed ({len(programs)} full-value host/model programs; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

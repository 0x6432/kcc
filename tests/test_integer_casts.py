"""One-token cast/group disambiguation and explicit 32-bit signedness changes."""
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
cases = [('(int)0xffffffff', -1), ('(unsigned)-1', mask), ('(int)(unsigned)-42', -42),
         ('(unsigned int)(signed int)0xffffffff', mask), ('(int)0xffffffff/2', 0),
         ('(unsigned)-1/2', 2147483647), ('(int)0xffffffff>>1', -1),
         ('(unsigned)-1>>1', 2147483647), ('(int)0xffffffff<0', 1),
         ('(unsigned)1<-1', 1), ('-(unsigned)1', mask), ('~(int)0xffffffff', 0),
         ('(int)(2U+3U)*4', 20), ('(int)1U+2', 3), ('((unsigned)1)<<31', 1 << 31),
         ('(int unsigned)(int signed)-1', mask)]
rng = random.Random(1204)
for _ in range(24):
    bits = rng.randrange(1 << 32)
    signed = bits-(1 << 32) if bits >= 1 << 31 else bits
    cases += [(f'(int){bits}U', signed), (f'(unsigned)(int){bits}U', bits)]
programs = [f'int main(void) {{ unsigned value={expression}; if(value=={value & mask}U) return 42; return 1; }}'
            for expression, value in cases]
programs += [
    'int f(void) { return 42; } int main(void) { return (int)(unsigned)f(); }',
    'unsigned f(int x) { return x; } int main(void) { return (int)(f)(42); }',
    'int f(int x) { return x; } int main(void) { return (unsigned)((f))(42); }',
    'int main(void) { int x=0; int y=(int)(unsigned)(x=42); return y+x-42; }',
    'int main(void) { unsigned x=42; return (int)(x); }',
    'int main(void) { int x=0; (x)=42; return (x); }',
    '#define T unsigned int\nint main(void) { return (int)(T)42; }',
]
with tempfile.TemporaryDirectory(prefix='kcc integer casts ') as directory:
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
    for expression, message in [('(int)', 'integer literal'), ('(unsigned 1)', "after cast type"),
                                ('(int int)1', 'conflicting integer type'),
                                ('(unsigned signed)1', 'conflicting integer type'),
                                ('(int)missing', 'undeclared'), ('(int)1=2', 'modifiable lvalue')]:
        source.write_text(f'int main(void) {{ return {expression}; }}\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, result.stderr
    # Parser and typed depth bounds include cast nodes and inserted loads.
    source.write_text('int main(void) { return '+'(int)'*127+'42; }\n')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0 and not result.stderr, result.stderr
    for text, message in [('int main(void) { return '+'(int)'*128+'0; }', 'expression nesting'),
                          ('int main(void) { int x=0; return '+'(int)'*127+'x; }', 'typed expression')]:
        source.write_text(text+'\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, result.stderr
print(f'Integer casts passed ({len(programs)} full-value model/host programs; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

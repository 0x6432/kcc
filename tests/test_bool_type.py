"""_Bool converts whole scalar values to 0/1; it never truncates first."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root/'build'/'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
types = [('char', 8, False, ''), ('signed char', 8, False, ''), ('unsigned char', 8, True, ''),
         ('short', 16, False, ''), ('unsigned short', 16, True, ''), ('int', 32, False, ''),
         ('unsigned', 32, True, 'U'), ('long', 64, False, 'L'), ('unsigned long', 64, True, 'UL'),
         ('long long', 64, False, 'LL'), ('unsigned long long', 64, True, 'ULL')]
def convert(value, width, unsigned):
    value &= (1 << width)-1
    return value if unsigned or value < (1 << (width-1)) else value-(1 << width)

checks = []
values = [0, 1, 2, 42, 127, 128, 255, 256, 32768, 65535, 65536,
          1 << 31, 1 << 32, 1 << 40, 1 << 63, (1 << 64)-1, -1, -128, -32768]
for name, width, unsigned, suffix in types:
    for value in values:
        source = convert(value, width, unsigned)
        expected = int(source != 0)
        # INT64_MIN is an expression; its positive decimal magnitude is not a
        # representable signed integer literal, even when preceded by unary -.
        spelling = (f'(-9223372036854775807{suffix}-1{suffix})'
                    if width == 64 and not unsigned and source == -(1 << 63)
                    else f'{source}{suffix}')
        checks.append(f'if((_Bool)({name}){spelling}!={expected}) return 1;')
        checks.append(f'if(({name})(_Bool)({name}){spelling}!={expected}{suffix}) return 2;')
programs = ['int main(void) {'+''.join(checks[i:i+28])+'return 42; }'
            for i in range(0, len(checks), 28)]
expressions = [('(_Bool)2+(_Bool)4', 2), ('~(_Bool)0', -1), ('-(_Bool)255', -1),
               ('+(_Bool)(1L<<40)', 1), ('(_Bool)65536<<3', 8), ('(_Bool)0>>1', 0),
               ('!(_Bool)0', 1), ('(_Bool)2==(_Bool)4', 1), ('(_Bool)0<(_Bool)-1', 1),
               ('(_Bool)(unsigned char)256', 0), ('(_Bool)(unsigned short)65536', 0),
               ('(_Bool)256', 1), ('(_Bool)(1ULL<<63)', 1)]
programs += [f'int main(void) {{ if(({text})=={value}) return 42; return 1; }}'
             for text, value in expressions]
programs += [
    'int main(void) { _Bool b=0; if((b=256)!=1 || b!=1) return 1; b=0; if(b) return 2; return 42; }',
    'int main(void) { int n=0; _Bool b=(_Bool)(n=n+2); if(n!=2 || b!=1) return 1; return 42; }',
    'int main(void) { int n=0; _Bool b=0; if((b=(n=n+2))!=1 || n!=2) return 1; return 42; }',
    '_Bool f(long x) { return x; } int main(void) { if(!f(1L<<40) || f(0)) return 1; return 42; }',
    'int f(_Bool x) { return x; } int main(void) { if(f(256)!=1 || f(0)!=0) return 1; return 42; }',
    'int main(void) { int n=0; 0 && (_Bool)(n=n+1); 1 || (_Bool)(n=n+1); return n+42; }',
    '#define FLAG _Bool\nint main(void) { FLAG b=256; return b+41; }',
    '_Bool f(_Bool); _Bool f(_Bool x) { return x; } int main(void) { return f(2)+41; }',
]
with tempfile.TemporaryDirectory(prefix='kcc bool type ') as directory:
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
        subprocess.run([host, '-std=c2x', '-fsigned-char', str(source), '-o', str(executable)],
                       capture_output=True, check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, text
    rejected = [('_Bool _Bool f(void);', 'duplicate _Bool'), ('unsigned _Bool f(void);', 'cannot combine'),
                ('_Bool int f(void);', 'cannot combine'), ('_Bool char f(void);', 'cannot combine'),
                ('_Bool short f(void);', 'cannot combine'), ('long _Bool f(void);', 'cannot combine'),
                ('_Bool f(void); unsigned char f(void);', 'incompatible function'),
                ('int f(_Bool); int f(unsigned char);', 'incompatible function'),
                ('_Bool main(void) { return 0; }', 'main must return int')]
    for text, message in rejected:
        source.write_text(text+'\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, result.stderr
    for count, valid in [(125, True), (126, False)]:
        source.write_text('int main(void) { _Bool x=1; return '+'+ '*count+'x; }\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'depth' in result.stderr, result.stderr
print(f'Bool type passed ({len(checks)} width/sign checks in {len(programs)} full-value host/model programs; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

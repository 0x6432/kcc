"""16-bit target types, independent narrowing model and integer promotions."""
import os
import random
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
values = [0, 1, 42, 127, 128, 255, 256, 32767, 32768, 65535, 65536, 65537,
          131071, (1 << 31)-1, 1 << 31, (1 << 32)-1, 1 << 32, (1 << 40)+32768,
          1 << 63, (1 << 64)-1]
for short, unsigned in [('short', False), ('unsigned short', True)]:
    for value in values:
        narrowed = convert(value, 16, unsigned)
        checks.append(f'if(({short}){value}ULL!={narrowed}) return 1;')
        for target, width, target_unsigned, suffix in types:
            expected = convert(narrowed, width, target_unsigned)
            checks.append(f'if(({target})({short}){value}ULL!={expected}{suffix}) return 2;')
    for source, width, source_unsigned, suffix in types:
        for value in (0, 127, 128, 255, 32767, 32768, 65535, 65536, -1, -32768):
            converted = convert(value, width, source_unsigned)
            expected = convert(converted, 16, unsigned)
            checks.append(f'if(({short})({source}){converted}{suffix}!={expected}) return 3;')
programs = ['int main(void) {'+''.join(checks[i:i+32])+'return 42; }'
            for i in range(0, len(checks), 32)]
expressions = [('(unsigned short)65535+1', 65536), ('~(unsigned short)0', -1),
               ('-(unsigned short)65535', -65535), ('(unsigned short)65535<<1', 131070),
               ('(short)65535>>15', -1), ('(unsigned short)65535>>15', 1),
               ('(short)65535<(unsigned short)65535', 1), ('+(short)65535', -1),
               ('(unsigned short)65535/(short)-2', -32767), ('(short)32768%3', -2),
               ('!(unsigned short)65536', 1), ('(unsigned short)65536||0', 0)]
rng = random.Random(1209)
for _ in range(12):
    a, b = rng.randrange(65536), rng.randrange(65536)
    signed = convert(a, 16, False)
    expressions += [(f'(short){a}+(unsigned short){b}', signed+b),
                    (f'(short){a}*(unsigned short){b}', signed*b)]
programs += [f'int main(void) {{ if(({text})=={value}) return 42; return 1; }}'
             for text, value in expressions]
for short, unsigned in [('short', False), ('unsigned short', True)]:
    expected = 65535 if unsigned else -1
    programs += [f'int main(void) {{ {short} a=0; if((a=65535)!={expected}) return 1; if(a!={expected}) return 2; return 42; }}',
                 f'{short} f({short} a) {{ return a+1; }} int main(void) {{ if(f(65535)!=0) return 1; return 42; }}',
                 f'int main(void) {{ {short} a=65536; if(a) return 1; a=32768; if(!a) return 2; return 42; }}']
programs += ['short signed int f(int signed short x) { return x; } int main(void) { return f(42); }',
             'short unsigned int f(int unsigned short x) { return x; } int main(void) { return f(42); }',
             '#define HALF unsigned short\nint main(void) { HALF x=65535; return (x+1==65536)+41; }',
             'int main(void) { unsigned short x=65535; for(short i=0;i<3;i=i+1) x=x+1; return x+40; }']
with tempfile.TemporaryDirectory(prefix='kcc short types ') as directory:
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
    rejected = [('short short f(void);', 'duplicate short'), ('short char f(void);', 'cannot combine'),
                ('short long f(void);', 'cannot combine'), ('unsigned short signed f(void);', 'conflicting'),
                ('short f(void); int f(void);', 'incompatible function'),
                ('int f(short); int f(unsigned short);', 'incompatible function'),
                ('short main(void) { return 0; }', 'main must return int')]
    for text, message in rejected:
        source.write_text(text+'\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, result.stderr
    for count, valid in [(125, True), (126, False)]:
        source.write_text('int main(void) { unsigned short x=42; return '+'+ '*count+'x; }\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'depth' in result.stderr, result.stderr
print(f'Short types passed ({len(checks)} width/sign checks in {len(programs)} full-value host/model programs; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

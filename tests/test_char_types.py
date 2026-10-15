"""Target byte types: canonical values, promotions and all width/sign conversions."""
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
byte_types = [('char', False), ('signed char', False), ('unsigned char', True)]
wide_types = [('int', 32, False, ''), ('unsigned', 32, True, 'U'),
              ('long', 64, False, 'L'), ('unsigned long', 64, True, 'UL'),
              ('long long', 64, False, 'LL'), ('unsigned long long', 64, True, 'ULL')]
def convert(value, bits, unsigned):
    value &= (1 << bits)-1
    return value if unsigned or value < (1 << (bits-1)) else value-(1 << bits)

checks = []
values = [0, 1, 42, 127, 128, 255, 256, 257, 511, (1 << 31)-1, 1 << 31,
          (1 << 32)-1, 1 << 32, (1 << 40)+128, 1 << 63, mask]
for name, unsigned in byte_types:
    for value in values:
        expected = convert(value, 8, unsigned)
        checks.append(f'if(({name}){value}ULL!={expected}) return 1;')
        for target, bits, target_unsigned, suffix in wide_types:
            widened = convert(expected, bits, target_unsigned)
            checks.append(f'if(({target})({name}){value}ULL!={widened}{suffix}) return 2;')
    for source, bits, source_unsigned, suffix in wide_types:
        for value in (0, 127, 128, 255, 256, -1, -128):
            converted = convert(value, bits, source_unsigned)
            expected = convert(converted, 8, unsigned)
            checks.append(f'if(({name})({source}){converted}{suffix}!={expected}) return 3;')
programs = ['int main(void) {'+''.join(checks[i:i+24])+'return 42; }'
            for i in range(0, len(checks), 24)]
expressions = [('(unsigned char)255+1', 256), ('~(unsigned char)0', -1),
               ('-(unsigned char)255', -255), ('(unsigned char)255<<1', 510),
               ('(signed char)255>>1', -1), ('(unsigned char)255>>1', 127),
               ('(signed char)255<(unsigned char)255', 1), ('+(char)255', -1),
               ('(unsigned char)255/(signed char)-2', -127), ('(char)128%3', -2),
               ('!(unsigned char)256', 1), ('(unsigned char)256||0', 0)]
rng = random.Random(1208)
for _ in range(12):
    a, b = rng.randrange(256), rng.randrange(256)
    signed = convert(a, 8, False)
    expressions += [(f'(signed char){a}+(unsigned char){b}', signed+b),
                    (f'(unsigned char){a}*(unsigned char){b}', a*b)]
programs += [f'int main(void) {{ if(({text})=={value}) return 42; return 1; }}'
             for text, value in expressions]
for name, unsigned in byte_types:
    expected = 255 if unsigned else -1
    programs += [f'int main(void) {{ {name} a=0; if((a=255)!={expected}) return 1; if(a!={expected}) return 2; return 42; }}',
                 f'{name} f({name} a) {{ return a+1; }} int main(void) {{ if(f(255)!=0) return 1; return 42; }}',
                 f'int main(void) {{ {name} a=256; if(a) return 1; a=128; if(!a) return 2; return 42; }}']
programs += ['char unsigned f(unsigned char x) { return x; } int main(void) { return f(42); }',
             'char signed f(signed char x) { return x; } int main(void) { return f(42); }',
             '#define BYTE unsigned char\nint main(void) { BYTE x=255; return (x+1==256)+41; }',
             'int main(void) { unsigned char x=255; for(char i=0;i<3;i=i+1) x=x+1; return x+40; }']
with tempfile.TemporaryDirectory(prefix='kcc char types ') as directory:
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
    rejected = [('char int f(void);', 'cannot combine'), ('long char f(void);', 'cannot combine'),
                ('char char f(void);', 'duplicate char'), ('char unsigned signed f(void);', 'conflicting'),
                ('char f(void); signed char f(void);', 'incompatible function'),
                ('int f(char); int f(signed char);', 'incompatible function'),
                ('char main(void) { return 0; }', 'main must return int')]
    for text, message in rejected:
        source.write_text(text+'\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, result.stderr
    # An lvalue load and byte promotion each count toward the typed-tree bound.
    for count, valid in [(125, True), (126, False)]:
        source.write_text('int main(void) { unsigned char x=42; return '+'+ '*count+'x; }\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid, result.stderr
        assert bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'depth' in result.stderr, result.stderr
print(f'Char types passed ({len(checks)} width/sign checks in {len(programs)} full-value host/model programs; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

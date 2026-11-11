"""Cross-scope enum compatibility must preserve width-specific base types."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
kcc = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')

with tempfile.TemporaryDirectory(prefix='kcc enum widths ') as tmp:
    d = Path(tmp)
    source, il, asm, exe = [d / name for name in ('input.c', 'output.ssa', 'output.s', 'output')]
    def compile_source(text, success):
        source.write_text(text + '\n')
        result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=15)
        assert result.returncode == (0 if success else 1), (text, result.stderr)
        if success:
            assert not result.stderr, (text, result.stderr)
        else:
            assert not result.stdout, (text, result.stderr)
        return result.stdout
    accepted = refused = 0
    for signed in (True, False):
        base = 'signed long' if signed else 'unsigned long'
        for width in range(33, 64):
            prefix = f'''struct Raw {{ {base} a:{width}; }} raw;
              typedef typeof(+raw.a) T; enum E:T {{ VALUE=42 }};
              typedef enum E Outer;'''
            text = prefix + '''int main(void) { Outer e=VALUE; {
              enum E:T { VALUE=42 }; enum E *p=&e;
              if (!_Generic(p, Outer *:1, default:0)) return 1;
              return *p; } }'''
            output = compile_source(text, True); accepted += 1
            if qbe:
                il.write_text(output)
                subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True, timeout=15)
                subprocess.run([host, str(asm), '-o', str(exe)], check=True, timeout=15)
                assert subprocess.run([str(exe)], timeout=5).returncode == 42
            for other in (width-1, width+1):
                if not 33 <= other <= 63:
                    continue
                prefix = f'''struct Raw {{ {base} a:{width}, b:{other}; }} raw;
                  typedef typeof(+raw.a) A; typedef typeof(+raw.b) B;
                  enum E:A {{ VALUE=42 }};'''
                text = prefix + '''int main(void) { enum E e=VALUE; {
                  enum E:B { VALUE=42 }; enum E *p=&e; return *p; } }'''
                compile_source(text, False); refused += 1
    # Member compatibility and function pointer compatibility must not erase width.
    for text in [
        '''struct R{unsigned long a:33,b:34;} raw; typedef typeof(+raw.a) A;
        typedef typeof(+raw.b) B; enum E:A { V=1 }; struct S{enum E e;};
        int f(void){struct S x={V}; {enum E:B{V=1}; struct S{enum E e;}; struct S y=x;} return 0;}''',
        '''struct R{unsigned long a:33,b:34;} raw; typedef typeof(+raw.a) A;
        typedef typeof(+raw.b) B; enum E:A { V=1 }; int f(enum E x){return x;}
        int g(void){{enum E:B{V=1}; int (*p)(enum E)=f;}return 0;}''',
    ]:
        compile_source(text, False); refused += 1
print(f'Fixed enum underlying widths: {accepted} compatible definitions, {refused} incompatible refusals; ' +
      ('QBE runtime passed' if qbe else 'QBE runtime not run'))

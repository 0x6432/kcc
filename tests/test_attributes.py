"""Bounded C23 maybe_unused and fallthrough subset; unknown semantics must not disappear."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))

pairs = [
    ('[[maybe_unused]] int x=42; int main(void){return x;}',
     'int x=42; int main(void){return x;}'),
    ('[[maybe_unused]] static int f(int x){return x+1;} int main(void){return f(41);}',
     'static int f(int x){return x+1;} int main(void){return f(41);}'),
    ('[[maybe_unused]] typedef int T,U; int main(void){ [[maybe_unused]] T x=40,y=2; return x+y; }',
     'typedef int T,U; int main(void){ T x=40,y=2; return x+y; }'),
    ('[[]][[maybe_unused,]] [[maybe_unused]] int x[2]; int main(void){[[maybe_unused]] int *p=x; p[0]=42; return x[0];}',
     'int x[2]; int main(void){int *p=x; p[0]=42; return x[0];}'),
    ('#define A [[maybe_unused]]\n#define N maybe_unused\nA int f(void); [[N]] int f(void){ A int x=42; return x; } int main(void){return f();}',
     'int f(void); int f(void){ int x=42; return x; } int main(void){return f();}'),
    ('int main(void){ [[maybe_unused]] auto x=42; return x; }',
     'int main(void){ auto x=42; return x; }'),
    ('[[maybe_unused]] struct S { int x; } s; int main(void){ s.x=42; return s.x; }',
     'struct S { int x; } s; int main(void){ s.x=42; return s.x; }'),
    ('int x [[maybe_unused]]; int f([[maybe_unused]] int n){return n;} int main(void){return f(x);}',
     'int x; int f(int n){return n;} int main(void){return f(x);}'),
    ('struct S { [[maybe_unused]] int a; int b [[maybe_unused]]; }; int main(void){return 0;}',
     'struct S { int a; int b; }; int main(void){return 0;}'),
    ('int f(int x){switch(x){case 0: x++; [[fallthrough]]; case 1: return x; default: return 0;}}',
     'int f(int x){switch(x){case 0: x++; ; case 1: return x; default: return 0;}}'),
    ('int f(void){for ([[maybe_unused]] int i=0; i<1; i++) {} return 0;}',
     'int f(void){for (int i=0; i<1; i++) {} return 0;}'),
]
invalid = [
    ('[[nodiscard]] int f(void);', 'unsupported or unknown attribute'),
    ('[[fallthrough]] int x;', 'fallthrough is only supported'),
    ('[[deprecated("reason")]] int x;', 'unsupported or unknown attribute'),
    ('[[vendor::unknown]] int x;', 'unsupported or unknown attribute'),
    ('[[unknown]] int x;', 'unsupported or unknown attribute'),
    ('[[maybe_unused(1)]] int x;', 'take no arguments'),
    ('[[maybe_unused] int x;', "expected ']]'"),
    ('[[maybe_unused]] struct S;', 'tag-only'),
    ('int f(void){ [[maybe_unused]] struct S; return 0; }', 'tag-only'),
    ('int f(void){ [[maybe_unused]] return 0; }', 'only on declarations'),
    ('[[maybe_unused]] static_assert(1);', 'only on declarations'),
    ('[[maybe_unused]] ;', 'only on declarations'),
    ('int f(void){[[fallthrough]]; return 0;}', 'within a switch'),
    ('int f(int x){switch(x){case 0: [[fallthrough]]; return 0;} return 1;}', 'immediately followed'),
    ('[[maybe_unused, unknown]] int x;', 'unsupported or unknown attribute'),
    ('[[maybe_unused]] [[nodiscard]] int f(void);', 'unsupported or unknown attribute'),
]
with tempfile.TemporaryDirectory(prefix='kcc-attributes-') as directory:
    path = Path(directory) / 'input.c'
    def compile(text):
        path.write_text(text)
        return subprocess.run([str(compiler), str(path)], capture_output=True, text=True)

    for attributed, plain in pairs:
        a, b = compile(attributed), compile(plain)
        assert a.returncode == b.returncode == 0, (attributed, a.stderr, b.stderr)
        assert not a.stderr and not b.stderr, (a.stderr, b.stderr)
        assert a.stdout == b.stdout, attributed
    for source, message in invalid:
        result = compile(source)
        assert result.returncode != 0 and 'error:' in result.stderr, (source, result)
        assert not result.stdout, (source, result.stdout)
        if message:
            assert message in result.stderr, (source, result.stderr)
    for count, success in [(256, True), (257, False)]:
        result = compile('[[]]' * count + ' int x;')
        assert (result.returncode == 0) == success, (count, result.stderr)
        if not success:
            assert 'attribute limit exceeded' in result.stderr
    for count, success in [(255, True), (256, False)]:
        result = compile('[[' + ','.join(['maybe_unused'] * count) + ']] int x;')
        assert (result.returncode == 0) == success, (count, result.stderr)
        if not success:
            assert 'attribute limit exceeded' in result.stderr
print(f'Attribute subset passed: {len(pairs)} IL-equivalence and {len(invalid)} rejection cases, plus limits')

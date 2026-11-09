"""Bounded known and ignored unknown C23 attributes."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))

pairs = [
    ('struct [[maybe_unused, vendor::hint(1)]] S { int x; } s;',
     'struct S { int x; } s;'),
    ('union [[__nodiscard__("check"), __deprecated__]] U { long x; double y; } u;',
     'union U { long x; double y; } u;'),
    ('struct [[nodiscard]] { int x; } s;', 'struct { int x; } s;'),
    ('enum [[__nodiscard__, __deprecated__]] E { A [[__maybe_unused__]]=42 } x=A;',
     'enum [[nodiscard, deprecated]] E { A [[maybe_unused]]=42 } x=A;'),
    ('void stop(void) [[__noreturn__]];', 'void stop(void) [[noreturn]];'),
    ('int f(int x){switch(x){case 0: x++; [[__fallthrough__]]; case 1: return x;} return 0;}',
     'int f(int x){switch(x){case 0: x++; [[fallthrough]]; case 1: return x;} return 0;}'),
    ('enum [[maybe_unused]] E { A [[maybe_unused]]=40, B [[deprecated("old")]]=2 }; int f(void){return A+2;}',
     'enum E { A=40, B=2 }; int f(void){return A+2;}'),
    ('enum [[vendor::hint(1, [2])]] : unsigned short { A [[unknown]]=42 }; int f(void){return A;}',
     'enum : unsigned short { A=42 }; int f(void){return A;}'),
    ('enum [[deprecated]] E { A=1 }; int f(void){return A;}',
     'enum E { A=1 }; int f(void){return A;}'),
    ('enum [[nodiscard("check result")]] E { A=1 }; enum E x;',
     'enum E { A=1 }; enum E x;'),
    ('typedef int F(void); [[nodiscard]] F f;', 'typedef int F(void); F f;'),
    ('typedef int F(void); F f [[nodiscard]];', 'typedef int F(void); F f;'),
    ('typedef int F(void); void g(void){[[nodiscard]] F f; (void)f();}', 'typedef int F(void); void g(void){F f; (void)f();}'),
    ('[[nodiscard]] int f(void){return 42;}', 'int f(void){return 42;}'),
    ('[[nodiscard("use " "result")]] int f(void);', 'int f(void);'),
    ('int f(void) [[nodiscard]];', 'int f(void);'),
    ('int f(void){[[nodiscard]] int g(void); return g();}', 'int f(void){int g(void); return g();}'),
    ('int f(void){int g(void) [[nodiscard]]; return g();}', 'int f(void){int g(void); return g();}'),
    ('void stop(void) [[noreturn]]; void other(void);',
     '_Noreturn void stop(void); void other(void);'),
    ('void f(void){void stop(void) [[noreturn]]; stop();}',
     'void f(void){_Noreturn void stop(void); stop();}'),
    ('void f(void){[[noreturn]] void stop(void); stop();}',
     'void f(void){_Noreturn void stop(void); stop();}'),
    ('typedef void F(void); void f(void){[[noreturn]] F stop; stop();}',
     'typedef void F(void); void f(void){_Noreturn F stop; stop();}'),
    ('[[noreturn]] void stop(void); int f(void){stop(); return 1;}',
     '_Noreturn void stop(void); int f(void){stop(); return 1;}'),
    ('typedef void F(void); [[noreturn]] F stop;',
     'typedef void F(void); _Noreturn F stop;'),
    ('int old(int x){return x;} int f([[deprecated]] int y){return old(y);}',
     'int old(int x){return x;} int f(int y){return old(y);}'),
    ('int f(int x){ [[vendor::trace]] if(x) [[ignored(2)]] return 1; [[unknown]] return 0; }',
     'int f(int x){ if(x) return 1; return 0; }'),
    ('[[vendor::unknown(1, {2, [3]}), unknown, maybe_unused]] int x=42; int main(void){return x;}',
     'int x=42; int main(void){return x;}'),
    ('[[unknown]] [[vendor::nodiscard("message")]] int x;', 'int x;'),
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
    ('struct [[nodiscard]] S;', 'require a record definition'),
    ('union [[maybe_unused]] U;', 'require a record definition'),
    ('struct [[fallthrough]] S { int x; };', 'not permitted on records'),
    ('union [[noreturn]] U { int x; };', 'not permitted on records'),
    ('struct [[gnu::packed]] S { int x; };', 'layout-altering GNU attribute'),
    ('[[__unsequenced__]] int f(void);', 'unsupported standard attribute'),
    ('[[__reproducible__]] int f(void);', 'unsupported standard attribute'),
    ('[[__maybe_unused__(1)]] int x;', 'take no arguments'),
    ('enum [[maybe_unused]] E;', 'require an enumeration definition'),
    ('enum E { A [[fallthrough]] };', 'fallthrough is only supported'),
    ('enum E { A [[maybe_unused(1)]] };', 'take no arguments'),
    ('enum [[nodiscard]] E;', 'require an enumeration definition'),
    ('enum E { A [[nodiscard]] };', 'nodiscard is only supported'),
    ('enum E { A [[noreturn]] };', 'noreturn attribute is only supported'),
    ('[[noreturn]] int x;', 'requires a function declaration'),
    ('[[noreturn]] typedef void F(void);', 'requires a function identifier'),
    ('[[noreturn]] enum E { X };', 'requires a direct function declaration'),
    ('[[noreturn(1)]] void f(void);', 'take no arguments'),
    ('int x [[noreturn]];', 'requires a function declaration'),
    ('void (*p)(void) [[noreturn]];', 'requires a function declaration'),
    ('typedef int F [[noreturn]];', 'only supported on function identifier declarations'),
    ('void f(void){ [[noreturn]] int x; }', 'requires a function declaration'),
    ('void f(void){ [[noreturn]] typedef int T; }', 'requires a function identifier'),
    ('void f(void){ [[noreturn]] return; }', 'requires a function identifier'),
    ('[[unsequenced]] int f(void);', 'unsupported standard attribute'),
    ('[[nodiscard]] int x;', 'nodiscard requires a function declaration'),
    ('int x [[nodiscard]];', 'nodiscard requires a function declaration'),
    ('[[nodiscard(1)]] int f(void);', 'ordinary string literal argument'),
    ('[[nodiscard(u"wide")]] int f(void);', 'ordinary string literal argument'),
    ('typedef int T; [[nodiscard]] T x;', 'nodiscard requires a function declaration'),
    ('void f(void){ [[nodiscard]] return; }', 'function identifier declarations'),
    ('typedef int T; void f(void){ [[nodiscard]] T: return; }', 'function identifier declarations'),
    ('typedef int T; void f(void){ [[noreturn]] T: return; }', 'requires a function identifier'),
    ('[[fallthrough]] int x;', 'fallthrough is only supported'),
    ('[[maybe_unused(1)]] int x;', 'take no arguments'),
    ('[[deprecated(1)]] int x;', 'ordinary string literal argument'),
    ('[[deprecated(u"wide")]] int x;', 'ordinary string literal argument'),
    ('int f(void){ [[deprecated]] return 0; }', 'only on declarations'),
    ('[[maybe_unused] int x;', "expected ']]'"),
    ('[[maybe_unused]] struct S;', 'tag-only'),
    ('int f(void){ [[maybe_unused]] struct S; return 0; }', 'tag-only'),
    ('int f(void){ [[maybe_unused]] return 0; }', 'only on declarations'),
    ('[[maybe_unused]] static_assert(1);', 'only on declarations'),
    ('[[maybe_unused]] ;', 'only on declarations'),
    ('int f(void){[[fallthrough]]; return 0;}', 'within a switch'),
    ('int f(int x){switch(x){case 0: [[fallthrough]]; return 0;} return 1;}', 'immediately followed'),
    ('[[maybe_unused]] [[unsequenced]] int f(void);', 'unsupported standard attribute'),
    ('[[unknown([)])]] int x;', 'mismatched attribute argument delimiter'),
    ('[[vendor::]] int x;', 'expected scoped attribute identifier'),
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
    result = compile('[[nodiscard]] int f(void); int g(void){f(); (void)f(); return f();}')
    assert result.returncode == 0, result.stderr
    assert result.stderr.count('warning: discarded result of nodiscard function') == 1, result.stderr
    result = compile('int f(void); int g(void){[[nodiscard]] int f(void); f(); return 0;} int h(void){f(); return 0;}')
    assert result.returncode == 0, result.stderr
    assert result.stderr.count('warning: discarded result of nodiscard function') == 1, result.stderr
    result = compile('enum [[nodiscard]] E { A=1 }; enum E f(void); '
                     'void g(enum E (*p)(void)){ f(); p(); (void)f(); }')
    assert result.returncode == 0, result.stderr
    assert result.stderr.count('warning: discarded result of function returning nodiscard enum') == 2, result.stderr
    result = compile('enum E : int; enum E f(void); enum [[nodiscard]] E : int { A=1 }; '
                     'void g(void){ f(); (void)f(); }')
    assert result.returncode == 0, result.stderr
    assert result.stderr.count('warning: discarded result of function returning nodiscard enum') == 1, result.stderr
    for source, direct, enum_count in [
        ('[[nodiscard]] int f(void); int g(void){return (f(), 1);}', 1, 0),
        ('[[nodiscard]] int f(void); void g(void){(f(), f()), f();}', 3, 0),
        ('[[nodiscard]] int f(void); void g(void){(void)f(), (void)f();}', 0, 0),
        ('[[nodiscard]] int f(void); int g(void){return sizeof((f(), 1));}', 0, 0),
        ('enum [[nodiscard]] E { A }; enum E f(void); int g(void){return (f(), 1);}', 0, 1),
    ]:
        result = compile(source)
        assert result.returncode == 0, result.stderr
        assert result.stderr.count('warning: discarded result of nodiscard function') == direct, result.stderr
        assert result.stderr.count('warning: discarded result of function returning nodiscard enum') == enum_count, result.stderr
    for source, count in [
        ('enum E { A [[deprecated("old")]]=1, B=A }; int f(void){return A+B;}', 2),
        ('enum E : unsigned long { A [[__deprecated__]]=1 }; unsigned long f(void){return A;}', 1),
        ('enum E { A=1 }; int f(void){return A;} enum E { A [[deprecated]]=1 }; int g(void){return A;}', 1),
        ('enum E { A [[deprecated]]=1 }; int f(void){int A=2; return A;}', 0),
    ]:
        result = compile(source)
        assert result.returncode == 0, result.stderr
        assert result.stderr.count('warning: use of deprecated enumerator') == count, result.stderr
    for source, count in [
        ('enum [[deprecated("old")]] E { A=1 }; enum E x; int f(void){return sizeof(enum E);}', 2),
        ('enum E : int; enum E x; enum [[__deprecated__]] E : int { A=1 }; enum E y;', 1),
        ('enum E { A=1 }; enum [[deprecated]] E { A=1 }; enum E x;', 1),
        ('enum [[deprecated]] E { A=1 }; int f(void){enum E { B=2 }; enum E x=B; return x;}', 0),
        ('enum [[deprecated]] E : int { A=1 }; enum E : int; int f(void){return A;}', 0),
    ]:
        result = compile(source)
        assert result.returncode == 0, result.stderr
        assert result.stderr.count('warning: use of deprecated enum type') == count, result.stderr
    for source, count in [
        ('[[deprecated("old")]] int x; int f(void){return x+x;}', 2),
        ('int x [[__deprecated__]]; int f(void){return x;}', 1),
        ('[[deprecated]] int f(void); int g(void){return f();}', 1),
        ('int f(void) [[deprecated]]; int g(void){return f();}', 1),
        ('typedef int F(void); [[deprecated]] F f; int g(void){return f();}', 1),
        ('int x; int a(void){return x;} int x [[deprecated]]; int b(void){return x;}', 1),
        ('int f(void){[[deprecated]] int x=1; return x;}', 1),
        ('int f(void){int x [[deprecated]]=1; return x;}', 1),
        ('[[deprecated]] int x; int f(void){int x=1; return x;} int g(void){return x;}', 1),
        ('int x; int f(void){[[deprecated]] extern int x; return x;} int g(void){return x;}', 1),
        ('int f(void){[[deprecated]] extern int x; extern int x; return x;}', 1),
        ('int f(void){for([[deprecated]] int x=0;x<1;x++){} return 0;}', 2),
        ('int f(void){[[deprecated]] static int x; return x;}', 1),
    ]:
        result = compile(source)
        assert result.returncode == 0, (source, result.stderr)
        assert result.stderr.count('warning: use of deprecated declaration') == count, (source, result.stderr)
    for source, count in [
        ('struct [[nodiscard]] S {int x;}; struct S f(void); '
         'void g(struct S (*p)(void)){f(); p(); (void)f();}', 2),
        ('union [[__nodiscard__("use")]] U {int x;}; union U f(void); '
         'void g(void){f(),f();}', 2),
        ('struct S; struct S f(void); struct [[nodiscard]] S {int x;}; '
         'void g(void){f(); (void)f();}', 1),
        ('typedef struct [[nodiscard]] {int x;} S; S f(void); '
         'void g(void){f();}', 1),
        ('struct [[nodiscard]] S {int x;}; struct S *f(void); '
         'void g(void){f();}', 0),
        ('struct [[nodiscard]] S {int x;}; struct S f(void); '
         'int g(void){return sizeof((f(),1));}', 0),
    ]:
        result = compile(source)
        assert result.returncode == 0, result.stderr
        assert result.stderr.count('warning: discarded result of function returning nodiscard record') == count, result.stderr
    for source, count in [
        ('struct [[deprecated("old")]] S {int x;}; struct S x; '
         'int f(void){return sizeof(struct S);}', 2),
        ('struct S; struct [[__deprecated__]] S {int x;}; struct S x;', 1),
        ('union [[deprecated]] U {long x;}; typedef union U T; T v;', 1),
        ('struct [[deprecated]] S {int x;}; int f(void){'
         'struct S {int y;}; struct S x={2}; return x.y;}', 0),
        ('struct [[deprecated]] S {int x;}; struct S; int f(void){return 0;}', 0),
    ]:
        result = compile(source)
        assert result.returncode == 0, result.stderr
        assert result.stderr.count('warning: use of deprecated record type') == count, result.stderr
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

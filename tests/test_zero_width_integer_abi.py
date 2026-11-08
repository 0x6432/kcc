"""Bounded integer-only zero-width barriers in the register aggregate ABI."""
from pathlib import Path
import subprocess
import tempfile
from test_bit_fields import ROOT, HOST, KCC, object_file, run
from test_zero_width_memory_abi import pair


def matrix(d):
    barriers = ('unsigned', 'unsigned char', 'unsigned short', 'unsigned long', '_Bool', 'enum E')
    prefixes = ('unsigned', 'unsigned char', 'unsigned short', 'unsigned long')
    for before in prefixes:
        for width in range(1, 8):
            declarations, definitions, checks = ['enum E { V=1 };'], [], []
            for j, barrier in enumerate(barriers):
                for n in (0, 1, 3):
                    name = f'S{j}_{n}'
                    pad = f'char pad[{n}];' if n else ''
                    declarations += [f'struct {name} {{ {before} p:{width}; {barrier} :0; unsigned char q:5; {pad} char end; }};',
                                     f'struct {name} f{name}(struct {name}); int size{name}(void); int offset{name}(void);']
                    definitions += [f'struct {name} f{name}(struct {name} x){{x.q=7;x.end++;return x;}}',
                                    f'int size{name}(void){{return sizeof(struct {name});}}',
                                    f'int offset{name}(void){{struct {name} s;return (char*)&s.end-(char*)&s;}}']
                    checks += [f'struct {name} a{name}={{0}}; a{name}.p={(1<<width)-1}; a{name}.q=17; a{name}.end=7;',
                               f'struct {name} b{name}=f{name}(a{name});',
                               f'if(sizeof(a{name})>16||size{name}()!=sizeof(a{name})||offset{name}()!=(char*)&a{name}.end-(char*)&a{name}||b{name}.p!={(1<<width)-1}||b{name}.q!=7||b{name}.end!=8||a{name}.q!=17) return 1;']
            text = '\n'.join(declarations) + '\n'
            (d/'owner.c').write_text(text + '\n'.join(definitions) + '\n')
            (d/'companion.c').write_text(text + 'int main(void){\n' + '\n'.join(checks) + '\nreturn 0;}\n')
            for options in ((), ('--legacy-clang-abi',)):
                for a, b in (('host', 'kcc'), ('kcc', 'host')):
                    object_file(d/'owner.c', d/'owner.o', a, options)
                    object_file(d/'companion.c', d/'companion.o', b, options)
                    run([HOST, d/'owner.o', d/'companion.o', '-o', d/'test'])
                    run([d/'test'])


def main():
    (ROOT/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='zero-integer-abi-', dir=ROOT/'build') as tmp:
        d = Path(tmp)
        matrix(d)
        declarations = '''#include <stdarg.h>
struct S { char a[7]; unsigned long :0; int b; };
struct Inner { int x; unsigned :0; }; struct Nested { struct Inner a[2]; };
union U { struct S s; long words[2]; };
struct P { float *p; unsigned :0; int x; };
'''
        definitions = '''struct S f(struct S x){x.a[0]++;x.b++;return x;}
long pressure(long a,long b,long c,long d,long e,struct S s,long z) {return a+b+c+d+e+s.a[0]+s.b+z;}
long exhausted(long a,long b,long c,long d,long e,long f0,struct S s,long z) {return a+b+c+d+e+f0+s.a[0]+s.b+z;}
long variadic(struct S s,...) {va_list a;va_start(a,s);long x=va_arg(a,long);double y=va_arg(a,double);va_end(a);return s.a[0]+s.b+x+(int)y;}
struct Nested nested(struct Nested s){s.a[0].x++;s.a[1].x+=2;return s;}
union U uni(union U s){s.s.a[0]++;s.s.b++;return s;}
struct P ptr(struct P s){s.x++;return s;}
'''
        caller = '''struct S f(struct S); long pressure(long,long,long,long,long,struct S,long); long exhausted(long,long,long,long,long,long,struct S,long); long variadic(struct S,...);
struct Nested nested(struct Nested); union U uni(union U); struct P ptr(struct P);
int main(void){struct S s={{0},7};s.a[0]=3; struct S r=f(s);
if(sizeof(s)!=12 || r.a[0]!=4 || r.b!=8 || s.b!=7) return 1;
if(pressure(1,1,1,1,1,s,5)!=20) return 2;
if(exhausted(1,1,1,1,1,1,s,5)!=21) return 3;
if(variadic(s,5L,6.)!=21) return 4;
struct Nested n={{{1},{2}}}; struct Nested m=nested(n); if(m.a[0].x!=2 || m.a[1].x!=4 || n.a[1].x!=2) return 5;
union U u={0};u.s.a[0]=3;u.s.b=7;union U v=uni(u); if(v.s.a[0]!=4 || v.s.b!=8 || u.s.b!=7) return 6;
float a=1.; struct P p={&a,2};struct P q=ptr(p);if(q.p!=&a || q.x!=3 || p.x!=2) return 7;
return 0;}
'''
        pair(d, declarations, definitions, caller)
        # Retain the exact original negative fixtures, now positive in both modes.
        originals = [
            'struct S { unsigned :0; int x; }; struct S f(struct S x){return x;}',
            'struct Inner { int x; unsigned :0; }; struct S { struct Inner i; }; struct S f(struct S x){return x;}',
            'struct S { short :0; int x; }; struct S f(struct S x){return x;}',
            'struct S { long :0; int x; }; struct S f(struct S x){return x;}',
            'struct S { _Bool :0; int x; }; struct S f(struct S x){return x;}',
            'enum E { A }; struct S { enum E :0; int x; }; struct S f(struct S x){return x;}',
            'struct S { char :0; int x; }; struct S f(struct S x){return x;}',
            'struct S { char a[12]; unsigned :0; int x; }; struct S f(struct S x){return x;}',
            'struct A { int x; unsigned :0; }; struct A f(struct A a) { return a; }\n',
        ]
        for source in originals:
            (d/'source.c').write_text(source)
            for options in ((), ('--legacy-clang-abi',)):
                result = subprocess.run([str(KCC), *options, str(d/'source.c')], capture_output=True, text=True, timeout=15)
                assert result.returncode == 0, (source, options, result.stderr)
        # Mixed floating and barrier records and bit-precise members stay unsupported.
        rejects = [
            'struct S { float a; unsigned :0; float b; }; struct S f(struct S x){return x;}',
            'struct I {float a; unsigned :0; float b;}; struct S { struct I a; }; struct S f(struct S x){return x;}',
            'union S { struct { int x; unsigned :0; } a; float b; }; union S f(union S x){return x;}',
            'struct I {float a; unsigned :0; float b;}; struct S { struct I a[1]; }; struct S f(struct S x){return x;}',
            'struct S { _BitInt(8) x; unsigned :0; char a[24]; }; struct S f(struct S x){return x;}',
        ]
        for source in rejects:
            (d/'source.c').write_text(source)
            options_to_reject = ((), ('--legacy-clang-abi',)) if '_BitInt' in source else ((),)
            for options in options_to_reject:
                result = subprocess.run([str(KCC), *options, str(d/'source.c')], capture_output=True, text=True, timeout=15)
                assert result.returncode == 1 and not result.stdout and 'aggregate ABI unsupported' in result.stderr, (source, options, result.stderr)
            if '_BitInt' not in source:
                result = subprocess.run([str(KCC), '--legacy-clang-abi', str(d/'source.c')], capture_output=True, text=True, timeout=15)
                assert result.returncode == 0, (source, result.stderr)
        # Pointers do not recursively contain their referents by value.
        (d/'source.c').write_text('struct S { _BitInt(8) *p; unsigned :0; int x; }; struct S f(struct S x){return x;}')
        for options in ((), ('--legacy-clang-abi',)):
            result = subprocess.run([str(KCC), *options, str(d/'source.c')], capture_output=True, text=True, timeout=15)
            assert result.returncode == 0, (options, result.stderr)
        # Older Clang classification yields a NO_CLASS first eightbyte, which QBE cannot represent.
        source = 'struct S { unsigned long :0; unsigned long :64; int x; }; struct S f(struct S x){return x;}'
        (d/'source.c').write_text(source)
        assert subprocess.run([str(KCC), str(d/'source.c')], capture_output=True, text=True, timeout=15).returncode == 0
        result = subprocess.run([str(KCC), '--legacy-clang-abi', str(d/'source.c')], capture_output=True, text=True, timeout=15)
        assert result.returncode == 1 and not result.stdout and 'aggregate ABI unsupported' in result.stderr, result.stderr
    print('zero-width integer ABI: 504 layouts in both directions/modes; pressure, variadic, nested, union, pointer and boundary checks passed')


if __name__ == '__main__':
    main()

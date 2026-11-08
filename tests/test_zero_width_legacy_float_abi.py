"""Legacy Clang-mode floating records with zero-width separators."""
from pathlib import Path
import random
import subprocess
import tempfile
from test_bit_fields import ROOT, HOST, KCC, legacy_clang_options, object_file, run


def align(n, a):
    return (n + a - 1) // a * a


def pair(d, declarations, definitions, caller, compare_host, options):
    (d/'owner.c').write_text(declarations + '\n' + definitions + '\n')
    (d/'companion.c').write_text(declarations + '\n' + caller + '\n')
    pairs = [('kcc', 'kcc')]
    if compare_host:
        pairs += [('host', 'host'), ('host', 'kcc'), ('kcc', 'host')]
    for a, b in pairs:
        object_file(d/'owner.c', d/'owner.o', a, options)
        object_file(d/'companion.c', d/'companion.o', b, options)
        run([HOST, d/'owner.o', d/'companion.o', '-o', d/'test'])
        try:
            run([d/'test'])
        except AssertionError as e:
            raise AssertionError((a, b, declarations, e)) from e


def run_suite(options, compare_host):
    (ROOT/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='legacy-float-barriers-', dir=ROOT/'build') as tmp:
        d = Path(tmp)
        barriers = (('unsigned char', 1), ('unsigned short', 2), ('unsigned', 4),
                    ('unsigned long', 8), ('_Bool', 1), ('enum E', 4))
        sizes = {'float': 4, 'double': 8, 'int': 4}
        cases = []
        for first in ('float', 'double'):
            for last in ('float', 'double', 'int'):
                for barrier, barrier_align in barriers:
                    for n in (0, 1, 3, 4, 7, 8):
                        a_offset = align(n, sizes[first])
                        b_offset = align(align(a_offset + sizes[first], barrier_align), sizes[last])
                        size = align(b_offset + sizes[last], max(sizes[first], sizes[last]))
                        pad = f'char pre[{n}];' if n else ''
                        cases.append((first, last, barrier, pad, size, a_offset, b_offset))
        assert len(cases) == 216
        for start in range(0, len(cases), 20):
            decls, bodies, checks = ['enum E { V=1 };'], [], []
            for i, (first, last, barrier, pad, size, a_offset, b_offset) in enumerate(cases[start:start+20]):
                decls += [f'struct S{i} {{ {pad} {first} x; {barrier} :0; {last} y; }};',
                          f'struct S{i} f{i}(struct S{i});']
                bodies.append(f'struct S{i} f{i}(struct S{i} s){{s.x+=2;s.y+=3;return s;}}')
                checks += [f'struct S{i} x{i}={{0}};x{i}.x=1;x{i}.y=2;',
                           f'if(sizeof(x{i})!={size}||(char*)&x{i}.x-(char*)&x{i}!={a_offset}||'
                           f'(char*)&x{i}.y-(char*)&x{i}!={b_offset}) return 1;',
                           f'struct S{i} r{i}=f{i}(x{i});if(r{i}.x!=3||r{i}.y!=5||x{i}.x!=1||x{i}.y!=2) return 2;']
            pair(d, '\n'.join(decls), '\n'.join(bodies),
                 'int main(void){\n' + '\n'.join(checks) + '\nreturn 0;}', compare_host, options)
        # Unnamed nonzero fields must use the same legacy classification rule.
        cases = [(typ, width) for typ, limit in (('unsigned char', 8), ('unsigned short', 16),
                 ('unsigned', 32), ('unsigned long', 63)) for width in range(1, limit+1)]
        for start in range(0, len(cases), 20):
            decls, bodies, checks = [], [], []
            for i, (typ, width) in enumerate(cases[start:start+20]):
                decls += [f'struct B{i} {{ float a; unsigned :0; {typ} :{width}; float b; }};',
                          f'struct B{i} f{i}(struct B{i});']
                bodies.append(f'struct B{i} f{i}(struct B{i} s){{s.a+=2;s.b+=3;return s;}}')
                checks += [f'struct B{i} x{i}={{0}};x{i}.a=1;x{i}.b=2;struct B{i} r{i}=f{i}(x{i});',
                           f'if(r{i}.a!=3||r{i}.b!=5||x{i}.a!=1||x{i}.b!=2) return 3;']
            pair(d, '\n'.join(decls), '\n'.join(bodies),
                 'int main(void){\n' + '\n'.join(checks) + '\nreturn 0;}', compare_host, options)
        # Deterministic nested records, arrays, and unions exercise effective offsets.
        nested = []
        for named in (False, True):
            rng = random.Random(7712)
            for _ in range(240):
                barrier = rng.choice(('unsigned', 'unsigned char', 'unsigned short',
                                      'unsigned long', '_Bool', 'enum E'))
                width = rng.choice((1, 3, 7, 15, 31) if named else (0, 1, 3, 7, 15, 31))
                prefix = rng.choice((0, 1, 3, 4, 7, 8))
                container = rng.choice(('record', 'array', 'union'))
                nested.append((barrier, width, prefix, container, named))
        assert len(nested) == 480
        for start in range(0, len(nested), 12):
            decls, bodies, checks = ['enum E { V=1 };'], [], []
            for i, (barrier, width, prefix, container, named) in enumerate(nested[start:start+12]):
                extra = f'unsigned {"named" if named else ""}:{width};' if width else ''
                pad = f'char pad[{prefix}];' if prefix else ''
                decls.append(f'struct I{i} {{ float x; {barrier} :0; {extra} float y; }};')
                if container == 'record':
                    member, x, y = f'struct I{i} v;', 'v.x', 'v.y'
                elif container == 'array':
                    member, x, y = f'struct I{i} v[2];', 'v[0].x', 'v[1].y'
                else:
                    decls.append(f'union U{i} {{ struct I{i} v; long alternative[2]; }};')
                    member, x, y = f'union U{i} u;', 'u.v.x', 'u.v.y'
                decls += [f'struct S{i} {{ {pad} {member} }};',
                          f'struct S{i} f{i}(struct S{i});']
                bodies.append(f'struct S{i} f{i}(struct S{i} s){{return s;}}')
                init_named = f's{i}.{x[:-1]}named=1;' if named else ''
                check_named = f'||r{i}.{x[:-1]}named!=1' if named else ''
                checks += [f'struct S{i} s{i}={{0}};s{i}.{x}=1;s{i}.{y}=2;{init_named}',
                           f'struct S{i} r{i}=f{i}(s{i});'
                           f'if(r{i}.{x}!=1||r{i}.{y}!=2{check_named}) return 4;']
            pair(d, '\n'.join(decls), '\n'.join(bodies),
                 'int main(void){\n' + '\n'.join(checks) + '\nreturn 0;}', compare_host, options)
        decls = '''#include <stdarg.h>
struct S {float a; unsigned :0; float b;};
struct I {unsigned :0; float b;}; struct N {float a; struct I i;};
struct J {float a; unsigned :0; float b;}; struct A {struct J a[2];};
union U {struct {float a; unsigned :0; float b;} s; long x;};
'''
        bodies = '''struct S f(struct S s){s.a+=2;s.b+=3;return s;}
struct N nest(struct N s){s.a+=2;s.i.b+=3;return s;}
struct A array(struct A s){s.a[0].a+=2;s.a[1].b+=3;return s;}
union U uni(union U u){u.s.a+=2;u.s.b+=3;return u;}
struct S pressure(double a,double b,double c,double d,double e,double f0,double g,struct S s,int z){s.a+=z;s.b+=a+b+c+d+e+f0+g;return s;}
int var(struct S s,...){va_list a;va_start(a,s);int x=va_arg(a,int);double y=va_arg(a,double);va_end(a);return (int)(s.a+s.b)+x+(int)y;}
'''
        caller = '''struct S f(struct S); struct N nest(struct N); struct A array(struct A); union U uni(union U);
struct S pressure(double,double,double,double,double,double,double,struct S,int); int var(struct S,...);
int main(void){struct S s={1,2};struct S r=f(s);if(r.a!=3||r.b!=5) return 1;
struct N n={1,{2}};struct N m=nest(n);if(m.a!=3||m.i.b!=5) return 2;
struct A a={{{1,2},{3,4}}};struct A b=array(a);if(b.a[0].a!=3||b.a[1].b!=7) return 3;
union U u={0};u.s.a=1;u.s.b=2;union U v=uni(u);if(v.s.a!=3||v.s.b!=5) return 4;
struct S q=pressure(1,1,1,1,1,1,1,s,3);if(q.a!=4||q.b!=9||var(s,3,4.)!=10) return 5;return 0;}
'''
        pair(d, decls, bodies, caller, compare_host, options)
        if options == ('--legacy-clang-abi',):
            source = 'struct S { float a; unsigned :0; unsigned long :64; }; struct S f(struct S s){return s;}\n'
            (d/'source.c').write_text(source)
            result = subprocess.run([str(KCC), *options, str(d/'source.c')], capture_output=True, text=True, timeout=15)
            assert result.returncode == 1 and not result.stdout and 'aggregate ABI unsupported' in result.stderr, result.stderr


def main():
    compare_host = bool(legacy_clang_options())
    run_suite(('--legacy-clang-abi',), compare_host)
    print(f'legacy float barriers: 216 layouts, 119 unnamed-field layouts, 480 nested layouts (240 named-field), pressure/variadic and NO_CLASS checks passed; host cross-calls: {"Clang 18.1" if compare_host else "not run (self-calls only)"}')



if __name__ == '__main__':
    main()

"""Floating records with barriers at eightbyte boundaries."""
from pathlib import Path
import subprocess
import tempfile
from test_bit_fields import ROOT, HOST, KCC, legacy_clang_options, object_file, run
from test_zero_width_memory_abi import pair


def align(n, a):
    return (n + a - 1) // a * a


def main():
    (ROOT/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='aligned-barriers-', dir=ROOT/'build') as tmp:
        d = Path(tmp)
        barriers = (('unsigned char', 1), ('unsigned short', 2), ('unsigned', 4),
                    ('unsigned long', 8), ('_Bool', 1), ('enum E', 4))
        sizes = {'float': 4, 'double': 8, 'int': 4}
        accepted = rejected = memory = 0
        for first in ('float', 'double'):
            for last in ('float', 'double', 'int'):
                for barrier, barrier_align in barriers:
                    for n in (0, 1, 3, 4, 7, 8):
                        first_offset = align(n, sizes[first])
                        barrier_offset = align(first_offset + sizes[first], barrier_align)
                        last_offset = align(barrier_offset, sizes[last])
                        size = align(last_offset + sizes[last], max(sizes[first], sizes[last]))
                        padding = f'char pre[{n}];' if n else ''
                        declaration = (f'enum E {{ V=1 }}; struct S {{ {padding} {first} x; '
                                       f'{barrier} :0; {last} y; }};\n')
                        definition = 'struct S f(struct S s){s.x+=2; s.y+=3; return s;}\n'
                        caller = (f'struct S f(struct S); int main(void){{struct S s={{0}}; s.x=1;s.y=2; '
                                  f'if(sizeof(s)!={size} || (char*)&s.x-(char*)&s!={first_offset} || '
                                  f'(char*)&s.y-(char*)&s!={last_offset}) return 1; '
                                  'struct S r=f(s);return r.x!=3 || r.y!=5 || s.x!=1 || s.y!=2;}\n')
                        (d/'owner.c').write_text(declaration + definition)
                        (d/'companion.c').write_text(declaration + caller)
                        if size <= 16 and barrier_offset % 8:
                            rejected += 1
                            for options in ((), ('--legacy-clang-abi',)):
                                result = subprocess.run([str(KCC), *options, str(d/'owner.c')],
                                                        text=True, capture_output=True, timeout=15)
                                assert result.returncode == 1 and not result.stdout and 'aggregate ABI unsupported' in result.stderr, (declaration, options, result.stderr)
                            continue
                        if size > 16:
                            memory += 1
                        else:
                            accepted += 1
                        for options in ((), ('--legacy-clang-abi',)):
                            for a, b in (('host', 'kcc'), ('kcc', 'host')):
                                object_file(d/'owner.c', d/'owner.o', a, options)
                                object_file(d/'companion.c', d/'companion.o', b, options)
                                run([HOST, d/'owner.o', d/'companion.o', '-o', d/'test'])
                                try:
                                    run([d/'test'])
                                except AssertionError as e:
                                    raise AssertionError((declaration, options, a, b, e)) from e
        assert (accepted, rejected, memory) == (75, 35, 106), (accepted, rejected, memory)
        # Nonzero unnamed fields use the native host's corresponding ABI mode.
        decls, bodies, checks = [], [], []
        i = 0
        for typ, limit in (('unsigned char', 8), ('unsigned short', 16), ('unsigned', 32), ('unsigned long', 63)):
            for width in range(1, limit + 1):
                decls += [f'struct B{i} {{ float a; unsigned long :0; {typ} :{width}; float b; }};',
                          f'struct B{i} f{i}(struct B{i});']
                bodies.append(f'struct B{i} f{i}(struct B{i} s){{s.a+=2;s.b+=3;return s;}}')
                checks += [f'struct B{i} x{i}={{0}};x{i}.a=1;x{i}.b=2;struct B{i} r{i}=f{i}(x{i});',
                           f'if(r{i}.a!=3||r{i}.b!=5||x{i}.a!=1||x{i}.b!=2) return 1;']
                i += 1
        text = '\n'.join(decls) + '\n'
        (d/'owner.c').write_text(text + '\n'.join(bodies) + '\n')
        options = legacy_clang_options()
        # Batch callers to respect the record-temporary limit.
        for start in range(0, len(checks), 40):
            (d/'companion.c').write_text(text + 'int main(void){\n' + '\n'.join(checks[start:start+40]) + '\nreturn 0;}\n')
            for a, b in (('host', 'kcc'), ('kcc', 'host')):
                object_file(d/'owner.c', d/'owner.o', a, options)
                object_file(d/'companion.c', d/'companion.o', b, options)
                run([HOST, d/'owner.o', d/'companion.o', '-o', d/'test'])
                run([d/'test'])
        # Inner offset zero is not enough: the effective outer offset matters.
        source = 'struct I { unsigned :0; float b; }; struct S { float a; struct I i; }; struct S f(struct S x){return x;}\n'
        (d/'source.c').write_text(source)
        for options in ((), ('--legacy-clang-abi',)):
            result = subprocess.run([str(KCC), *options, str(d/'source.c')], capture_output=True, text=True, timeout=15)
            assert result.returncode == 1 and not result.stdout and 'aggregate ABI unsupported' in result.stderr, result.stderr
        declarations = '''#include <stdarg.h>
struct I {float a; unsigned :0; float b;}; struct S {int pre; struct I i;};
struct T {float a; unsigned long :0; float b;};
union U {struct T t; long n[2];};
struct A {float a; unsigned long :0;}; struct N {struct A a[2];};
'''
        definitions = '''struct S nest(struct S s){s.i.a+=2;s.i.b+=3;return s;}
struct T pressure(long a,long b,long c,long d,long e,long f,double a0,double a1,double a2,double a3,double a4,double a5,double a6,struct T s,int z) {s.a+=a+b+c+d+e+f+z;s.b+=a0+a1+a2+a3+a4+a5+a6;return s;}
int var(struct T s,...) {va_list a;va_start(a,s);int x=va_arg(a,int);double y=va_arg(a,double);va_end(a);return (int)(s.a+s.b)+x+(int)y;}
union U uni(union U s){s.t.a+=2;s.t.b+=3;return s;}
struct N array(struct N s){s.a[0].a+=2;s.a[1].a+=3;return s;}
'''
        caller = '''struct S nest(struct S); struct T pressure(long,long,long,long,long,long,double,double,double,double,double,double,double,struct T,int); int var(struct T,...); union U uni(union U); struct N array(struct N);
int main(void){struct S s={1,{1,2}};struct S r=nest(s);if(r.pre!=1||r.i.a!=3||r.i.b!=5) return 1;
struct T t={1,2}; struct T q=pressure(1,1,1,1,1,1,1,1,1,1,1,1,1,t,3);if(q.a!=10||q.b!=9) return 2;
if(var(t,3,4.)!=10) return 3;
union U u={0};u.t.a=1;u.t.b=2;union U v=uni(u);if(v.t.a!=3||v.t.b!=5) return 4;
struct N n={{{1},{2}}};struct N m=array(n);if(m.a[0].a!=3||m.a[1].a!=5) return 5;return 0;}
'''
        pair(d, declarations, definitions, caller)
    print('aligned float barrier ABI: 75 register and 106 MEMORY layouts in both directions/modes; 35 unaligned cases rejected; 119 unnamed-field layouts plus nested/union/pressure/variadic passed')


if __name__ == '__main__':
    main()

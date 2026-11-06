"""Bounded M21 SysV aggregate calls: separate objects, both directions."""
import os
import re
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
KCC = ROOT / 'build/kcc'
QBE = os.environ['QBE']
HOST = os.environ.get('HOST_CC', 'cc')


def run(cmd):
    p = subprocess.run([str(x) for x in cmd], capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, (cmd, p.returncode, p.stdout, p.stderr)
    return p


def test_pair(d, decl, body, caller):
    def kcc(src):
        (d/'k.c').write_text(src)
        p = run([KCC, d/'k.c'])
        assert not p.stderr, p.stderr
        (d/'k.ssa').write_text(p.stdout)
        run([QBE, '-t', 'amd64_sysv', '-o', d/'k.s', d/'k.ssa'])
        run([HOST, '-c', d/'k.s', '-o', d/'k.o'])
    def host(src):
        (d/'h.c').write_text(src)
        run([HOST, '-std=c2x', '-O2', '-Wall', '-Wextra', '-Werror', '-c', d/'h.c', '-o', d/'h.o'])
    for k, h in ((decl+body, decl+caller), (decl+caller, decl+body)):
        kcc(k); host(h)
        run([HOST, d/'k.o', d/'h.o', '-o', d/'exe'])
        run([d/'exe'])


def reject(d, src, diagnostic):
    (d/'bad.c').write_text(src)
    p = subprocess.run([str(KCC), str(d/'bad.c')], capture_output=True, text=True, timeout=30)
    pattern = re.escape(str(d/'bad.c')) + r':\d+:\d+: error: ' + re.escape(diagnostic) + r'\n'
    assert p.returncode == 1 and not p.stdout and re.fullmatch(pattern, p.stderr), (src, p.stdout, p.stderr)


def main():
    with tempfile.TemporaryDirectory(prefix='aggregate-abi-', dir=ROOT/'build') as tmp:
        d = Path(tmp)
        # All small integer extents exercise rounding, padding and stack staging.
        for n in range(1, 17):
            decl = f'struct S {{ unsigned char a[{n}]; }}; '
            body = 'struct S transform(struct S x) { x.a[0]+=2; return x; } '
            caller = ('struct S transform(struct S); int main(void) { struct S x={0}; '
                      f'x.a[0]=40; x.a[{n-1}]=40; struct S y=transform(x); '
                      'return y.a[0]!=42 || x.a[0]!=40; }')
            test_pair(d, decl, body, caller)
        shapes = [
            ('struct S { float a; };', 'x.a=1.5f;', 'y.a==3.5f', 'x.a+=2.0f;'),
            ('struct S { double a; double b; };', 'x.a=1.5; x.b=9.0;', 'y.a==3.5 && y.b==9.0', 'x.a+=2.0;'),
            ('struct S { double a; int b; };', 'x.a=1.5; x.b=9;', 'y.a==3.5 && y.b==9', 'x.a+=2.0;'),
            ('struct S { unsigned int a:32; int b:32; double d; };', 'x.a=40; x.b=-2; x.d=1.5;', 'y.a==42 && y.b==-2 && y.d==1.5', 'x.a+=2;'),
            ('struct S { int a; double b; };', 'x.a=40; x.b=1.5;', 'y.a==42 && y.b==1.5', 'x.a+=2;'),
            ('struct S { float a[3]; };', 'x.a[0]=1.5f; x.a[1]=2.5f; x.a[2]=3.5f;', 'y.a[0]==3.5f && y.a[1]==2.5f && y.a[2]==3.5f', 'x.a[0]+=2.0f;'),
            ('union S { double a; long b; };', 'x.b=40;', 'y.b==42', 'x.b+=2;'),
            ('struct S { union { float f; int i; } u; double d; };', 'x.u.i=40; x.d=1.5;', 'y.u.i==42 && y.d==1.5', 'x.u.i+=2;'),
            ('struct S { double a[8]; };', 'x.a[0]=1.5; x.a[7]=9.0;', 'y.a[0]==3.5 && y.a[7]==9.0', 'x.a[0]+=2.0;'),
            ('struct S { char a[17]; };', 'x.a[0]=40; x.a[16]=9;', 'y.a[0]==42 && y.a[16]==9', 'x.a[0]+=2;'),
            ('struct S { long a[3]; };', 'x.a[0]=40; x.a[2]=9;', 'y.a[0]==42 && y.a[2]==9', 'x.a[0]+=2;'),
        ]
        for shape, init, check, change in shapes:
            tag = 'union' if shape.startswith('union') else 'struct'
            decl = shape + ' '
            body = f'{tag} S transform({tag} S x) {{ {change} return x; }} '
            caller = (f'{tag} S transform({tag} S); int main(void) {{ {tag} S x={{0}}; {init} '
                      f'{tag} S (*p)({tag} S)=transform; {tag} S y=p(x); return !({check}); }}')
            test_pair(d, decl, body, caller)
        # Register exhaustion, mixed SSE/INTEGER, hidden sret pointer and stack arguments.
        decl = 'struct S { double d; long x; }; struct B { long a[3]; }; '
        body = '''struct B stress(int a,int b,int c,int d,int e,int f, double u,double v,double w,double x,double y,double z,double q,double r,struct S s,int last) {
          struct B t={{0}}; t.a[0]=a+b+c+d+e+f+last+s.x; t.a[1]=(long)(u+v+w+x+y+z+q+r+s.d); t.a[2]=77; return t; }'''
        caller = '''struct B stress(int,int,int,int,int,int,double,double,double,double,double,double,double,double,struct S,int);
          int main(void) { struct S s={1.0,10}; struct B b=stress(1,2,3,4,5,6,1.,1.,1.,1.,1.,1.,1.,1.,s,11); return b.a[0]!=42 || b.a[1]!=9 || b.a[2]!=77; }'''
        test_pair(d, decl, body, caller)
        # Aggregate register assignment must roll back when only one class is
        # exhausted, leaving the other class available for a later scalar.
        decl = 'struct S { double d; long n; }; '
        body = ('int mix(int a,int b,int c,int d,int e,int f,struct S s,double tail) '
                '{ return a+b+c+d+e+f+s.n+(int)s.d+(int)tail; } ')
        caller = ('int mix(int,int,int,int,int,int,struct S,double); '
                  'int main(void) { struct S s={1.,10}; return mix(1,2,3,4,5,6,s,10.)!=42; }')
        test_pair(d, decl, body, caller)
        body = ('int mix(double a,double b,double c,double d,double e,double f,double g,double h,struct S s,int tail) '
                '{ return (int)(a+b+c+d+e+f+g+h+s.d)+s.n+tail; } ')
        caller = ('int mix(double,double,double,double,double,double,double,double,struct S,int); '
                  'int main(void) { struct S s={1.,10}; return mix(1.,1.,1.,1.,1.,1.,1.,1.,s,23)!=42; }')
        test_pair(d, decl, body, caller)
        decl = 'struct S { long a,b; }; '
        body = ('int mix(int a,int b,int c,int d,int e,struct S s,int tail) '
                '{ return a+b+c+d+e+s.a+s.b+tail; } ')
        caller = ('int mix(int,int,int,int,int,struct S,int); '
                  'int main(void) { struct S s={10,11}; return mix(1,2,3,4,5,s,6)!=42; }')
        test_pair(d, decl, body, caller)
        # Fixed aggregate parameter in a variadic signature; parameter mutation is private.
        decl = 'struct S { int x; }; '
        body = 'int f(struct S s, ...) { s.x+=2; return s.x; } '
        caller = 'int f(struct S,...); int main(void) { struct S s={40}; return f(s,3.0)!=42 || s.x!=40; }'
        test_pair(d, decl, body, caller)
        # va_start must account for both fixed aggregate register classes.
        decl = '#include <stdarg.h>\nstruct S { double d; long n; }; '
        body = ('int var(struct S s, ...) { va_list a; va_start(a,s); '
                'int x=va_arg(a,int); double y=va_arg(a,double); va_end(a); '
                'return s.n+x==42 && s.d+y==4.0; } ')
        caller = ('int var(struct S,...); int main(void) { struct S s={1.5,40}; '
                  'return !var(s,2,2.5); }')
        test_pair(d, decl, body, caller)
        # Explicit alignment through 8 is accepted; only-padding bytes are not
        # classified as INTEGER when a float occupies the same eightbyte.
        decl = 'struct S { _Alignas(8) float f; }; '
        body = 'struct S transform(struct S x) { x.f+=2.0f; return x; } '
        caller = ('struct S transform(struct S); int main(void) { struct S s={1.5f}; '
                  'return transform(s).f!=3.5f; }')
        test_pair(d, decl, body, caller)
        # Tail subobject of a return value, recursion, discarded call, repeated calls.
        source = '''struct X { int z; }; struct Y { long a; struct X x; };
          struct Y make(int n) { struct Y y={5,{n}}; return y; }
          struct X id(struct X x) { return x; }
          struct X rec(int n) { if(n) return rec(n-1); return id(make(42).x); }
          int main(void) { int i=0; while(i<100) { make(i); if(rec(2).z!=42) return 1; i++; } return 0; }'''
        (d/'local.c').write_text(source)
        il = run([KCC, d/'local.c']).stdout
        (d/'local.ssa').write_text(il)
        run([QBE, '-t', 'amd64_sysv', '-o', d/'local.s', d/'local.ssa'])
        run([HOST, d/'local.s', '-o', d/'local'])
        run([d/'local'])
        error = ('aggregate ABI unsupported (M21): requires complete record without flexible array, '
                 'size 1..64, alignment <= 8 and representable eightbytes')
        for src in [
            'struct S { char a[65]; }; int f(struct S x) { return x.a[0]; }',
            'struct S { _Alignas(16) int x; }; struct S f(void) { struct S s={0}; return s; }',
            'struct S { int n; char a[]; }; int f(struct S x) { return x.n; }',
        ]:
            reject(d, src, error)
        reject(d, 'struct S { int x; }; int f(int,...); int g(void) { struct S s={0}; return f(1,s); }', 'unsupported variadic argument type (aggregate varargs are not supported yet)')
        # Aggregate call results count toward the existing per-function limit,
        # even when discarded; the 257th is diagnosed before emitting IL.
        prefix = 'struct S { int x; }; struct S f(void); void g(void) {'
        (d/'limit.c').write_text(prefix + 'f();'*256 + '}')
        run([KCC, d/'limit.c'])
        reject(d, prefix + 'f();'*257 + '}', 'function exceeds record value temporary limit (256)')
        reject(d, 'struct S { int x; }; struct S f(void); void g(void) { char a[1048576]; f(); }',
               'function exceeds local object and record temporary storage limit (1 MiB)')
        # Unevaluated aggregate signatures stay representable even outside this slice.
        (d/'query.c').write_text('struct S { char x[65]; }; struct S f(void); int g(void) { return sizeof(f())==65; }')
        query = run([KCC, d/'query.c'])
        assert ':kcc_abi_' not in query.stdout
    print('M21 aggregate ABI tests passed with', HOST)


if __name__ == '__main__':
    main()

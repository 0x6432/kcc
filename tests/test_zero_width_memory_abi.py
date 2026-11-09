"""Zero-width barriers in bounded MEMORY-class aggregates, both ABI modes."""
from pathlib import Path
import subprocess
import tempfile
from test_bit_fields import ROOT, HOST, KCC, object_file, run


def pair(d, declaration, body, caller):
    (d/'owner.c').write_text(declaration + '\n' + body + '\n')
    (d/'companion.c').write_text(declaration + '\n' + caller + '\n')
    for options in ((), ('--legacy-clang-abi',)):
        for a, b in (('host', 'host'), ('host', 'kcc'), ('kcc', 'host'), ('kcc', 'kcc')):
            object_file(d/'owner.c', d/'owner.o', a, options)
            object_file(d/'companion.c', d/'companion.o', b, options)
            run([HOST, d/'owner.o', d/'companion.o', '-o', d/'test'])
            result = subprocess.run([str(d/'test')], capture_output=True, text=True, timeout=15)
            assert result.returncode == 0 and not result.stdout and not result.stderr, (a, b, options, declaration, result)


def main():
    (ROOT/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='zero-memory-abi-', dir=ROOT/'build') as tmp:
        d = Path(tmp)
        # Original formerly rejected shape remains intact and gets runtime coverage.
        decl = 'struct S { long a[3]; unsigned :0; int x; };'
        body = 'struct S f(struct S x){return x;}'
        caller = ('struct S f(struct S); int main(void){ struct S s={{1,2,3},42}; '
                  'struct S r=f(s); return r.a[0]!=1 || r.a[2]!=3 || r.x!=42; }')
        pair(d, decl, body, caller)
        decl = '#include <stdarg.h>\nstruct S { long a[3]; unsigned :0; int x; };'
        body = ('int var(struct S s,...){ va_list ap; va_start(ap,s); '
                'int n=va_arg(ap,int); double d=va_arg(ap,double); va_end(ap); '
                'return s.a[2]+s.x+n+(int)d; }')
        caller = ('int var(struct S,...); int main(void){ struct S s={{1,2,3},4}; '
                  'return var(s,5,6.)!=18 || s.a[2]!=3 || s.x!=4; }')
        pair(d, decl, body, caller)
        # Offset the tail by several sizes, including a 17-byte MEMORY record.
        shapes = [('unsigned', n) for n in (13, 16, 17, 28, 40, 55)]
        shapes += [(typ, n) for typ in ('unsigned char', 'unsigned short', 'unsigned long', '_Bool', 'enum E')
                   for n in (16, 17, 28, 40, 55)]
        for typ, n in shapes:
            decl = f'enum E {{ V=1 }}; struct S {{ char data[{n}]; {typ} :0; char end; }};'
            body = '''struct S f(struct S x) { x.data[0]++; x.end+=2; return x; }
int pressure(long a,long b,long c,long d,long e,long f0,double a0,double a1,double a2,double a3,double a4,double a5,double a6,double a7,struct S x,int y,struct S z,int last) {
return a+b+c+d+e+f0+(int)(a0+a1+a2+a3+a4+a5+a6+a7)+x.data[0]+x.end+y+z.data[0]+z.end+last; }'''
            caller = f'''struct S f(struct S);
int pressure(long,long,long,long,long,long,double,double,double,double,double,double,double,double,struct S,int,struct S,int);
int main(void) {{ struct S x={{0}},z={{0}}; x.data[0]=1; x.data[{n-1}]=7; x.end=3; z.data[0]=2; z.end=4;
struct S (*p)(struct S)=f; struct S r=p(x);
if(sizeof(struct S)<=16 || sizeof(struct S)>64 || r.data[0]!=2 || r.data[{n-1}]!=7 || r.end!=5 || x.data[0]!=1 || x.end!=3) return 1;
if(pressure(1,1,1,1,1,1,1,1,1,1,1,1,1,1,x,5,z,6)!=35) return 2; return 0; }}'''
            pair(d, decl, body, caller)
        decl = ('struct Inner { unsigned x:3; unsigned :0; char c; }; '
                'struct S { struct Inner a[2]; long tail; };')
        body = 'struct S f(struct S s){ s.a[0].x=3; s.a[1].c+=2; s.tail++; return s; }'
        caller = ('struct S f(struct S); int main(void){ struct S s={{{1,2},{4,5}},9}; '
                  'struct S r=f(s); return sizeof(s)<=16 || r.a[0].x!=3 || r.a[0].c!=2 || '
                  'r.a[1].x!=4 || r.a[1].c!=7 || r.tail!=10 || s.tail!=9; }')
        pair(d,decl,body,caller)
        decl = 'union S { struct { char data[13]; unsigned :0; char end; } x; char raw[64]; };'
        body = 'union S f(union S s){ s.x.data[0]++; s.x.end++; return s; }'
        caller = ('union S f(union S); int main(void){ union S s={0}; s.x.data[0]=4; s.x.end=7; '
                  'union S r=f(s); return sizeof(s)!=64 || r.x.data[0]!=5 || r.x.end!=8 || s.x.end!=7; }')
        pair(d,decl,body,caller)
        # Batch mixed named fields, floating members and varied padding, so the
        # MEMORY path is exercised with more than byte arrays around a barrier.
        declarations, definitions, checks = ['enum E { V=1 };'], [], []
        for i, (typ, n) in enumerate((typ, n) for typ in
                                     ('unsigned', 'unsigned char', 'unsigned short',
                                      'unsigned long', '_Bool', 'enum E')
                                     for n in (1, 3, 8, 16, 24, 32)):
            declarations += [f'struct M{i} {{ unsigned v:3; {typ} :0; double d; int x; char pad[{n}]; }};',
                             f'struct M{i} m{i}(struct M{i});']
            definitions += [f'struct M{i} m{i}(struct M{i} s){{s.v=5; s.d+=2; s.x++; return s;}}']
            checks += [f'struct M{i} x{i}={{0}}; x{i}.v=3; x{i}.d=1.5; x{i}.x=8; x{i}.pad[{n-1}]=9;',
                       f'struct M{i} r{i}=m{i}(x{i});',
                       f'if(sizeof(x{i})<=16 || sizeof(x{i})>64 || r{i}.v!=5 || r{i}.d!=3.5 || '
                       f'r{i}.x!=9 || r{i}.pad[{n-1}]!=9 || x{i}.v!=3 || x{i}.x!=8) return 1;']
        text='\n'.join(declarations)+'\n'
        (d/'owner.c').write_text(text+'\n'.join(definitions)+'\n')
        (d/'companion.c').write_text(text+'int main(void){\n'+'\n'.join(checks)+'\nreturn 0;}\n')
        for options in ((), ('--legacy-clang-abi',)):
            for a, b in (('host','kcc'), ('kcc','host')):
                object_file(d/'owner.c', d/'owner.o', a, options)
                object_file(d/'companion.c', d/'companion.o', b, options)
                run([HOST, d/'owner.o', d/'companion.o', '-o', d/'test'])
                run([d/'test'])
        # The former 64-byte ceiling no longer rejects this barrier record.
        decl = 'struct S { char a[64]; unsigned :0; int x; };'
        body = 'struct S f(struct S x){x.a[63]++; x.x+=2; return x;}'
        caller = ('struct S f(struct S); int main(void){struct S s={0}; s.a[63]=7; s.x=40; '
                  'struct S r=f(s); return r.a[63]!=8 || r.x!=42 || s.a[63]!=7;}')
        pair(d, decl, body, caller)
        # Floating register-class barriers and records beyond the size limit remain rejected.
        for src in ('struct S { float a; unsigned :0; float b; }; struct S f(struct S x){return x;}',
                    'struct S { char a[1024]; unsigned :0; int x; }; struct S f(struct S x){return x;}'):
            (d/'reject.c').write_text(src)
            options_to_reject = ((),) if 'float a;' in src else ((), ('--legacy-clang-abi',))
            for options in options_to_reject:
                p = subprocess.run([str(KCC), *options, str(d/'reject.c')], capture_output=True, text=True, timeout=15)
                assert p.returncode == 1 and not p.stdout and 'aggregate ABI unsupported' in p.stderr, (src, options, p.stderr)
            if 'float a;' in src:
                p = subprocess.run([str(KCC), '--legacy-clang-abi', str(d/'reject.c')], capture_output=True, text=True, timeout=15)
                assert p.returncode == 0, (src, p.stderr)
    print('zero-width MEMORY aggregate ABI: original, variadic and 33 pressure/nested/union shapes, four combinations in both modes and 36 mixed layouts in both directions passed')


if __name__=='__main__': main()

"""Named 33–63-bit long fields: storage, conversions and bounded SysV ABI.

Run with QBE and HOST_CC set. All mixed objects are compiled separately.
Arithmetic on an uncast field is intentionally rejected (GCC/Clang disagree).
"""
from pathlib import Path
import subprocess
import tempfile
from test_bit_fields import ROOT, HOST, KCC, object_file, run

KINDS = [('sl', 'signed long', True), ('ul', 'unsigned long', False),
         ('sll', 'signed long long', True), ('ull', 'unsigned long long', False)]


def matrix(d, prefix, kind):
    decl, owner, checks = [], [], []
    for width in range(33, 64):
        for suffix, typ, signed in [kind]:
            n = f'w{prefix}_{width}_{suffix}'
            initial = f'-{1 << (width-1)}LL' if signed else f'{(1 << width)-1}ULL'
            updated = f'-{(1 << (width-2))+3}LL' if signed else f'{(1 << (width-1))+5}ULL'
            cast = 'long long' if signed else 'unsigned long long'
            decl.extend([f'struct {n} {{ unsigned p:{prefix}; {typ} a:{width}; unsigned b:3; char end; }};',
                         f'extern struct {n} g{n}; int size{n}(void); int align{n}(void); int end{n}(void); struct {n} f{n}(struct {n} x); {cast} bump{n}(struct {n} *x);'])
            owner.extend([f'struct {n} g{n}={{.p={(1<<prefix)-1},.a={initial},.b=5,.end=77}};',
                          f'int size{n}(void){{return sizeof(struct {n});}} int align{n}(void){{return _Alignof(struct {n});}}',
                          f'int end{n}(void){{return (char*)&g{n}.end-(char*)&g{n};}}',
                          f'struct {n} f{n}(struct {n} x){{x.a={updated}; x.b=6; return x;}}',
                          f'{cast} bump{n}(struct {n} *x){{return ({cast})x->a++;}}'])
            checks.extend([f'struct {n} r{n}=f{n}(g{n});',
                           f'if(size{n}()!=sizeof(struct {n}) || align{n}()!=_Alignof(struct {n}) || end{n}()!=(char*)&g{n}.end-(char*)&g{n} || ({cast})g{n}.a!=({cast})({initial}) || ({cast})r{n}.a!=({cast})({updated}) || r{n}.p!={(1<<prefix)-1} || r{n}.b!=6 || r{n}.end!=77) return {width};',
                           f'if(bump{n}(&g{n})!=({cast})({initial}) || ({cast})g{n}.a!=({cast})({f"-{(1 << (width-1))-1}LL" if signed else "0"}) || g{n}.p!={(1<<prefix)-1} || g{n}.b!=5 || g{n}.end!=77) return {width};'])
    text = '\n'.join(decl)+'\n'
    (d/'owner.c').write_text(text+'\n'.join(owner)+'\n')
    (d/'companion.c').write_text(text+'\nint main(void){\n'+'\n'.join(checks)+'\nreturn 0;}\n')
    for a, b in [('host', 'kcc'), ('kcc', 'host')]:
        object_file(d/'owner.c', d/'owner.o', a)
        object_file(d/'companion.c', d/'companion.o', b)
        run([HOST, d/'owner.o', d/'companion.o', '-o', d/'test'])
        result = subprocess.run([str(d/'test')], capture_output=True, text=True)
        if result.returncode or result.stdout or result.stderr:
            raise AssertionError(f'prefix {prefix}, {a}/{b}: {result.returncode} {result.stdout} {result.stderr}')

DECL = r'''
struct S { unsigned p:5; unsigned long u:59; signed long long s:47; unsigned tail:6; char end; };
struct F { float x; unsigned long u:37; }; struct M { double x; struct S s; double y; };
union U { unsigned long u:61; signed long s:61; double d; };
struct N { struct F f; union U u; };
extern struct S g; extern int calls; struct S *once(void);
struct S exchange(struct S); struct F fexchange(struct F); struct F pressure(long,long,long,long,long,long,struct F); int vf(struct F,int,...); unsigned long get_u(void); unsigned long echo(unsigned long); struct M mexchange(struct M); union U uexchange(union U); struct N nexchange(struct N);
'''
OWNER = DECL + r'''
struct S g={.p=17,.u=3,.u=0x7123456789abcdULL,.s=-1234567890123LL,.tail=42,.end=91}; int calls;
struct S *once(void){calls++;return &g;}
unsigned long get_u(void){return g.u;} unsigned long echo(unsigned long x){return x;}
struct S exchange(struct S x){x.u=0x6fedcba9876543ULL; x.s=-1234567891234LL; return x;}
struct F fexchange(struct F x){x.x=2.5f; x.u=0x123456789aULL; return x;}
struct F pressure(long a,long b,long c,long d,long e,long f,struct F x){x.x=(float)(a+b+c+d+e+f); x.u=0x123456789aULL; return x;}
int vf(struct F x,int n,...){return x.x==1.5f && (unsigned long)x.u==0x1122334455ULL && n==17;}
struct M mexchange(struct M x){x.x=4.5; x.s.u=0x3456789abcULL; x.y=8.5; return x;}
union U uexchange(union U x){x.s=-123456789012LL; return x;}
struct N nexchange(struct N x){x.f.u=0xabcdef123ULL; x.u.u=0x123456789abcULL; return x;}
'''
COMPANION = DECL + r'''
int main(void){
 struct S x={.p=17,.u=0x7123456789abcdULL,.s=-1234567890123LL,.tail=42,.end=91};
 struct S y=exchange(x); struct F f={1.5f,0x1122334455ULL}, z=fexchange(f);
 struct M m={1.5,x,2.5}, n=mexchange(m); union U u={.u=77}, v=uexchange(u);
 struct N a={{3.5f,0x111111111ULL},{.u=5}}, b=nexchange(a);
 struct F (*fp)(struct F)=fexchange; struct F indirect=fp(f), stressed=pressure(1,2,3,4,5,6,f);
 if(indirect.x!=2.5f || (unsigned long)indirect.u!=0x123456789aULL || stressed.x!=21.0f || (unsigned long)stressed.u!=0x123456789aULL || !vf(f,17,9)) return 9;
 if(get_u()!=0x7123456789abcdULL || echo(g.u)!=0x7123456789abcdULL || !g.u || (unsigned long)g.u+1UL!=0x7123456789abceULL) return 10;
 if((unsigned long long)g.u!=0x7123456789abcdULL || (long long)g.s!=-1234567890123LL || g.p!=17 || g.tail!=42 || g.end!=91) return 1;
 if((unsigned long long)y.u!=0x6fedcba9876543ULL || (long long)y.s!=-1234567891234LL || y.p!=17 || y.tail!=42 || y.end!=91) return 2;
 if(z.x!=2.5f || (unsigned long)z.u!=0x123456789aULL || n.x!=4.5 || (unsigned long)n.s.u!=0x3456789abcULL || n.y!=8.5 || (long)v.s!=-123456789012LL || b.f.x!=3.5f || (unsigned long)b.f.u!=0xabcdef123ULL || (unsigned long)b.u.u!=0x123456789abcULL) return 3;
 calls=0; if((unsigned long)(once()->u=0xffffffffffffffffULL)!=0x7ffffffffffffffULL || calls!=1 || (unsigned long)g.u!=0x7ffffffffffffffULL || g.p!=17 || g.tail!=42) return 4;
 calls=0; if((unsigned long)once()->u++!=0x7ffffffffffffffULL || calls!=1 || (unsigned long)g.u!=0 || g.tail!=42) return 5;
 calls=0; if((long long)++once()->s!=-1234567890122LL || calls!=1 || (long long)g.s!=-1234567890122LL) return 6;
 if((long long)(g.s=0x400000000000LL)!=-70368744177664LL || (long long)g.s!=-70368744177664LL || g.end!=91) return 7;
 struct S q={.p=1,.u=3,.u=0x123456789abcdefULL,.s=-2,.tail=2,.end=3};
 if((unsigned long)q.u!=0x123456789abcdefULL || (long long)q.s!=-2 || q.p!=1 || q.tail!=2 || q.end!=3) return 8;
 return 0;
}
'''

REJECT = [
 'return s.u + 1;', 'return (0,s.u) + 1;', 'return (s.u=1) + 1;',
 'return (s.u++) + 1;', 'return +s.u;', 'return ~s.u;',
 'return s.u==1;', 'return 1 ? s.u : 0;', 's.u += 1; return 0;',
 'long x=0; x += s.u; return x;', 'switch(s.u){case 0:return 0;} return 1;',
 'int a[2]; return a[s.u];', 'return variadic(0,s.u);',
 'return _Generic(s.u, unsigned long:1,default:0);',
 'typeof((0,s.u)) x=0; return x;', 'return sizeof(+s.u);',
]

def main():
    (ROOT/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='named-wide-fields-', dir=ROOT/'build') as tmp:
        d=Path(tmp)
        (d/'owner.c').write_text(OWNER); (d/'companion.c').write_text(COMPANION)
        for a,b in [('host','host'),('host','kcc'),('kcc','host'),('kcc','kcc')]:
            object_file(d/'owner.c',d/'owner.o',a); object_file(d/'companion.c',d/'companion.o',b)
            run([HOST,d/'owner.o',d/'companion.o','-o',d/'test']); run([d/'test'])
        for prefix in range(1,8):
            for kind in KINDS: matrix(d,prefix,kind)
        for text in REJECT:
            (d/'reject.c').write_text('struct S { unsigned long u:33; } s; int variadic(int, ...); int f(void){'+text+'}\n')
            result=subprocess.run([str(KCC),str(d/'reject.c')],capture_output=True,text=True)
            if result.returncode == 0 or result.stdout or not ('wide bit-field operation' in result.stderr or 'generic selection of an unpromoted' in result.stderr):
                raise AssertionError((text,result.returncode,result.stdout,result.stderr))
        for source, options, diagnostic in [
            ('struct S { float x; unsigned :0; float y; unsigned long a:33; }; struct S f(struct S x){return x;}', (), 'aggregate ABI unsupported'),
            ('struct S { unsigned long :64; unsigned long a:33; }; struct S f(struct S x){return x;}', ('--legacy-clang-abi',), 'aggregate ABI unsupported'),
        ]:
            (d/'abi-reject.c').write_text(source)
            result=subprocess.run([str(KCC),*options,str(d/'abi-reject.c')],capture_output=True,text=True)
            if result.returncode != 1 or result.stdout or diagnostic not in result.stderr:
                raise AssertionError((source,options,result.returncode,result.stderr))
    print(f'named wide bit-fields: {7*31*4} layouts both directions, 4 object combinations, {len(REJECT)} semantic guards and 2 ABI refusals passed ({HOST})')

if __name__=='__main__': main()

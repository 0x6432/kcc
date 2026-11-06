"""Named int bit-fields inside SysV by-value aggregate calls and returns."""
from pathlib import Path
import tempfile
from test_bit_fields import ROOT, HOST, object_file, run

DECL = r'''
struct S { char c; unsigned a:9,b:4; char tail; };
struct Mix { double d; char c; unsigned a:9,b:4; char end; };
union U { double d; struct { char c; unsigned a:9,b:4; } v; };
struct Nest { struct S s; float f; };
struct S f(struct S x); struct Mix g(struct Mix x); union U h(union U x);
struct Nest j(struct Nest x);
struct S pressure(int a,int b,int c,int d,int e,int f,struct S x);
'''
OWNER = DECL + r'''
struct S f(struct S x) { x.a+=3; x.b+=2; x.tail++; return x; }
struct Mix g(struct Mix x) { x.d+=1; x.a+=3; x.b+=2; x.end++; return x; }
union U h(union U x) { x.v.a+=3; x.v.b+=2; return x; }
struct Nest j(struct Nest x) { x.s.a+=3; x.s.b+=2; x.f+=1; return x; }
struct S pressure(int a,int b,int c,int d,int e,int f,struct S x) { x.a+=a+b+c+d+e+f; x.b+=1; return x; }
'''
COMPANION = DECL + r'''
int main(void) {
 struct S a={5, 300, 9, 70}, b=f(a), p=pressure(1,2,3,4,5,6,a);
 struct Mix m={4.5, 1, 257, 7, 9}, n=g(m);
 union U u={.v={2,301,9}}, v=h(u);
 struct Nest x={{3,301,10,12},3.5f}, y=j(x);
 if(b.c!=5||b.a!=303||b.b!=11||b.tail!=71||a.a!=300) return 1;
 if(p.a!=321||p.b!=10||p.c!=5||p.tail!=70) return 2;
 if(n.d!=5.5||n.c!=1||n.a!=260||n.b!=9||n.end!=10||m.a!=257) return 3;
 if(v.v.c!=2||v.v.a!=304||v.v.b!=11) return 4;
 if(y.s.c!=3||y.s.a!=304||y.s.b!=12||y.s.tail!=12||y.f!=4.5f) return 5;
 return 0;
}
'''

def matrix(d, prefix):
    decl, owner, checks = [], [], []
    for w in range(1,33):
        for signed in (False, True):
            name=f'f{prefix}_{w}_{"s" if signed else "u"}'
            typ='signed' if signed else 'unsigned'
            old='-1' if signed else '0'
            new='0' if signed else '1'
            decl += [f'struct {name} {{ char p[{prefix}]; {typ} a:{w}; unsigned b:3; char tail; }};',
                     f'struct {name} {name}(struct {name} x);']
            owner += [f'struct {name} {name}(struct {name} x) {{ x.a={new}; x.b=6; x.tail++; return x; }}']
            checks += [f'struct {name} x{name} = {{ {{11}}, {old}, 3, 71 }}; struct {name} y{name}={name}(x{name});',
                       f'if(y{name}.p[0]!=11||y{name}.a!={new}||y{name}.b!=6||y{name}.tail!=72||x{name}.b!=3) return 1;']
    text='\n'.join(decl)+'\n'
    (d/'owner.c').write_text(text+'\n'.join(owner))
    (d/'companion.c').write_text(text+'\nint main(void){\n'+'\n'.join(checks)+'\nreturn 0;}')
    for a,b in [('host','kcc'),('kcc','host')]:
        object_file(d/'owner.c',d/'owner.o',a); object_file(d/'companion.c',d/'companion.o',b)
        run([HOST,d/'owner.o',d/'companion.o','-o',d/'test']); run([d/'test'])

def main():
    (ROOT/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bitfield-abi-',dir=ROOT/'build') as tmp:
        d=Path(tmp)
        (d/'owner.c').write_text(OWNER); (d/'companion.c').write_text(COMPANION)
        for a,b in [('host','host'),('host','kcc'),('kcc','host'),('kcc','kcc')]:
            object_file(d/'owner.c',d/'owner.o',a); object_file(d/'companion.c',d/'companion.o',b)
            run([HOST,d/'owner.o',d/'companion.o','-o',d/'test']); run([d/'test'])
        for prefix in range(1,8): matrix(d,prefix)
    print('named bit-field aggregates: four host/KCC combinations and 448 by-value layouts in both directions passed')

if __name__=='__main__': main()

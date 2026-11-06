"""Unnamed int bit-fields in SysV by-value aggregate calls and returns."""
from pathlib import Path
import tempfile
from test_bit_fields import ROOT, HOST, object_file, run

DECL = r'''
struct A { float f; unsigned :1; }; struct B { double d; unsigned :1; };
struct C { float f; unsigned :31; float g; }; struct D { float f; unsigned :32; float g; };
union U { double d; unsigned :1; };
struct Big { long p[3]; unsigned :5; int n; };
struct A a(struct A x); struct B b(struct B x); struct C c(struct C x);
struct D d(struct D x); union U u(union U x);
struct Big big(struct Big x); struct C pressure(int a,int b,int c,int d,int e,int f,struct C x);
'''
OWNER = DECL + r'''
struct A a(struct A x){x.f+=1; return x;} struct B b(struct B x){x.d+=1; return x;}
struct C c(struct C x){x.f+=1; x.g+=2; return x;} struct D d(struct D x){x.f+=1; x.g+=2; return x;}
union U u(union U x){x.d+=1; return x;}
struct Big big(struct Big x){x.p[2]++; x.n+=2; return x;}
struct C pressure(int a,int b,int c,int d,int e,int f,struct C x){x.f+=a+b+c+d+e+f; x.g+=2; return x;}
'''
COMPANION = DECL + r'''
int main(void){
 struct A va={1.5f}, ra=a(va); struct B vb={1.5}, rb=b(vb);
 struct C vc={1.5f,2.5f}, rc=c(vc), rp=pressure(1,2,3,4,5,6,vc);
 struct D vd={3.5f,4.5f}, rd=d(vd);
 union U vu={.d=1.5}, ru=u(vu); struct Big vbig={{1,2,3},9}, rbig=big(vbig);
 if(ra.f!=2.5f||rb.d!=2.5||rc.f!=2.5f||rc.g!=4.5f) return 1;
 if(rd.f!=4.5f||rd.g!=6.5f) return 2;
 if(ru.d!=2.5||rbig.p[0]!=1||rbig.p[2]!=4||rbig.n!=11||vbig.n!=9) return 3;
 if(rp.f!=22.5f||rp.g!=4.5f||vc.f!=1.5f) return 4;
 return 0;
}
'''

def matrix(d, typ):
    decl, owner, checks = [], [], []
    for w in range(1,33):
        name=f'f_{typ}_{w}'
        decl += [f'struct {name} {{ {typ} f; unsigned :{w}; float g; }};', f'struct {name} {name}(struct {name} x);']
        owner += [f'struct {name} {name}(struct {name} x) {{ x.f+=1; x.g+=2; return x; }}']
        checks += [f'struct {name} x{name}={{1.5,2.5f}}, y{name}={name}(x{name});', f'if(y{name}.f!=2.5 || y{name}.g!=4.5f || x{name}.g!=2.5f) return {w+1};']
    text='\n'.join(decl)+'\n'
    (d/'owner.c').write_text(text+'\n'.join(owner))
    (d/'companion.c').write_text(text+'\nint main(void){\n'+'\n'.join(checks)+'\nreturn 0;}')
    for a,b in [('host','kcc'),('kcc','host')]:
        object_file(d/'owner.c',d/'owner.o',a); object_file(d/'companion.c',d/'companion.o',b)
        run([HOST,d/'owner.o',d/'companion.o','-o',d/'test'])
        try: run([d/'test'])
        except AssertionError as e: raise AssertionError(f'{typ} {a}/{b}: {e}') from e

def matrix_integer(d, prefix):
    decl, owner, checks = [], [], []
    for w in range(1,33):
        name=f'i_{prefix}_{w}'
        decl += [f'struct {name} {{ char p[{prefix}]; unsigned :{w}; unsigned x:5; float f; }};', f'struct {name} {name}(struct {name} x);']
        owner += [f'struct {name} {name}(struct {name} x) {{ x.x+=1; x.f+=2; return x; }}']
        checks += [f'struct {name} x{name}={{{{11}},7,2.5f}}, y{name}={name}(x{name});', f'if(y{name}.p[0]!=11 || y{name}.x!=8 || y{name}.f!=4.5f || x{name}.x!=7) return {w};']
    text='\n'.join(decl)+'\n'
    (d/'owner.c').write_text(text+'\n'.join(owner))
    (d/'companion.c').write_text(text+'\nint main(void){\n'+'\n'.join(checks)+'\nreturn 0;}')
    for a,b in [('host','kcc'),('kcc','host')]:
        object_file(d/'owner.c',d/'owner.o',a); object_file(d/'companion.c',d/'companion.o',b)
        run([HOST,d/'owner.o',d/'companion.o','-o',d/'test'])
        try: run([d/'test'])
        except AssertionError as e: raise AssertionError(f'prefix {prefix} {a}/{b}: {e}') from e

def main():
    (ROOT/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='unnamed-abi-',dir=ROOT/'build') as tmp:
        d=Path(tmp)
        (d/'owner.c').write_text(OWNER); (d/'companion.c').write_text(COMPANION)
        for a,b in [('host','host'),('host','kcc'),('kcc','host'),('kcc','kcc')]:
            object_file(d/'owner.c',d/'owner.o',a); object_file(d/'companion.c',d/'companion.o',b)
            run([HOST,d/'owner.o',d/'companion.o','-o',d/'test']); run([d/'test'])
        for typ in ('float','double'): matrix(d,typ)
        for prefix in range(1,8): matrix_integer(d,prefix)
    print('unnamed-field aggregates: four host/KCC combinations and 288 floating and mixed layouts in both directions passed')

if __name__=='__main__': main()

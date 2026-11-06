"""Signed, unsigned and plain char bit-fields on x86-64 SysV."""
from pathlib import Path
import subprocess
import tempfile
from test_bit_fields import ROOT, HOST, KCC, object_file, run

DECL = r'''
struct C { unsigned char a:4; signed char b:5; char c:3; unsigned char :3; _Bool flag:1; char end; };
union U { unsigned char c:3; float f; };
struct Barrier { unsigned a:3; unsigned char :0; unsigned b:4; char end; };
extern struct C g; extern union U u; extern struct Barrier barrier;
int inspect(void); struct C change(struct C x); union U reset(union U x);
'''
OWNER = DECL + r'''
struct C g={15,-7,-2,1,77}; union U u={.c=6}; struct Barrier barrier={5,9,10};
int inspect(void){return g.a==15 && g.b==-7 && g.c==-2 && g.flag==1 && g.end==77 && u.c==6;}
struct C change(struct C x){x.a+=2; x.b-=1; x.c=-4; x.flag=0; return x;}
union U reset(union U x){x.c=3; return x;}
'''
COMPANION = DECL + r'''
int main(void){
 struct C a={7,-5,-1,1,66}, b=change(a); union U v=reset(u);
 if(!inspect()||sizeof(struct C)!=4||_Alignof(struct C)!=1) return 1;
 if(b.a!=9||b.b!=-6||b.c!=-4||b.flag!=0||b.end!=66||a.b!=-5||v.c!=3) return 2;
 if((a.a=18)!=2 || (a.b=-20)!=12 || a.c!=-1 || a.flag!=1) return 3;
 if(a.a++!=2 || a.a!=3 || ++a.c!=0 || _Generic(+a.a,int:1,default:0)!=1) return 4;
 if((char*)&barrier.end-(char*)&barrier!=2 || barrier.a!=5 || barrier.b!=9) return 5;
 return 0;
}
'''

def matrix(d,prefix):
    decl, owner, checks = [], [], []
    for width in range(1,9):
        for signed in (False,True):
            name=f'b{prefix}_{width}_{"s" if signed else "u"}'; typ='signed char' if signed else 'unsigned char'
            initial='-1' if signed else '1'
            decl += [f'struct {name} {{ unsigned p:{prefix}; {typ} a:{width}; unsigned char b:5; char end; }};',
                     f'extern struct {name} v{name}; int size_{name}(void); struct {name} f{name}(struct {name} x);']
            owner += [f'struct {name} v{name}={{{(1<<prefix)-1},{initial},17,77}};',
                      f'int size_{name}(void){{return sizeof(struct {name});}}',
                      f'struct {name} f{name}(struct {name} x){{x.a=0; x.b=3; return x;}}']
            checks += [f'struct {name} r{name}=f{name}(v{name});',
                       f'if(size_{name}()!=sizeof(struct {name})||v{name}.a!={initial}||r{name}.a!=0||r{name}.b!=3||r{name}.p!={(1<<prefix)-1}||r{name}.end!=77) return {width};']
    text='\n'.join(decl)+'\n'; (d/'owner.c').write_text(text+'\n'.join(owner))
    (d/'companion.c').write_text(text+'\nint main(void){\n'+'\n'.join(checks)+'\nreturn 0;}')
    for a,b in [('host','kcc'),('kcc','host')]:
        object_file(d/'owner.c',d/'owner.o',a); object_file(d/'companion.c',d/'companion.o',b)
        run([HOST,d/'owner.o',d/'companion.o','-o',d/'test'])
        try: run([d/'test'])
        except AssertionError as e: raise AssertionError(f'prefix {prefix} {a}/{b}: {e}') from e

def main():
    (ROOT/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='char-fields-',dir=ROOT/'build') as tmp:
        d=Path(tmp); (d/'owner.c').write_text(OWNER); (d/'companion.c').write_text(COMPANION)
        for a,b in [('host','host'),('host','kcc'),('kcc','host'),('kcc','kcc')]:
            object_file(d/'owner.c',d/'owner.o',a); object_file(d/'companion.c',d/'companion.o',b)
            run([HOST,d/'owner.o',d/'companion.o','-o',d/'test']); run([d/'test'])
        for prefix in range(1,8): matrix(d,prefix)
        for source in ['struct S { signed char a:9; };', 'struct S { unsigned char :9; int x; };', 'struct S { char a:0; };', 'struct S { volatile char a:1; };', 'struct S { char :0; int x; }; struct S f(struct S x){return x;}']:
            (d/'reject.c').write_text(source); r=subprocess.run([str(KCC),str(d/'reject.c')],text=True,capture_output=True)
            diagnostic='aggregate ABI unsupported' if 'f(struct' in source else 'bit-field'
            if r.returncode==0 or r.stdout or diagnostic not in r.stderr: raise AssertionError((source,r.returncode,r.stderr,r.stdout))
    print('char bit-fields: four host/KCC combinations and 112 by-value layouts in both directions passed')

if __name__=='__main__': main()

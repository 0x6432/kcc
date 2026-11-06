"""Bounded long-base bit-fields: SysV layout, values and host ABI."""
from pathlib import Path
import subprocess
import tempfile
from test_bit_fields import ROOT, HOST, KCC, object_file, run

DECL = r'''
struct S { unsigned p:7; signed long a:31; unsigned long long b:29; char end; };
struct Barrier { unsigned a:3; unsigned long :0; unsigned b:4; char end; };
extern struct S global; extern struct Barrier barrier; extern int calls;
struct S *once(struct S *p); struct S change(struct S x); int inspect(void);
'''
OWNER = DECL + r'''
struct S global={99,-123456789,400000000,77}; struct Barrier barrier={5,9,10}; int calls;
struct S *once(struct S *p){calls++;return p;}
int inspect(void){return global.p==99 && global.a==-123456789 && global.b==400000000 && global.end==77;}
struct S change(struct S x){x.a+=10; x.b-=9; return x;}
'''
COMPANION = DECL + r'''
int main(void){
 struct S a={3,-100000001,500000000,66}, b=change(a);
 if(!inspect() || b.a!=-99999991 || b.b!=499999991 || b.p!=3 || b.end!=66) return 1;
 if((long)global.a!=-123456789L || (unsigned long long)global.b!=400000000ULL) return 2;
 if(_Generic(+global.a,int:1,default:0)!=1 || _Generic(+global.b,int:1,default:0)!=1) return 3;
 calls=0; if((once(&global)->a=-100)!=-100 || calls!=1 || global.b!=400000000) return 4;
 calls=0; if(once(&global)->b++!=400000000 || calls!=1 || global.b!=400000001) return 5;
 calls=0; if((once(&global)->a+=7)!=-93 || calls!=1 || global.a!=-93) return 6;
 if((char*)&barrier.end-(char*)&barrier!=9 || barrier.a!=5 || barrier.b!=9) return 7;
 if((global.b=0x180000001ULL)!=1 || global.b!=1 || global.a!=-93 || global.p!=99) return 8;
 if((global.a=1073741824L)!=-1073741824L || global.a!=-1073741824L || global.b!=1) return 9;
 if(++global.a!=-1073741823L || global.a--!=-1073741823L || global.a!=-1073741824L) return 10;
 return 0;
}
'''

def matrix(d, prefix, kinds):
    decl, owner, checks = [], [], []
    for width in range(1,32):
        for kind, typ in kinds:
            name=f'b{prefix}_{width}_{kind}'; signed=kind.startswith('s')
            initial='-1' if signed else '0'; updated='0' if signed else '1'
            decl += [f'struct {name} {{ unsigned p:{prefix}; {typ} a:{width}; unsigned b:3; char end; }};',
                     f'extern struct {name} v{name}; int size_{name}(void); struct {name} f{name}(struct {name} x);']
            owner += [f'struct {name} v{name}={{{(1<<prefix)-1},{initial},3,77}};',
                      f'int size_{name}(void){{return sizeof(struct {name});}}',
                      f'struct {name} f{name}(struct {name} x){{x.a={updated}; x.b=6; return x;}}']
            checks += [f'struct {name} r{name}=f{name}(v{name});',
                       f'if(size_{name}()!=sizeof(struct {name}) || v{name}.a!={initial} || r{name}.a!={updated} || r{name}.b!=6 || r{name}.p!={(1<<prefix)-1} || r{name}.end!=77) return 1;']
    text='\n'.join(decl)+'\n'; (d/'owner.c').write_text(text+'\n'.join(owner));
    (d/'companion.c').write_text(text+'\nint main(void){\n'+'\n'.join(checks)+'\nreturn 0;}')
    for a,b in [('host','kcc'),('kcc','host')]:
        object_file(d/'owner.c',d/'owner.o',a); object_file(d/'companion.c',d/'companion.o',b)
        run([HOST,d/'owner.o',d/'companion.o','-o',d/'test']); run([d/'test'])

def matrix_unnamed(d, typ, field):
    decl, owner, checks = [], [], []
    for width in range(1,32):
        name=f'n{typ}_{field}_{width}'
        field_type = 'unsigned long' if field == 'long' else 'unsigned long long'
        decl += [f'struct {name} {{ {typ} x; {field_type} :{width}; float y; }};',
                 f'struct {name} f{name}(struct {name} x);']
        owner += [f'struct {name} f{name}(struct {name} x){{x.x+=1; x.y+=2; return x;}}']
        checks += [f'struct {name} a{name}={{1.5,2.5f}}, b{name}=f{name}(a{name});',
                   f'if(b{name}.x!=2.5 || b{name}.y!=4.5f || a{name}.y!=2.5f) return 1;']
    text='\n'.join(decl)+'\n'; (d/'owner.c').write_text(text+'\n'.join(owner))
    (d/'companion.c').write_text(text+'\nint main(void){\n'+'\n'.join(checks)+'\nreturn 0;}')
    for a,b in [('host','kcc'),('kcc','host')]:
        object_file(d/'owner.c',d/'owner.o',a); object_file(d/'companion.c',d/'companion.o',b)
        run([HOST,d/'owner.o',d/'companion.o','-o',d/'test']); run([d/'test'])

def main():
    (ROOT/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='long-fields-',dir=ROOT/'build') as tmp:
        d=Path(tmp); (d/'owner.c').write_text(OWNER); (d/'companion.c').write_text(COMPANION)
        for a,b in [('host','host'),('host','kcc'),('kcc','host'),('kcc','kcc')]:
            object_file(d/'owner.c',d/'owner.o',a); object_file(d/'companion.c',d/'companion.o',b)
            run([HOST,d/'owner.o',d/'companion.o','-o',d/'test']); run([d/'test'])
        for prefix in range(1,8):
            for kinds in ([('sl','signed long'),('ul','unsigned long')],
                          [('sll','signed long long'),('ull','unsigned long long')]):
                matrix(d,prefix,kinds)
        for typ in ('float','double'):
            for field in ('long','llong'): matrix_unnamed(d,typ,field)
        (d/'formerly-unsupported.c').write_text('struct S { unsigned long x:3; }; struct S s; int main(void){return (struct S){.x=2}.x!=2;}')
        object_file(d/'formerly-unsupported.c',d/'formerly-unsupported.o','kcc'); run([HOST,d/'formerly-unsupported.o','-o',d/'formerly-unsupported']); run([d/'formerly-unsupported'])
        for source in ['struct S { long x:32; };', 'struct S { unsigned long long x:64; };',
                       'struct S { long :32; int x; };', 'struct S { long x:0; };',
                       'struct S { volatile long x:1; };',
                       'struct S { long :0; int x; }; struct S f(struct S x){return x;}']:
            (d/'reject.c').write_text(source); r=subprocess.run([str(KCC),str(d/'reject.c')],text=True,capture_output=True)
            diagnostic='aggregate ABI unsupported' if 'f(struct' in source else 'bit-field'
            if r.returncode==0 or r.stdout or diagnostic not in r.stderr: raise AssertionError((source,r.returncode,r.stderr,r.stdout))
    print('long-base bit-fields 1–31: four host/KCC combinations and 868 named and 124 unnamed by-value layouts in both directions passed')

if __name__=='__main__': main()

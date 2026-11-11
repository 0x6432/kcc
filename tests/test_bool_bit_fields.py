"""Boolean bit-fields: representation, conversions, initialization and SysV ABI."""
from pathlib import Path
import subprocess
import tempfile
from test_bit_fields import ROOT, HOST, KCC, object_file, run

DECL = r'''
struct S { char c; _Bool a:1, b:1; unsigned x:5; _Bool z:1; char end; };
struct F { _Bool :1; _Bool a:1; unsigned :2; _Bool b:1; };
struct Nine { _Bool a:1,b:1,c:1,d:1,e:1,f:1,g:1,h:1,i:1; char end; };
struct Mixed { double d; _Bool a:1,b:1; float f; };
struct Barrier { unsigned a:3; _Bool :0; unsigned b:4; char end; };
union U { _Bool b:1; char c; };
extern struct S s; extern struct F f; extern struct Barrier bar; extern union U u;
extern struct Nine nine;
int inspect(void); struct S change(struct S x); struct F changep(struct F x); struct Mixed mix(struct Mixed x);
'''
OWNER = DECL + r'''
struct S s={9, 2, 0, 27, -3, 77}; struct F f={2,0};
struct Barrier bar={5, 9, 10}; union U u={.b=9};
struct Nine nine={1,0,1,0,1,0,1,0,1,77};
int inspect(void){return s.c==9 && s.a==1 && s.b==0 && s.x==27 && s.z==1 && s.end==77 && f.a==1 && f.b==0 && bar.a==5 && bar.b==9 && bar.end==10 && u.b==1;}
struct S change(struct S x){x.a=0; x.b=2; x.x+=2; return x;}
struct F changep(struct F x){x.a=0; x.b=4; return x;}
struct Mixed mix(struct Mixed x){x.d+=1; x.a=1; x.b=0; x.f+=2; return x;}
'''
COMPANION = DECL + r'''
int main(void){
 struct S q={1,0,1,9,0,3}, r=change(q); struct F z={1,0}, y=changep(z);
 struct Mixed m={1.5,0,1,2.5f}, n=mix(m);
 if(!inspect()) return 1;
 if(sizeof(struct S)!=4 || _Alignof(struct S)!=4 || sizeof(struct F)!=1 || _Alignof(struct F)!=1 || sizeof(union U)!=1) return 2;
 if(r.c!=1 || r.a!=0 || r.b!=1 || r.x!=11 || r.z!=0 || r.end!=3 || q.b!=1) return 3;
 if(y.a!=0||y.b!=1||z.a!=1||z.b!=0) return 4;
 if((q.a=2)!=1 || q.a!=1 || q.x!=9) return 5;
 if(q.a++!=1 || q.a!=1 || --q.a!=0 || q.a!=0) return 6;
 q.a+=5; if(q.a!=1 || q.b!=1 || q.x!=9 || q.end!=3) return 7;
 if(_Generic(+q.a,int:1,default:0)!=1) return 8;
 if((char*)&bar.end-(char*)&bar!=2 || bar.a!=5||bar.b!=9) return 9;
 if(sizeof(struct Nine)!=3||nine.a!=1||nine.b!=0||nine.h!=0||nine.i!=1||nine.end!=77) return 10;
 nine.i=0; nine.h=1; if(nine.g!=1||nine.h!=1||nine.i!=0||nine.end!=77) return 11;
 if(n.d!=2.5||n.a!=1||n.b!=0||n.f!=4.5f||m.a!=0) return 12;
 return 0;
}
'''

def main():
    (ROOT/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bool-fields-',dir=ROOT/'build') as tmp:
        d=Path(tmp)
        (d/'owner.c').write_text(OWNER); (d/'companion.c').write_text(COMPANION)
        for a,b in [('host','host'),('host','kcc'),('kcc','host'),('kcc','kcc')]:
            object_file(d/'owner.c',d/'owner.o',a); object_file(d/'companion.c',d/'companion.o',b)
            run([HOST,d/'owner.o',d/'companion.o','-o',d/'test']); run([d/'test'])
        (d/'keyword.c').write_text('struct B { bool a:1; bool b:1; }; struct B g={true,false}; int main(void){g.b=99;return !(g.a && g.b);}')
        object_file(d/'keyword.c',d/'keyword.o','kcc'); run([HOST,d/'keyword.o','-o',d/'keyword']); run([d/'keyword'])
        for source in ['struct S { _Bool x:2; };', 'struct S { _Bool x:0; };']:
            (d/'reject.c').write_text(source)
            result=subprocess.run([str(KCC),str(d/'reject.c')],text=True,capture_output=True)
            diagnostic='aggregate ABI unsupported' if 'f(struct' in source else 'bit-field'
            if result.returncode==0 or result.stdout or diagnostic not in result.stderr:
                raise AssertionError((source,result.returncode,result.stderr,result.stdout))
    print('boolean bit-fields: four host/KCC combinations, conversions, ABI and rejections passed')

if __name__=='__main__': main()

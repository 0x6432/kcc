"""Unnamed int bit-fields: SysV layout, initialization and pointer interop."""
from pathlib import Path
import tempfile
import subprocess
from test_bit_fields import ROOT, HOST, KCC, object_file, run

DECL = r'''
struct A { char c; unsigned :3; char d; };
struct B { char c; unsigned :0; char d; };
struct C { unsigned a:3; unsigned :0; char d; };
struct D { char c; unsigned :32; char d; };
struct E { unsigned :3, a:4, :5, b:7, :0; char end; };
union U { unsigned :32; char c; };
struct Nested { unsigned :2; struct { unsigned :0; int x:5; }; unsigned :3; int y; };
extern struct A a; extern struct B b; extern struct C c; extern struct D d;
extern struct E e; extern union U u; extern struct Nested n;
int inspect(void); int sizes(int i); int offsets(int i);
'''
OWNER = DECL + r'''
struct A a={11,12}; struct B b={13,14}; struct C c={5,15}; struct D d={16,17};
struct E e={9,81,18}; union U u={19}; struct Nested n={.x=-6,.y=20};
int inspect(void) { return a.c==11 && a.d==12 && b.c==13 && b.d==14 && c.a==5 && c.d==15 && d.c==16 && d.d==17 && e.a==9 && e.b==81 && e.end==18 && u.c==19 && n.x==-6 && n.y==20; }
int sizes(int i) { if(i==0)return sizeof(struct A); if(i==1)return sizeof(struct B); if(i==2)return sizeof(struct C); if(i==3)return sizeof(struct D); if(i==4)return sizeof(struct E); if(i==5)return sizeof(union U); return sizeof(struct Nested); }
int offsets(int i) { if(i==0)return (char*)&a.d-(char*)&a; if(i==1)return (char*)&b.d-(char*)&b; if(i==2)return (char*)&c.d-(char*)&c; if(i==3)return (char*)&d.d-(char*)&d; if(i==4)return (char*)&e.end-(char*)&e; return (char*)&n.y-(char*)&n; }
'''
COMPANION = DECL + r'''
int main(void) {
 struct E local={7, 91, 25}; struct E designated={.b=100,.a=8,.end=30};
 if (!inspect()) return 1;
 if (sizes(0)!=sizeof(struct A)||sizes(1)!=sizeof(struct B)||sizes(2)!=sizeof(struct C)||sizes(3)!=sizeof(struct D)||sizes(4)!=sizeof(struct E)||sizes(5)!=sizeof(union U)||sizes(6)!=sizeof(struct Nested)) return 2;
 if (offsets(0)!=(char*)&a.d-(char*)&a||offsets(1)!=(char*)&b.d-(char*)&b||offsets(2)!=(char*)&c.d-(char*)&c||offsets(3)!=(char*)&d.d-(char*)&d||offsets(4)!=(char*)&e.end-(char*)&e||offsets(5)!=(char*)&n.y-(char*)&n) return 3;
 if (_Alignof(struct A)!=1||_Alignof(struct B)!=1||_Alignof(struct C)!=4||_Alignof(struct D)!=1||_Alignof(union U)!=1) return 4;
 if (local.a!=7||local.b!=91||local.end!=25||designated.a!=8||designated.b!=100||designated.end!=30) return 5;
 local.b=3; if(local.a!=7||local.b!=3||local.end!=25) return 6;
 return 0;
}
'''

def matrix_batch(d, prefix):
    declarations, owner, checks = [], [], []
    for w in range(33):
        n = f'f{prefix}_{w}'
        declarations += [f'struct {n} {{ unsigned pre:{prefix}; unsigned :{w}; unsigned post:5; char tail; }};',
                         f'extern struct {n} {n}; int size_{n}(void); int tail_{n}(void); int get_{n}(void);']
        owner += [f'struct {n} {n} = {{ {(1<<prefix)-1}, 19, 67 }};',
                  f'int size_{n}(void) {{ return sizeof(struct {n}); }}',
                  f'int tail_{n}(void) {{ return (char*)&{n}.tail-(char*)&{n}; }}',
                  f'int get_{n}(void) {{ return {n}.post; }}']
        checks += [f'if (size_{n}()!=sizeof(struct {n}) || tail_{n}()!=(char*)&{n}.tail-(char*)&{n} || {n}.pre!={(1<<prefix)-1} || {n}.post!=19 || {n}.tail!=67) return 1;',
                   f'{n}.post=7; if(get_{n}()!=7 || {n}.pre!={(1<<prefix)-1} || {n}.tail!=67) return 2;']
    text='\n'.join(declarations)+'\n'
    (d/'owner.c').write_text(text+'\n'.join(owner)+'\n')
    blocks=[]
    for i in range(0,len(checks),32):
        blocks.append('int check%d(void){\n%s\nreturn 0;}' % (i, '\n'.join(checks[i:i+32])))
    (d/'companion.c').write_text(text+'\n'.join(blocks)+'\nint main(void){'+''.join(f'if(check{i}()) return 1;' for i in range(0,len(checks),32))+'return 0;}\n')
    for a,b in [('host','kcc'),('kcc','host')]:
        object_file(d/'owner.c',d/'owner.o',a); object_file(d/'companion.c',d/'companion.o',b)
        run([HOST,d/'owner.o',d/'companion.o','-o',d/'test']); run([d/'test'])

def main():
    (ROOT/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='unnamed-fields-',dir=ROOT/'build') as tmp:
        d=Path(tmp)
        (d/'owner.c').write_text(OWNER); (d/'companion.c').write_text(COMPANION)
        for a,b in [('host','host'),('host','kcc'),('kcc','host'),('kcc','kcc')]:
            object_file(d/'owner.c',d/'owner.o',a); object_file(d/'companion.c',d/'companion.o',b)
            run([HOST,d/'owner.o',d/'companion.o','-o',d/'test']); run([d/'test'])
        for prefix in range(1,8):
            matrix_batch(d, prefix)
        (d/"assign.c").write_text("struct S { const int :1; int x; }; void f(void) { struct S a={1}, b={2}; a=b; }\n")
        object_file(d/"assign.c", d/"assign.o", "kcc")
        for source in [
            'struct S { int x:0; char c; };',
            'struct S { unsigned :33; int x; };',
            'struct S { unsigned :-1; int x; };',
            'struct S { _Bool :2; int x; };',
        ]:
            (d/'reject.c').write_text(source)
            result = subprocess.run([str(KCC), str(d/'reject.c')], text=True, capture_output=True)
            diagnostic = 'aggregate ABI unsupported' if 'f(struct' in source else 'bit-field'
            if result.returncode == 0 or diagnostic not in result.stderr or result.stdout:
                raise AssertionError(f'{source}: rc={result.returncode}\n{result.stderr}\n{result.stdout}')
    print('unnamed fields: four host/KCC combinations and 231-layout bidirectional matrix passed')

if __name__=='__main__': main()

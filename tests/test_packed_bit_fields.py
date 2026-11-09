"""Non-byte-start int fields: QBE/host layout, RMW, initializers and ABI."""
from pathlib import Path
import subprocess
import tempfile
from test_bit_fields import ROOT, HOST, object_file, run, KCC

DECL = r'''
struct S { unsigned a:3; signed b:4; unsigned c:8; signed d:12; char tail; };
struct T { unsigned x:3, y:8; };
struct U { unsigned x:12, y:16; };
struct Deep { unsigned a:23, b:9; signed c:20; unsigned d:11; char tail; };
struct Large { long pad[3]; unsigned a:3, b:6; };
struct Promoted { char head; struct { unsigned a:3; signed b:4; }; char tail; };
struct ABI { double d; unsigned a:3; signed b:5; };
extern struct S global; extern struct T t; extern struct U u; extern struct Deep deep; extern struct Promoted promoted; extern int calls;
struct S *once(struct S *p);
struct ABI transform(struct ABI v);
struct Large large_transform(struct Large v);
int foreign(struct S *p);
'''
OWNER = DECL + r'''
struct S global = { .a={5}, .b={-3}, .c=201, .d=-1000, .tail=77, .a=6 };
struct T t = { 5, 199 }; struct U u = { 3000, 60000 };
struct Deep deep = { 7000000, 400, -400000, 1700, 89 };
struct Promoted promoted = { .head=9, .a=5, .b=-4, .tail=8 };
struct Large large_transform(struct Large v) { v.a++; v.b+=2; v.pad[2]+=3; return v; }
int calls; struct S *once(struct S *p) { calls++; return p; }
struct ABI transform(struct ABI v) { v.a+=1; v.b-=1; v.d+=2; return v; }
int foreign(struct S *p) { if(p->a!=3 || p->b!=-5 || p->c!=253 || p->d!=-999 || p->tail!=88) return 0;
 p->b=-7; p->c=17; return 1; }
'''
COMPANION = DECL + r'''
int main(void) {
 struct S p = { .a={3}, .b={-5}, .c={253}, .d={-999}, .tail=88 };
 struct S copy = p; struct ABI v = { 4.0, 6, -8 }; struct ABI r = transform(v);
 struct Large large = {{1,2,3}, 5, 60}; struct Large lr=large_transform(large);
 if (sizeof(struct S)!=8 || _Alignof(struct S)!=4 || (char *)&p.tail-(char *)&p!=4) return 1;
 if (global.a!=6 || global.b!=-3 || global.c!=201 || global.d!=-1000 || global.tail!=77) return 2;
 if (t.x!=5 || t.y!=199 || u.x!=3000 || u.y!=60000) return 3;
 if (!foreign(&p) || p.a!=3 || p.b!=-7 || p.c!=17 || p.d!=-999 || p.tail!=88 || copy.b!=-5) return 4;
 calls=0; if ((once(&p)->b=-2)!=-2 || calls!=1 || p.a!=3 || p.c!=17) return 5;
 calls=0; if (once(&p)->c++!=17 || calls!=1 || p.c!=18) return 6;
 calls=0; if ((once(&p)->b+=3)!=1 || calls!=1 || p.b!=1) return 7;
 if ((p.c=511)!=255 || p.a!=3 || p.b!=1 || p.d!=-999 || p.tail!=88) return 8;
 if (p.c-256>=0 || _Generic(+p.c, int: 1, default: 0)!=1) return 9;
 if (r.d!=6.0 || r.a!=7 || r.b!=-9 || v.b!=-8) return 10;
 if (deep.a!=7000000 || deep.b!=400 || deep.c!=-400000 || deep.d!=1700 || deep.tail!=89) return 11;
 deep.b=300; deep.c=-200000; if (deep.a!=7000000 || deep.b!=300 || deep.c!=-200000 || deep.d!=1700 || deep.tail!=89) return 12;
 if(lr.pad[0]!=1 || lr.pad[1]!=2 || lr.pad[2]!=6 || lr.a!=6 || lr.b!=62 || large.b!=60) return 13;
 if(promoted.head!=9 || promoted.a!=5 || promoted.b!=-4 || promoted.tail!=8) return 14;
 promoted.b=-2; if(promoted.a!=5 || promoted.b!=-2 || promoted.head!=9 || promoted.tail!=8) return 15;
 return 0;
}
'''

LOCAL = r'''
#include <stdarg.h>
struct S { unsigned a:3, b:4, c:9; signed d:7; char end; };
struct AbiFormerRejection { unsigned a:9,b:4; };
struct AbiFormerRejection abi_copy(struct AbiFormerRejection s) { s.b++; return s; }
struct S g = { .a={3}, .b={5}, .c={400}, .d={-20}, .a={7}, .end=9 };
struct S array[2] = { [1]={.b=9, .c=300}, [0]={.a=7, .d=-4} };
union V { struct S s; unsigned raw; };
union V v = { .s={1,2,3,-4,5} };
struct Flex { unsigned a:3, b:4; char data[]; };
int var(int n, ...) { va_list ap; va_start(ap,n); int r=va_arg(ap,int); va_end(ap); return r; }
int main(void) {
 struct S s = { .a={3}, .b={5}, .c={400}, .d={-20}, .a={7}, .end=9 };
 struct AbiFormerRejection abi={300,7}, result=abi_copy(abi);
 if(result.a!=300 || result.b!=8 || abi.b!=7) return 8;
 if (g.a!=7 || g.b!=5 || g.c!=400 || g.d!=-20 || g.end!=9) return 1;
 if (s.a!=7 || s.b!=5 || s.c!=400 || s.d!=-20 || s.end!=9) return 2;
 if (v.s.a!=1 || v.s.b!=2 || v.s.c!=3 || v.s.d!=-4 || v.s.end!=5) return 4;
 if(array[0].a!=7 || array[0].b!=0 || array[0].d!=-4 || array[1].a!=0 || array[1].b!=9 || array[1].c!=300) return 7;
 struct Flex f={ .a=6, .b=10 };
 if (sizeof(struct Flex)!=4 || (char *)f.data-(char *)&f!=1 || f.a!=6 || f.b!=10) return 5;
 _BitInt(32) bi=10;
 if (bi+s.b!=15 || var(0,s.b)!=5 || var(0,s.d)!=-20) return 6;
 s.b=2; if(s.a!=7 || s.b!=2 || s.c!=400 || s.d!=-20 || s.end!=9) return 3;
 return 0;
}
'''
REJECT = [
 ('struct S { unsigned a:3,b:4; } s; unsigned *p=&s.b;', 'bit-field'),
 ('struct S { unsigned a:3,b:4; } s; int a[sizeof(s.b)];', 'bit-field'),
 ('struct S { unsigned a:3,b:4; } s; typeof(s.b) x;', 'bit-field'),
 ('struct S { unsigned a:3,b:4; }; int a[__kcc_offsetof(struct S,b)];', 'bit-field'),
 ('struct S { unsigned a:3; const unsigned b:4; } s; void f(void){s.b=2;}', 'modifiable lvalue'),
 ('struct S { unsigned a:3,b:4; } s; int f(void){return _Generic(s.b,int:1,default:0);}', 'bit-field'),
 ('struct S { _BitInt(32) a:33; unsigned b:4; };', 'bit-field'),
 # A whole-record copy followed by a partial bit write is not representable by the bounded plan.
 ('struct S { unsigned a:3,b:4; }; struct O { struct S s; }; int f(struct S p) { struct O x = { .s=p, .s.b=3 }; return x.s.a; }', 'initializer'),
]

def matrix(d, signed, offsets):
    decl, owner, check = [], [], []
    typ = 'signed' if signed else 'unsigned'
    for off in offsets:
        for width in range(1, 33):
            name = f'f{off}_{width}'
            decl += [f'struct {name} {{ unsigned pre:{off}; {typ} x:{width}; char post; }};',
                     f'extern struct {name} {name}; extern int size_{name};',
                     f'{typ} int read_{name}(void);']
            v = '-1' if signed else f'{(1 << width)-1}U'
            changed = ('0' if width == 1 else '-2') if signed else f'{((1 << width)-1)//2}U'
            owner += [f'struct {name} {name} = {{ {(1 << off)-1}, {v}, 67 }};',
                      f'int size_{name}=sizeof(struct {name});',
                      f'{typ} int read_{name}(void) {{return {name}.x;}}']
            check += [f'if (size_{name}!=sizeof(struct {name}) || {name}.pre!={(1 << off)-1} || {name}.x!=({v}) || {name}.post!=67) return 1;',
                      f'{name}.x={changed}; if(read_{name}()!=({changed}) || {name}.pre!={(1 << off)-1} || {name}.post!=67) return 2;']
    text = '\n'.join(decl)+'\n'
    (d/'matrix-owner.c').write_text(text+'\n'.join(owner)+'\n')
    # Keep function and expression resources within the existing limits.
    blocks = []
    for i in range(0, len(check), 32):
        blocks.append('int check%d(void){\n%s\nreturn 0;}' % (i, '\n'.join(check[i:i+32])))
    main = 'int main(void){' + ''.join(f'if(check{i}()) return 1;' for i in range(0,len(check),32)) + 'return 0;}'
    (d/'matrix-companion.c').write_text(text+'\n'.join(blocks)+'\n'+main+'\n')
    for a,b in [('host','kcc'),('kcc','host')]:
        object_file(d/'matrix-owner.c',d/'matrix-owner.o',a)
        object_file(d/'matrix-companion.c',d/'matrix-companion.o',b)
        run([HOST,d/'matrix-owner.o',d/'matrix-companion.o','-o',d/'matrix'])
        run([d/'matrix'])

def main():
    (ROOT/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='packed-fields-',dir=ROOT/'build') as tmp:
        d=Path(tmp)
        (d/'owner.c').write_text(OWNER); (d/'companion.c').write_text(COMPANION)
        for a,b in [('host','host'),('host','kcc'),('kcc','host'),('kcc','kcc')]:
            object_file(d/'owner.c',d/'owner.o',a); object_file(d/'companion.c',d/'companion.o',b)
            run([HOST,d/'owner.o',d/'companion.o','-o',d/'test']); run([d/'test'])
        for signed in (False, True):
            for offsets in (range(1, 3), range(3, 5), range(5, 7), range(7, 8)):
                matrix(d, signed, offsets)
        (d/'local.c').write_text(LOCAL); object_file(d/'local.c',d/'local.o','kcc')
        run([HOST,d/'local.o','-o',d/'local']); run([d/'local'])
        for i,(source,msg) in enumerate(REJECT):
            path=d/f'reject{i}.c'; path.write_text(source)
            r=subprocess.run([str(KCC),str(path)],text=True,capture_output=True)
            if r.returncode==0 or r.stdout or msg not in r.stderr:
                raise AssertionError((source,r.returncode,r.stdout,r.stderr))
    print('packed fields: four interop combinations, 448 layouts in both directions, initializer and rejection tests passed')

if __name__=='__main__': main()

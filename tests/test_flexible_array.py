"""Bounded flexible array layout, runtime and constraints."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
kcc = Path(os.environ.get('KCC', root / 'build/kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')
source = r'''
struct Packet { int n; char tag; long items[]; };
_Static_assert(sizeof(struct Packet)==8, "size");
_Static_assert(alignof(struct Packet)==8, "alignment");
struct Packet zero={1,2};
struct Promoted { struct { int n; }; long items[]; static_assert(1); };
static_assert(sizeof(struct Promoted)==8);
static_assert(alignof(struct Promoted)==8);
long promoted_read(struct Promoted *p) { return p->items[p->n]; }
struct Nested { union { struct { int n; }; long pad; }; long items[]; static_assert(1); };
static_assert(sizeof(struct Nested)==8 && alignof(struct Nested)==8);
long read_item(struct Packet *p) { return p->items[1]; }
void write_item(struct Packet *p, long x) { p->items[2]=x; }
long offset(struct Packet *p) { return (char *)p->items-(char *)p; }
'''
harness = r'''
#include <stdlib.h>
struct Packet { int n; char tag; long items[]; };
struct Promoted { struct { int n; }; long items[]; };
long promoted_read(struct Promoted *);
extern struct Packet zero;
long read_item(struct Packet *); void write_item(struct Packet *,long); long offset(struct Packet *);
int main(void) {
 struct Packet *p=malloc(sizeof(*p)+3*sizeof(long));
 if(!p) return 1;
 p->items[1]=42; write_item(p,73);
 if(sizeof(*p)!=8 || offset(p)!=8 || read_item(p)!=42 || p->items[2]!=73) return 2;
 if(zero.n!=1 || zero.tag!=2) return 3;
 free(p);
 struct Promoted *q=malloc(sizeof(*q)+2*sizeof(long));
 if (!q) return 4;
 q->n=1; q->items[1]=17;
 if (promoted_read(q)!=17) return 5;
 free(q); return 0;
}
'''
invalid = [
 'struct S { int a[]; };',
 'struct S { int a[]; static_assert(1); };',
 'struct S { int n; int a[]; static_assert(0); };',
 'struct S { int n; int a[]; int x; };',
 'struct S { struct { int n; }; int a[]; static_assert(1); int x; };',
 'union U { int n; int a[]; };',
 'struct S { int n; int a[]; }; struct S rows[2];',
 'struct S { int n; int a[]; }; struct Outer { struct S s; };',
 'struct S { int n; int a[]; }; struct S x={1,2};',
 'struct S { int n; int a[]; }; struct S x={.a={1}};',
 'struct S { int n; int a[]; }; int f(struct S *p){return sizeof p->a;}',
]
with tempfile.TemporaryDirectory(prefix='kcc-flex-') as directory:
    d = Path(directory)
    c = d/'input.c'
    def compile_text(text):
        c.write_text(text)
        return subprocess.run([str(kcc),str(c)],capture_output=True,text=True,timeout=15)
    result=compile_text(source)
    assert result.returncode==0 and not result.stderr, result.stderr
    if qbe:
        (d/'input.ssa').write_text(result.stdout)
        (d/'host.c').write_text(harness)
        subprocess.run([qbe,'-t','amd64_sysv','-o',str(d/'input.s'),str(d/'input.ssa')],check=True)
        subprocess.run([host,str(d/'input.s'),str(d/'host.c'),'-o',str(d/'test')],check=True)
        subprocess.run([str(d/'test')],check=True)
    for text in invalid:
        result=compile_text(text)
        assert result.returncode!=0 and result.stderr and not result.stdout, (text,result.stderr)

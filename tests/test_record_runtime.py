"""M16 independent record runtime and pointer-only host interop.

Unchanged originals; no M17 braces, M21 aggregate by-value calls/returns, or M22
bitfields/flexible arrays in executing owners. Read only the active union member;
member byte checks deliberately ignore padding. --native-only is NOT KCC PASS.
A KCC run requires --frozen-hash matching the selected compiler source checkout.
"""
import argparse
import copy
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import shutil
import tempfile

from test_integer_initializers import (
    KCC, HOST, QBE, invoke, producer, clang_style, native_diagnostics,
    harness_self_test, run_program, reject,
)
from test_null_initializers import native_compilers, compiler_selection_self_test
from test_address_offsets import OffsetRelocations, OffsetReference, diagnostic_flags
from test_thread_storage import TLS

ROOT = Path(__file__).resolve().parents[1]
R = ('struct I { short s; long l; }; '
     'struct R { char c; int x; int a[3]; int *p; int (*fn)(int); struct I in; }; ')
P = 'struct P { char c; int x; long y; }; '
U = 'union U { long l; int a[2]; struct I in; }; '
A = ('struct A { char lead; union { struct { short small; int promoted; }; '
     'long wide; }; int tail; }; ')
# Target ABI facts, checked independently by host offsetof/sizeof/_Alignof.
R_FIELDS = ((0, 1), (4, 4), (8, 12), (24, 8), (32, 8), (40, 2), (48, 8))


@dataclass
class Case:
    name: str
    owner: str
    companion: str
    # name -> (size, alignment, binding, defined member byte ranges); no padding.
    zeros: dict = field(default_factory=dict)
    references: dict = field(default_factory=dict)
    tls: tuple = ()
    pthread: bool = False
    compact_copy: bool = False


def main_for(declarations, expression):
    return declarations+' int main(void) { return ('+expression+')?42:1; }'


def fixtures():
    cases = []
    def local(name, header, body):
        cases.append(Case(name, header+'int test(void) { '+body+' }',
                          main_for('int test(void);', 'test()==42')))
    local('scalar nested array pointer function members', R,
          'struct R r; int v=39; r.c=3; r.x=4; r.a[0]=5; r.a[1]=6; r.a[2]=7; '
          'r.p=&v; r.fn=add; r.in.s=8; r.in.l=9; struct R *p=&r; '
          'return r.c==3 && p->x==4 && p->a[1]==6 && *p->p==39 && '
          'p->fn(40)==42 && p->in.s==8 && (&r)->in.l==9?42:1;')
    cases[-1].owner = 'int add(int x) { return x+2; } '+cases[-1].owner
    local('anonymous promoted member paths', A,
          'struct A a; struct A *p=&a; a.lead=1; a.small=2; p->promoted=40; a.tail=3; '
          'return a.promoted+a.small==42 && p->lead==1 && p->tail==3 && '
          '(char *)&p->promoted-(char *)p==12 && (char *)&a.tail-(char *)&a==16?42:1;')
    local('union active scalar copy initialization', 'struct I { short s; long l; }; '+U,
          'union U a; a.l=42; union U b=a; union U c; c=b; '
          'return b.l==42 && c.l==42?42:1;')
    local('union active nested member copy', 'struct I { short s; long l; }; '+U,
          'union U a; a.in.s=2; a.in.l=40; union U b; b=a; '
          'return b.in.s+b.in.l==42?42:1;')
    local('union active array copy', 'struct I { short s; long l; }; '+U,
          'union U a; a.a[0]=19; a.a[1]=23; union U b=a; '
          'return b.a[0]+b.a[1]==42?42:1;')
    local('copy assignment expression chain', P,
          'struct P a; a.c=2; a.x=40; a.y=9; struct P b; struct P c; '
          'struct P d=(c=b=a); a.x=1; '
          'return b.x==40 && c.x==40 && d.x+d.c==42 && d.y==9?42:1;')
    local('self assignment and disjoint copy', P,
          'struct P a; a.c=2; a.x=40; a.y=9; a=a; struct P b=a; b.x=3; '
          'return a.x+a.c==42 && b.x==3 && b.y==9?42:1;')
    local('conditional comma aggregate values', P,
          'struct P a; struct P b; a.c=2; a.x=40; a.y=9; b.c=1; b.x=3; b.y=4; '
          'int n=0; struct P c=(++n, n? a:b); struct P d=(n==0?a:b); '
          'return n==1 && c.c+c.x==42 && c.y==9 && d.x==3?42:1;')
    local('conditional selected side effects', P,
          'struct P a; struct P b; struct P c; a.c=2; a.x=40; a.y=7; '
          'b.c=1; b.x=3; b.y=8; int n=0; int m=0; '
          'c=1?(++n,a):(++m,b); '
          'return n==1 && m==0 && c.x+c.c==42?42:1;')
    local('member address once only postfix base', P,
          'struct P a[2]; a[0].x=40; a[1].x=7; struct P *p=a; '
          'int *q=&p++->x; *q+=2; return p==a+1 && a[0].x==42 && a[1].x==7?42:1;')
    local('member compound and update once only', P,
          'struct P a[3]; a[0].x=40; a[1].x=9; a[2].x=12; int i=0; '
          'a[i++].x+=2; int old=a[i++].x++; int now=++a[i++].x; '
          'return i==3 && old==9 && now==13 && a[0].x==42 && a[1].x==10?42:1;')
    local('copy destination and source once only', P,
          'struct P a[3]; a[0].c=2; a[0].x=40; a[0].y=9; int i=0; int j=1; '
          'struct P b=(a[j++]=a[i++]); '
          'return i==1 && j==2 && a[1].x==40 && b.c+b.x==42 && b.y==9?42:1;')
    local('struct array stride and commuted subscript', P,
          'struct P a[3]; struct P *p=a+1; p->x=40; 2[a].x=2; '
          'return (a+3)-a==3 && &p[1]==&a[2] && (char *)(a+1)-(char *)a==16 && '
          '(p-1)==a && p[0].x+p[1].x==42?42:1;')
    local('const member view and mutable pointer referent',
          P+'struct C { int *p; int a[2]; struct P nested; }; ',
          'int x=40; struct C c; c.p=&x; c.a[0]=2; c.nested.c=1; c.nested.x=3; c.nested.y=4; '
          'const struct C *p=&c; *p->p+=2; const int *q=p->a; '
          'return x==42 && *q==2 && p->nested.x==3?42:1;')
    local('nested record copy preserves pointer function array members', R,
          'struct R a; int v=19; a.c=2; a.x=40; a.a[0]=3; a.a[1]=4; a.a[2]=5; '
          'a.p=&v; a.fn=add; a.in.s=6; a.in.l=7; struct R b=a; struct R c; c=b; '
          'a.x=1; b.a[1]=8; return c.c+c.x==42 && c.a[0]==3 && c.a[1]==4 && '
          'c.a[2]==5 && c.p==&v && *c.p==19 && c.fn(40)==42 && '
          'c.in.s==6 && c.in.l==7?42:1;')
    cases[-1].owner='int add(int x) { return x+2; } '+cases[-1].owner
    local('aggregate assignment value member selection', P,
          'struct P a; struct P b; b.c=2; b.x=40; b.y=7; '
          'return (a=b).x==40 && (a=b).c==2 && a.y==7?42:1;')
    local('struct multidimensional array member chains', P,
          'struct P a[2][3]; a[1][2].x=40; a[0][1].x=2; '
          'struct P (*p)[3]=a; return p+2==a+2 && (&p[1][2])->x+1[p[0]].x==42?42:1;')
    # Host initializes every member before KCC reads. KCC writes every member
    # before host reads. No aggregate parameters/returns or padding comparison.
    interop_owner = R+'''int add(int x) { return x+2; }
int read_record(const struct R *p) { return p->c==3 && p->x==40 && p->a[0]==5 && p->a[1]==6 && p->a[2]==7 && *p->p==19 && p->fn(40)==42 && p->in.s==8 && p->in.l==9; }
void write_record(struct R *p, int *v) { p->c=4; p->x=0x12345678; p->a[0]=10; p->a[1]=11; p->a[2]=12; p->p=v; p->fn=add; p->in.s=13; p->in.l=14; }
int offsets(struct R *p) { return sizeof(*p)==56 && _Alignof(struct R)==8 && (char *)&p->x-(char *)p==4 && (char *)&p->a-(char *)p==8 && (char *)&p->p-(char *)p==24 && (char *)&p->fn-(char *)p==32 && (char *)&p->in.s-(char *)p==40 && (char *)&p->in.l-(char *)p==48; }
'''
    interop_host = R+'''
#include <stddef.h>
#include <string.h>
int read_record(const struct R *); void write_record(struct R *, int *); int offsets(struct R *); int add(int);
int hostadd(int x) { return x+2; }
int main(void) { struct R r; int v=19; r.c=3; r.x=40; r.a[0]=5; r.a[1]=6; r.a[2]=7; r.p=&v; r.fn=hostadd; r.in.s=8; r.in.l=9;
if(sizeof r!=56 || _Alignof(struct R)!=8 || offsetof(struct R,in.l)!=48 || !offsets(&r) || !read_record(&r)) return 1;
write_record(&r,&v); unsigned char *b=(unsigned char *)&r; int *saved; int (*fn)(int); memcpy(&saved,b+24,8); memcpy(&fn,b+32,8);
return r.c==4 && r.x==0x12345678 && b[4]==0x78 && b[5]==0x56 && b[6]==0x34 && b[7]==0x12 && r.a[0]==10 && r.a[1]==11 && r.a[2]==12 && saved==&v && fn==add && fn(40)==42 && r.in.s==13 && r.in.l==14?42:2; }
'''
    cases.append(Case('bidirectional host record layout bytes', interop_owner, interop_host))
    cases.append(Case('bidirectional host union active bytes',
        'union V { unsigned long l; unsigned char a[8]; }; '
        'int read_union(const union V *p) { return p->l==0x12345678UL; } '
        'void write_union(union V *p) { p->l=0x23456789UL; }',
        'union V { unsigned long l; unsigned char a[8]; }; '
        'int read_union(const union V *); void write_union(union V *); '
        'int main(void) { union V u; u.l=0x12345678UL; if(!read_union(&u)) return 1; '
        'write_union(&u); unsigned char *b=(unsigned char *)&u; '
        'return sizeof u==8 && _Alignof(union V)==8 && u.l==0x23456789UL && b[0]==0x89 && b[3]==0x23?42:2; }'))
    for storage, name in [('', 'file tentative'), ('static ', 'private tentative')]:
        cases.append(Case(name+' record zero', R+storage+'struct R target; '
            'struct R *slot(void) { return &target; }', R+
            main_for('struct R *slot(void);',
                'slot()->c==0 && slot()->x==0 && slot()->a[0]==0 && slot()->a[2]==0 && '
                'slot()->p==0 && slot()->fn==0 && slot()->in.s==0 && slot()->in.l==0'),
            {'target': (56, 8, not bool(storage), R_FIELDS)}))
    cases.append(Case('block static record persists', P+
        'struct P *slot(void) { static struct P target; return &target; }', P+
        'struct P *slot(void); int main(void) { struct P *p=slot(); '
        'if(p->c || p->x || p->y) return 1; p->x=42; '
        'return slot()==p && slot()->x==42?42:2; }',
        {None: (16, 8, False, ((0,1),(4,4),(8,8)))}))
    cases.append(Case('union zero first member', 'union V { long l; int a[2]; }; '
        'union V target; union V *slot(void) { return &target; }',
        'union V { long l; int a[2]; }; '+main_for('union V *slot(void);', 'slot()->l==0'),
        {'target': (8,8,True,((0,8),))}))
    # All pointer slots initialized individually, never by record braces.
    refs = {
        'px': (4, 'int *px=&target.x;'),
        'pxend': (8, 'int *pxend=&target.x+1;'),
        'pa': (16, 'int *pa=&target.a[2];'),
        'pend': (20, 'int *pend=target.a+3;'),
        'pp': (24, 'int **pp=&target.p;'),
        'pf': (32, 'int (**pf)(int)=&target.fn;'),
        'ps': (40, 'short *ps=&target.in.s;'),
        'pl': (48, 'long *pl=&target.in.l;'),
    }
    cases.append(Case('static record subobject addresses', R+'struct R target; '+
        ' '.join(x[1] for x in refs.values()), R+
        'extern struct R target; extern int *px,*pxend,*pa,*pend; extern int **pp; '
        'extern int (**pf)(int); extern short *ps; extern long *pl; '
        'int main(void) { return px==&target.x && pxend==&target.x+1 && pa==&target.a[2] && pend==target.a+3 && '
        'pp==&target.p && pf==&target.fn && ps==&target.in.s && pl==&target.in.l?42:1; }',
        {'target': (56,8,True,R_FIELDS)},
        {n: OffsetReference('object','target',byte_addend=v[0]) for n,v in refs.items()}))
    cases.append(Case('static anonymous path and array stride', A+'struct A target[3]; '
        'int *cell=&target[2].promoted; int *tail=&target[1].tail;', A+
        'extern struct A target[3]; extern int *cell,*tail; '+
        'int main(void) { return cell==&target[2].promoted && tail==&target[1].tail?42:1; }',
        references={'cell': OffsetReference('object','target',byte_addend=60),
                    'tail': OffsetReference('object','target',byte_addend=40)}))
    cases.append(Case('static record array nested address and onepast', P+
        'struct P target[3]; long *cell=&target[2].y; '
        'struct P *end=target+3; struct P (*whole)[3]=&target+1;', P+
        'extern struct P target[3]; extern long *cell; extern struct P *end; '
        'extern struct P (*whole)[3]; int main(void) { return cell==&target[2].y && '
        'end==target+3 && whole==&target+1?42:1; }',
        {'target': (48,8,True,tuple((i*16+o,w) for i in range(3) for o,w in ((0,1),(4,4),(8,8))))},
        {'cell': OffsetReference('object','target',byte_addend=40),
         'end': OffsetReference('object','target',byte_addend=48),
         'whole': OffsetReference('object','target',byte_addend=48)}))
    cases.append(Case('private base representation offset', P+
        'static int first=40; static struct P target; int *cell=&target.x; '
        'int first_value(void) { return first; }',
        'extern int *cell; int first_value(void); '+
        'int main(void) { return first_value()==40 && *cell==0?42:1; }',
        {'target': (16,8,False,((0,1),(4,4),(8,8)))},
        {'cell': OffsetReference('object','target',byte_addend=4)}))
    tls_header='struct P { long c; long x; long y; }; '
    tls_host = tls_header+'''
#include <pthread.h>
struct P *slot(void); extern _Thread_local struct P target;
static void *worker(void *unused) { (void)unused; struct P *p=slot(); if(p!=&target || p->c || p->x || p->y) return (void *)1; p->x=23; return p->x==23?0:(void *)2; }
int main(void) { pthread_t t; void *r; struct P *p=slot(); if(p!=&target || p->c || p->x || p->y) return 1; p->x=42; if(pthread_create(&t,0,worker,0) || pthread_join(t,&r) || r) return 2; return slot()==p && p->x==42?42:3; }
'''
    cases.append(Case('TLS zero record and pthread isolation', tls_header+
        '_Thread_local struct P target; struct P *slot(void) { return &target; }',
        tls_host, tls=(('target',24,0,True),), pthread=True))
    local('all existing integer and object pointer member families',
          'struct Scalar { _Bool b; signed char sc; unsigned char uc; short sh; '
          'unsigned short us; int i; unsigned int ui; long l; unsigned long ul; '
          'long long ll; unsigned long long ull; void *v; const int *ci; int (*pa)[2]; }; ',
          'struct Scalar s; int x=42; int a[2]; a[0]=19; a[1]=23; '
          's.b=2; s.sc=-7; s.uc=250; s.sh=-12345; s.us=60000; s.i=-123456; '
          's.ui=4000000000U; s.l=-4294967297L; s.ul=18446744073709551615UL; '
          's.ll=-9223372036854775807LL; s.ull=18446744073709551615ULL; '
          's.v=&x; s.ci=&x; s.pa=&a; struct Scalar c=s; '
          'return sizeof c==72 && _Alignof(struct Scalar)==8 && c.b==1 && c.sc==-7 && '
          'c.uc==250 && c.sh==-12345 && c.us==60000 && c.i==-123456 && '
          'c.ui==4000000000U && c.l==-4294967297L && c.ul==18446744073709551615UL && '
          'c.ll==-9223372036854775807LL && c.ull==18446744073709551615ULL && '
          'c.v==&x && *c.ci==42 && (*c.pa)[0]+(*c.pa)[1]==42?42:1;')
    local('recursive record pointer member chains',
          'struct Node { int x; struct Node *next; }; ',
          'struct Node a; struct Node b; a.x=40; b.x=2; a.next=&b; b.next=&a; '
          'return a.next->next==&a && a.next->x+b.next->x==42?42:1;')
    for size in (70,129,1048576):
        header=f'struct Large {{ unsigned char a[{size}]; }}; '
        cases.append(Case(f'large {size} byte global copy with tail',
            header+'struct Large source,target; int copy_record(void) { target=source; return 42; }',
            header+'extern struct Large source,target; int copy_record(void); '
            f'int main(void) {{ int i=0; for(i=0;i<{size};++i) source.a[i]=(unsigned char)(i*17+3); '
            f'if(copy_record()!=42) return 1; for(i=0;i<{size};++i) '
            'if(target.a[i]!=(unsigned char)(i*17+3)) return 2; '
            f'return target.a[0]==3 && target.a[{size-1}]==(unsigned char)(({size-1})*17+3)?42:3; }}',
            {n:(size,1,True,((0,size),)) for n in ('source','target')},compact_copy=True))
    return cases


def zero_evidence(elf, zeros, qbe=False):
    """Actual symbol/section bytes; no assumption that size equals alignment."""
    used = set()
    for name, (width, alignment, public, fields) in zeros.items():
        candidates = [s for s in elf.symbols if s['section'] and s['name'] not in used and
                      (s['name']==name if name is not None else s['binding']==0 and s['kind'] in (0,1))]
        matches = []
        for s in candidates:
            if s['binding'] != int(public):
                continue
            assert s['kind']==(0 if qbe else 1), ('record ELF type', name, s)
            assert s['size']==(0 if qbe else width), ('record ELF size', name, s)
            section=elf.sections[s['section']]
            assert section[1] in (1,8) and section[2]&3==3 and not section[2]&0x400
            assert section[8]>=alignment and s['value']%alignment==0, ('record alignment',name,s,section)
            assert s['value']+width<=section[5]
            contents = bytes(width) if section[1]==8 else elf.section_bytes(s['section'])[s['value']:s['value']+width]
            for offset,size in fields:
                assert contents[offset:offset+size]==bytes(size), ('record member zero', name,offset,contents)
            matches.append(s)
        assert len(matches)==1, ('record object missing/ambiguous',name,matches)
        used.add(matches[0]['name'])


def check_il(text, case):
    # Before accepting width-less QBE ELF labels, prove exact storage extent,
    # alignment and linkage from typed IL. Generated block labels are consumed.
    blocks = re.findall(r'^(export )?(thread )?data \$([^\s=]+) = align (\d+) \{([^}]+)\}$',text,re.M)
    if case.compact_copy:
        assert len(text.encode()) < 20000, ('record copy IL expanded linearly',case.name,len(text))
        assert len(text.splitlines()) < 400, ('record copy instruction explosion',case.name)
        for amount in re.findall(r'\bblit\s+[^\n]+,\s*(\d+)\s*$',text,re.M):
            assert int(amount)<=64, ('large record must use bounded copy loop, not QBE giant blit',case.name,amount)
        assert not re.search(r'\bcall \$(?:memcpy|memmove)\b',text), ('hidden libc record-copy dependency',case.name)
    used=set()
    for name,(width,alignment,public,fields) in case.zeros.items():
        matches=[b for b in blocks if b[2] not in used and not b[1] and
                 (b[2]==name if name is not None else not b[0]) and bool(b[0])==public and
                 int(b[3])==alignment and re.fullmatch(r'\s*z '+str(width)+r'\s*',b[4])]
        assert len(matches)==1, ('record IL zero extent/alignment/binding',case.name,name,text)
        used.add(matches[0][2])
    for name,ref in case.references.items():
        assert blocks.count(('export ', '', name, '8', f' l ${ref.name} + {ref.byte_addend} '))==1, (name,text)


def check_object(path, case, qbe=False):
    elf=OffsetRelocations(path)
    zero_evidence(elf,case.zeros,qbe)
    elf.check(case.references)
    if case.tls:
        TLS(path).check(case.tls,qbe=qbe,required=('target',))
    return elf


# Meaningful native constraints only. Exact signature tables populated from
# unchanged originals; no arbitrary error substring or warning whitelist.
CONSTRAINTS = [
    ('const scalar member', 'struct S { int x; }; void f(const struct S *p) { p->x=1; }'),
    ('const nested member', 'struct I { int x; }; struct S { struct I in; }; void f(const struct S *p) { p->in.x=1; }'),
    ('const array member', 'struct S { int a[2]; }; void f(const struct S *p) { p->a[0]=1; }'),
    ('nested const aggregate assignment', 'struct I { const int x; }; struct S { struct I in; }; void f(struct S *p, struct S *q) { *p=*q; }'),
    ('const pointer member', 'struct S { int *p; }; void f(const struct S *p, int *q) { p->p=q; }'),
    ('missing member', 'struct S { int x; }; int f(struct S *p) { return p->missing; }'),
    ('dot on pointer', 'struct S { int x; }; int f(struct S *p) { return p.x; }'),
    ('arrow on record', 'struct S { int x; }; int f(void) { struct S p; return p->x; }'),
    ('incompatible record assignment', 'struct S { int x; }; struct T { int x; }; void f(struct S *p, struct T *q) { *p=*q; }'),
]
NATIVE_CONSTRAINTS = {
    'const scalar member': ((('error', "assignment of member 'x' in read-only object"),),
        (('error', "cannot assign to variable 'p' with const-qualified type 'const struct S *'"), ('note', "variable 'p' declared const here"))),
    'const nested member': ((('error', "assignment of member 'x' in read-only object"),),
        (('error', "cannot assign to variable 'p' with const-qualified type 'const struct S *'"), ('note', "variable 'p' declared const here"))),
    'const array member': ((('error', "assignment of read-only location 'p->a[0]'"),),
        (('error', "cannot assign to variable 'p' with const-qualified type 'const struct S *'"), ('note', "variable 'p' declared const here"))),
    'nested const aggregate assignment': ((('error', "assignment of read-only location '*p'"),),
        (('error', "cannot assign to lvalue with nested const-qualified data member 'x'"), ('note', "nested data member 'x' declared const here"))),
    'const pointer member': ((('error', "assignment of member 'p' in read-only object"),),
        (('error', "cannot assign to variable 'p' with const-qualified type 'const struct S *'"), ('note', "variable 'p' declared const here"))),
    'missing member': ((('error', "'struct S' has no member named 'missing'"),),
        (('error', "no member named 'missing' in 'struct S'"),)),
    'dot on pointer': ((('error', "'p' is a pointer; did you mean to use '->'?"),),
        (('error', "member reference type 'struct S *' is a pointer; did you mean to use '->'?"),)),
    'arrow on record': ((('error', "invalid type argument of '->' (have 'struct S')"),),
        (('error', "member reference type 'struct S' is not a pointer; did you mean to use '.'?"),)),
    'incompatible record assignment': ((('error', "incompatible types when assigning to type 'struct S' from type 'struct T'"),),
        (('error', "assigning to 'struct S' from incompatible type 'struct T'"),)),
}


def native_constraint(cc, source, output, name):
    output.unlink(missing_ok=True)
    # GCC's human fix-it arrow is suppressed at the rendering level; all actual
    # diagnostic headers (including notes) remain checked in full. No filtering.
    flags=diagnostic_flags(cc)+([] if clang_style(cc) else ['-fno-diagnostics-show-caret'])
    r=invoke([cc,*flags,'-std=c2x','-pedantic-errors','-fno-common','-c',source,'-o',output])
    expected=NATIVE_CONSTRAINTS[name][int(clang_style(cc))]
    actual=native_diagnostics(r.stderr,source,source.read_text(),clang_style(cc))
    assert r.returncode!=0 and not r.stdout and not output.exists(), (name,cc,r)
    assert actual==expected, (name,cc,actual,expected,r.stderr)


# These are native-valid out-of-scope forms, NOT language constraints. They are
# never executed and native acceptance is not treated as semantic evidence.
SUBSET = [
    ('M17 general braces', 'struct S { int x; }; struct S s={1};'),
    ('M21 aggregate argument', 'struct S { int x; }; int f(struct S s) { return s.x; }'),
    ('M21 aggregate return', 'struct S { int x; }; struct S f(struct S *p) { return *p; }'),
    ('M22 bitfield', 'struct S { unsigned int x:3; }; struct S s;'),
    ('M22 flexible array', 'struct S { int n; int a[]; }; struct S *p;'),
]


# Conservative address-proof/UB-oriented refusals. No native execution or
# native-constraint claims: acceptance by a host is not proof of defined C.
ADDRESS_REFUSALS = [
    ('member scalar beyond onepast', 'struct S { int x; int y; }; struct S target; int *cell=&target.x+2;'),
    ('member array beyond onepast', 'struct S { int a[2]; int y; }; struct S target; int *cell=target.a+3;'),
    ('member subscript beyond onepast', 'struct S { int a[2]; }; struct S target; int *cell=&target.a[3];'),
    ('member on outer onepast', 'struct S { int x; }; struct S target[2]; int *cell=&target[2].x;'),
    ('member on scalar record onepast', 'struct S { int x; }; struct S target; int *cell=&(&target+1)->x;'),
    ('member on row array onepast', 'struct S { int x; }; struct S target[2][2]; int *cell=&target[0][2].x;'),
    ('member root dereference from null', 'struct S { int x; }; int *cell=&((struct S *)0)->x;'),
    ('member pointer load is not static address', 'struct S { int *p; }; struct S target; int *cell=target.p;'),
    ('pointer base load is not static address', 'struct S { int x; }; struct S *target; int *cell=&target->x;'),
    ('TLS member address', 'struct S { int x; }; _Thread_local struct S target; int *cell=&target.x;'),
    ('TLS member decay', 'struct S { int a[2]; }; _Thread_local struct S target; int *cell=target.a;'),
    ('TLS member cast address', 'struct S { int x; }; _Thread_local struct S target; void *cell=(void *)&target.x;'),
    ('TLS nested member address', 'struct S { struct { int x; } in; }; _Thread_local struct S target; int *cell=&target.in.x;'),
]


def must_fail(operation, label):
    try:
        operation()
    except AssertionError:
        return
    raise AssertionError('M16 negative control escaped: '+label)


def controls(d):
    source, output=d/'control.c',d/'control.o'
    source.write_text('struct P { char c; int x; long y; }; struct P target; int *cell=&target.x;\n')
    producer([HOST,*diagnostic_flags(HOST),'-std=c2x','-pedantic-errors','-fno-common','-c',source,'-o',output],output)
    elf=OffsetRelocations(output)
    zeros={'target':(16,8,True,((0,1),(4,4),(8,8)))}
    refs={'cell':OffsetReference('object','target',byte_addend=4)}
    zero_evidence(elf,zeros); elf.check(refs)
    for mutation in ('size','alignment','offset','binding','type','missing'):
        damaged=copy.deepcopy(elf); s=damaged.symbol('target')
        if mutation=='size': s['size']=12
        elif mutation=='alignment':
            section=list(damaged.sections[s['section']]); section[8]=1; damaged.sections[s['section']]=tuple(section)
        elif mutation=='offset': s['value']+=1
        elif mutation=='binding': s['binding']=0
        elif mutation=='type': s['kind']=6
        else: damaged.symbols.remove(s)
        must_fail(lambda:zero_evidence(damaged,zeros),mutation)
    # Materialize a copy of the BSS section in the oracle only, then mutate a
    # member vs padding byte. Both cases exercise the actual byte comparison.
    material=copy.deepcopy(elf); sym=material.symbol('target')
    section=list(material.sections[sym['section']]); section[1]=1; section[4]=len(material.data)
    material.data+=bytes(section[5]); material.sections[sym['section']]=tuple(section)
    zero_evidence(material,zeros)
    for byte in (0,4,7,8,15):
        damaged=copy.deepcopy(material); offset=section[4]+sym['value']+byte
        damaged.data=damaged.data[:offset]+b'X'+damaged.data[offset+1:]
        must_fail(lambda:zero_evidence(damaged,zeros),'changed member byte '+str(byte))
    for byte in (1,2,3):
        damaged=copy.deepcopy(material); offset=section[4]+sym['value']+byte
        damaged.data=damaged.data[:offset]+b'X'+damaged.data[offset+1:]
        zero_evidence(damaged,zeros)  # Padding is explicitly NOT constrained.
    for mutation in ('member','base','duplicate'):
        damaged=copy.deepcopy(elf); r=damaged.slot_relocation('cell')
        if mutation=='member': r['addend']=8
        elif mutation=='base': r['symbol']['name']='wrong'
        else: damaged.relocations.append(copy.deepcopy(r))
        must_fail(lambda:damaged.check(refs),mutation)
    case=Case('control','','',zeros,refs)
    text='export data $target = align 8 { z 16 }\nexport data $cell = align 8 { l $target + 4 }\n'
    check_il(text,case)
    for bad in (text.replace('z 16','z 12'),text.replace('align 8','align 1'),text.replace('+ 4','+ 8'),text+text):
        must_fail(lambda:check_il(bad,case),'IL mutation')
    compact=Case('large copy control','','',compact_copy=True)
    check_il('export function w $copy() {\n@start\nret 42\n}\n',compact)
    for bad in ('blit $source, $target, 1048576\n', 'call $memcpy()\n', 'x\n'*500, 'x'*20001):
        must_fail(lambda:check_il(bad,compact),'unbounded/hidden large copy')
    assert native_diagnostics('unrecognized compiler noise\n',source,source.read_text(),False) is None
    print('M16 controls: ELF record extent/alignment/binding/type; exact member relocation and IL')


def compile_native(cc, source, output):
    producer([cc,*diagnostic_flags(cc),'-std=c2x','-pedantic-errors','-fno-common','-O0','-c',source,'-o',output],output)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-only',action='store_true')
    parser.add_argument('--harness-self-test',action='store_true')
    parser.add_argument('--frozen-hash')
    args=parser.parse_args()
    if not args.native_only and not args.harness_self_test:
        assert args.frozen_hash and re.fullmatch('[0-9a-f]{40}',args.frozen_hash), 'exact --frozen-hash required; no provisional PASS'
        head=invoke(['git','-C',ROOT,'rev-parse','HEAD'])
        assert head.returncode==0 and head.stdout.strip()==args.frozen_hash, (head,args.frozen_hash)
        assert Path(KCC).resolve().is_relative_to(ROOT), 'KCC must be built inside the frozen checkout'
        dirty=invoke(['git','-C',ROOT,'status','--porcelain','--','src'])
        assert dirty.returncode==0 and not dirty.stdout, ('dirty production sources',dirty)
        assert QBE, 'QBE required for actual M16 ELF/runtime coverage'
    with tempfile.TemporaryDirectory(prefix='kcc record runtime ') as tmp:
        d=Path(tmp)
        harness_self_test(d); compiler_selection_self_test(d); controls(d)
        if args.harness_self_test: return
        compilers=native_compilers(HOST,os.environ.get('CLANG_CC') or shutil.which('clang'))
        extra=os.environ.get('GCC13_CC')
        if extra:
            assert shutil.which(extra), ('GCC13 unavailable',extra)
            if all(os.path.realpath(shutil.which(cc))!=os.path.realpath(shutil.which(extra)) for cc in compilers): compilers.append(extra)
        counts={cc:0 for cc in compilers}; kcc_count=0
        owner,host,native,other,il,assembly,obj,exe=[d/n for n in ('owner.c','host.c','native.o','host.o','record.ssa','record.s','record.o','program')]
        cases=fixtures(); assert len(set(c.name for c in cases))==len(cases)
        for case in cases:
            owner.write_text(case.owner+'\n'); host.write_text(case.companion+'\n')
            for cc in compilers:
                compile_native(cc,owner,native); check_object(native,case)
                compile_native(cc,host,other)
                run_program(cc,[native,other]+(['-pthread'] if case.pthread else []),exe)
                counts[cc]+=1
            if args.native_only: continue
            result=invoke([KCC,owner])
            assert result.returncode==0 and not result.stderr and result.stdout,(case.name,result)
            check_il(result.stdout,case); il.write_text(result.stdout)
            producer([QBE,'-t','amd64_sysv','-o',assembly,il],assembly)
            producer([HOST,'-c',assembly,'-o',obj],obj); check_object(obj,case,True)
            compile_native(HOST,host,other)
            run_program(HOST,[obj,other]+(['-pthread'] if case.pthread else []),exe)
            kcc_count+=1
        for name,text in CONSTRAINTS:
            owner.write_text(text+'\n')
            for cc in compilers: native_constraint(cc,owner,native,name)
            if not args.native_only: reject(owner)
        if not args.native_only:
            for name,text in SUBSET+ADDRESS_REFUSALS:
                owner.write_text(text+'\n'); reject(owner)
        print(f'M16 constraints: {len(CONSTRAINTS)} exact full native diagnostic originals per compiler; '
              f'{0 if args.native_only else len(SUBSET)} separately scoped subset refusals; '
              f'{0 if args.native_only else len(ADDRESS_REFUSALS)} address/UB-proof compile-only refusals')
        print(f'M16 runtime: {len(cases)} unchanged originals; KCC/QBE/ELF/runtime {kcc_count}')
        for cc,n in counts.items(): print(f'{cc}: {n} unchanged native originals passed')
        if args.native_only: print('NATIVE-ONLY: no KCC coverage or frozen-production PASS claimed')
        else: print('Frozen production hash: '+args.frozen_hash)


if __name__=='__main__': main()

"""Independent M18 declaration-alignment oracle (LP64 / amd64 SysV).

Only unchanged, defined originals execute. Native C23 capability gaps, real
constraints, and compile-only checked redeclaration/target policies are separate.
Imports M17 hardened infrastructure directly, never the parallel enum harness.
Production requires --frozen-hash; --native-only NEVER claims a KCC PASS.
"""
import argparse
import copy
import hashlib
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import subprocess
import tempfile
from unittest.mock import patch

from test_integer_initializers import (
    KCC, HOST, QBE, invoke, producer, native_diagnostics, clang_style,
    harness_self_test, run_program, features_for,
)
from test_null_initializers import compiler_selection_self_test
from test_address_offsets import OffsetRelocations, OffsetReference, diagnostic_flags
from test_compound_literals import (
    Literal, ints, literal_evidence, il_extents, selected_compilers,
    native_version, compile_native, must_fail,
)


@dataclass(frozen=True)
class Object:
    size: int
    alignment: int
    public: bool = True
    tls: bool = False
    # Defined value bytes only; None intentionally never inspects record padding.
    contents: bytes | None = None


@dataclass
class Case:
    name: str
    owner: str
    companion: str = 'int test(void); int main(void) { return test(); }'
    objects: dict = field(default_factory=dict)
    roots: dict = field(default_factory=dict)
    references: dict = field(default_factory=dict)
    features: tuple = ()
    no_data: bool = False
    pthread: bool = False
    private_object: Object | None = None


def fixtures():
    out = []
    def local(name, body, header='', **kw):
        out.append(Case(name, header+'int test(void) { '+body+' }', **kw))
    for spelling in ('_Alignas', 'alignas'):
        for alignment, typ, width in ((1,'char',1),(2,'short',2),(4,'int',4),(8,'long',8),(16,'int',4)):
            local(f'{spelling} automatic {alignment}',
                  f'{spelling}({alignment}) {typ} x=42; '
                  f'return aligned(&x,{alignment}) && sizeof x=={width} && x==42?42:1;',
                  features=(() if spelling=='_Alignas' else ('alignas',)))
    local('zero ignored natural long', '_Alignas(0) long x=42; return sizeof x==8 && aligned(&x,8)?42:1;')
    local('combined weaker stronger source order', '_Alignas(1) _Alignas(16) _Alignas(0) int x=42; '
          '_Alignas(16) _Alignas(2) int y=0; return aligned(&x,16) && aligned(&y,16)?x:1;')
    local('type operand typedef array and enum', '_Alignas(L) int x=42; _Alignas(int[3]) int y=0; '
          '_Alignas(enum E) int z=0; return aligned(&x,8) && aligned(&y,4) && sizeof z==4?x:1;',
          'typedef long L; enum E { A=8 }; ')
    local('ICE conditional and query operand', '_Alignas(1 ? sizeof(long) : 4) int x=42; '
          '_Alignas(_Alignof(long)) int y=0; return aligned(&x,8) && aligned(&y,8)?x:1;')
    local('comma declarators distinct natural types', '_Alignas(8) int x=42, *p=&x; '
          'return aligned(&x,8) && aligned(&p,8) && sizeof x==4 && sizeof p==8?*p:1;')
    local('aligned array object preserves stride', '_Alignas(16) int a[3]={19,23,7}; '
          'return aligned(a,16) && sizeof a==12 && (char *)&a[1]-(char *)&a[0]==4 && a[0]+a[1]==42?42:1;')
    local('object alignment does not contaminate typeof', '_Alignas(16) int x=42; typeof(x) y=0; '
          'return _Alignof(typeof(x))==4 && _Alignof(typeof(y))==4 && sizeof x==4?x:1;', features=('typeof',))
    record='struct R { char a; _Alignas(16) int n; char b; }; '
    local('member layout tail padding record array stride', 'struct R a[2]={{1,40,2},{3,19,4}}; '
          'a[1]=a[0]; return _Alignof(struct R)==16 && sizeof(struct R)==32 && '
          '(char *)&a[0].n-(char *)&a[0]==16 && (char *)&a[0].b-(char *)&a[0]==20 && '
          '(char *)&a[1]-(char *)&a[0]==32 && aligned(a,16) && a[1].n+a[1].b==42?42:1;', record)
    local('union member alignment rounds size', 'union U u={.n=42}; return _Alignof(union U)==16 && sizeof u==16 && aligned(&u,16)?u.n:1;',
          'union U { char c; _Alignas(16) int n; }; ')
    local('anonymous member accumulated offset', 'struct O x={.n=42}; return sizeof x==48 && _Alignof(struct O)==16 && '
          '(char *)&x.n-(char *)&x==32 && aligned(&x.n,16)?x.n:1;',
          'struct O { char a; struct { char b; _Alignas(16) int n; }; }; ')
    local('recursive stack alignment across calls', 'return recur(8)==42?42:1;',
          'int recur(int n) { _Alignas(16) int a[3]={n,19,23}; if(!aligned(a,16)) return 1; '
          'if(n && recur(n-1)!=42) return 2; return a[0]==n?a[1]+a[2]:3; } ')
    local('block static initialized aligned storage', 'static _Alignas(16) int x=40; ++x; ++x; return '
          'aligned(&x,16) && sizeof x==4?x:1;', private_object=Object(4,16,False,False,ints(40)))
    for name, declarations, align in (
        ('initialized global', '_Alignas(16) int cell=42;',16),
        ('aligned tentative then plain', '_Alignas(16) int cell; int cell;',16),
        ('plain tentative then aligned', 'int cell; _Alignas(16) int cell;',16),
        ('zero extern then definition', '_Alignas(0) extern int cell; _Alignas(16) int cell=42;',16),
        ('equivalent combined redeclarations', '_Alignas(4) _Alignas(16) extern int cell; _Alignas(16) int cell=42;',16),
        ('natural nonzero explicit', '_Alignas(4) extern int cell; _Alignas(4) int cell=42;',4),
        ('zero only tentative', '_Alignas(0) int cell; int cell;',4),
        ('extern request later aligned tentative', '_Alignas(16) extern int cell; int cell; _Alignas(16) int cell;',16),
    ):
        zero='tentative' in name
        out.append(Case(name,declarations,
            'extern int cell; int main(void) { return sizeof cell==4 && aligned(&cell,'+str(align)+') && cell=='+('0' if zero else '42')+'?42:1; }',
            {'cell':Object(4,align,contents=ints(0 if zero else 42))}))
    out.append(Case('private aligned initialized global', 'static _Alignas(16) int cell=42; int test(void) { return aligned(&cell,16)?cell:1; }',
                    objects={'cell':Object(4,16,False,contents=ints(42))}))
    out.append(Case('pure extern emits no storage', '_Alignas(16) extern int cell; int test(void) { return aligned(&cell,16)?cell:1; }',
                    '_Alignas(16) int cell=42; int test(void); int main(void) { return test(); }', no_data=True))
    out.append(Case('block extern canonical alignment', '_Alignas(16) int cell=42; int test(void) { _Alignas(16) extern int cell; return aligned(&cell,16)?cell:1; }',
                    objects={'cell':Object(4,16,contents=ints(42))}))
    out.append(Case('aligned array relocation exact addend', '_Alignas(16) int cell[3]={19,23,7}; int *slot=cell+1;',
                    'extern int cell[3]; extern int *slot; int main(void) { return aligned(cell,16) && slot==cell+1 && slot[-1]+*slot==42?42:1; }',
                    {'cell':Object(12,16,contents=ints(19,23,7)), 'slot':Object(8,8)},
                    references={'slot':OffsetReference('object','cell',byte_addend=4)}))
    for initialized in (False,True):
        out.append(Case('TLS '+('initialized' if initialized else 'zero'),
            '_Alignas(16) _Thread_local int cell'+('=40;' if initialized else ';')+
            'int test(void) { if(!aligned(&cell,16) || cell!='+('40' if initialized else '0')+') return 1; cell=42; return cell; }',
            '#include <pthread.h>\nextern _Thread_local int cell; int test(void); '
            'static void *worker(void *p) { (void)p; return (void *)(unsigned long)test(); } '
            'int main(void) { pthread_t t; void *r=0; if(test()!=42 || pthread_create(&t,0,worker,0) || pthread_join(t,&r)) return 1; '
            'return (unsigned long)r==42 && cell==42?42:1; }',
            {'cell':Object(4,16,tls=True,contents=ints(40 if initialized else 0))}, pthread=True))
    local('C23 parameter local after scalar adjustment', 'return f(42);',
          'int f(int); int f(_Alignas(16) int x) { return sizeof x==4 && aligned(&x,16)?x:1; } ', features=('parameter',))
    local('C23 array parameter adjusted pointer slot', 'int a[2]={19,23}; return f(a);',
          'int f(_Alignas(16) int a[2]) { return sizeof a==8 && aligned(&a,16)?a[0]+a[1]:1; } ', features=('parameter-array',))
    local('C23 function parameter adjusted pointer slot', 'return f(answer);',
          'int answer(void) { return 42; } int f(_Alignas(16) int cb(void)) { return sizeof cb==8 && aligned(&cb,16)?cb():1; } ', features=('parameter',))
    local('C23 aligned automatic compound literal', 'int *p=&(_Alignas(16) int){40}; *p+=2; return sizeof *p==4 && aligned(p,16)?*p:1;', features=('literal',))
    out.append(Case('C23 aligned file compound literal', 'int *slot=&(_Alignas(16) int){42};',
        'extern int *slot; int main(void) { return sizeof *slot==4 && (unsigned long)slot%16==0?*slot:1; }',
        objects={'slot':Object(8,8)}, roots={'slot':Literal(4,16,((0,ints(42)),))}, features=('literal',)))
    local('C23 aligned static compound literal', 'int *p=&(static _Alignas(16) int){40}; *p+=2; return aligned(p,16)?*p:1;',
          features=('literal-storage',),private_object=Object(4,16,False,False,ints(40)))
    local('C23 aligned thread compound literal', 'int *p=&(static _Thread_local _Alignas(16) int){40}; *p+=2; return aligned(p,16)?*p:1;',
          features=('literal-thread',),private_object=Object(4,16,False,True,ints(40)))
    local('C23 query aligned literal allocates nothing', 'return sizeof((_Alignas(16) int){42})==4?42:1;',
          features=('literal',),no_data=True)
    local('C23 query aligned static literal allocates nothing', 'return sizeof((static _Alignas(16) int){42})==4?42:1;',
          features=('literal-storage',),no_data=True)
    local('alignment operand introduces enum before core type',
          '_Alignas(sizeof(enum E { A=4 })) enum E x=A; return sizeof x==4 && A==4 && aligned(&x,4)?42:1;')
    local('alignment operands bind sequentially',
          '_Alignas(sizeof(enum E { A=4 })) _Alignas(A) enum E x=A; return sizeof x==4 && aligned(&x,4)?42:1;')
    local('enum core introduces later alignment operand',
          'enum { A=16 } _Alignas(A) x=A; return sizeof x==4 && aligned(&x,16)?42:1;', features=('post-enum-alignment',))
    local('macro expansion preserves alignment operand order',
          'MAKE _Alignas(A) enum E x=A; return sizeof x==4 && aligned(&x,4)?42:1;',
          '#define MAKE _Alignas(sizeof(enum E { A=4 }))\n')
    local('macro expansion preserves core before alignment',
          'CORE REQUEST x=A; return sizeof x==4 && aligned(&x,16)?42:1;',
          '#define CORE enum { A=16 }\n#define REQUEST _Alignas(A)\n', features=('post-enum-alignment',))
    local('pre-core operand enum feeds array bound',
          '_Alignas(sizeof(enum { A=2 })) int x[A]={19,23}; return sizeof x==8 && aligned(x,4)?x[0]+x[1]:1;')
    local('post-core operand enum feeds array bound',
          'int _Alignas(sizeof(enum { A=2 })) x[A]={19,23}; return sizeof x==8 && aligned(x,4)?x[0]+x[1]:1;')
    local('alignment enum operand shared comma syntax',
          '_Alignas(sizeof(enum E { A=2 })) enum E x=A, y=A; return sizeof x==4 && x+y==4?42:1;')
    local('member post-core operand feeds array bound',
          'struct R x={{19,23}}; return sizeof x==8 && aligned(&x,4)?x.a[0]+x.a[1]:1;',
          'struct R { int _Alignas(sizeof(enum { A=2 })) a[A]; }; ')
    local('parameter post-core operand feeds array bound', 'int a[2]={19,23}; return f(a);',
          'int f(int _Alignas(sizeof(enum { A=2 })) _Alignas(16) a[A]) { return sizeof a==8 && aligned(&a,16)?a[0]+a[1]:1; } ',
          features=('parameter-array',))
    local('literal post-core operand feeds array bound',
          'int *p=(int _Alignas(sizeof(enum { A=2 })) [A]){19,23}; return aligned(p,4)?p[0]+p[1]:1;',features=('literal',))
    local('literal core enum introduces trailing alignment operand',
          'return aligned(&(enum { A=16 } _Alignas(A)){42},16)?42:1;',features=('literal','post-enum-alignment'))
    local('parameter core enum introduces trailing alignment operand', 'return f(42);',
          'int f(enum { A=16 } _Alignas(A) x) { return aligned(&x,16)?x:1; } ',features=('parameter','post-enum-alignment'))
    local('alignment operand typeof exact query-depth budget',
          '_Alignas('+'typeof('*64+'int'+')'*64+') int x=42; return sizeof x==4 && aligned(&x,4)?x:1;',features=('typeof',))
    local('record alignment tail padding fits storage boundary',
          'return sizeof(struct R)==1048576 && _Alignof(struct R)==16?42:1;',
          'struct R { char a[1048560]; _Alignas(16) int n; }; ',no_data=True)
    out.append(Case('aligned record global extent excludes extra padding',
          record+'struct R cell={.a=1,.n=40,.b=2};',
          record+'extern struct R cell; int main(void) { return sizeof cell==32 && aligned(&cell,16) && '
          '(char *)&cell.n-(char *)&cell==16 && cell.n+cell.b==42?42:1; }',
          {'cell':Object(32,16)}))
    local('anonymous member requested alignment not intrinsic type',
          'struct O x={.n=42,.b=1}; return sizeof x==32 && _Alignof(struct O)==16 && '
          '(char *)&x.n-(char *)&x==16 && (char *)&x.b-(char *)&x==20 && sizeof x.n==4 && aligned(&x.n,16)?x.n:1;',
          'struct O { char a; _Alignas(16) struct { int n; }; char b; }; ')
    local('mixed stack slots survive eight argument calls',
          '_Alignas(16) int x=40; _Alignas(8) long y=2; char c=7; '
          'int n=sum8(1,2,3,4,5,6,7,14); return n==42 && c==7 && aligned(&x,16) && aligned(&y,8)?x+y:1;',
          'int sum8(int a,int b,int c,int d,int e,int f,int g,int h) { return a+b+c+d+e+f+g+h; } ')
    local('C23 query aligned thread literal allocates nothing',
          'return sizeof((static _Thread_local _Alignas(16) int){42})==4?42:1;',features=('literal-thread',),no_data=True)
    out.append(Case('typedef-root object alignment metadata',
          'typedef int I; _Alignas(16) I cell=42;',
          'extern int cell; int main(void) { return sizeof cell==4 && aligned(&cell,16)?cell:1; }',
          {'cell':Object(4,16,contents=ints(42))}))
    out.append(Case('typeof-root object alignment metadata',
          'int anchor; _Alignas(16) typeof(anchor) cell=42;',
          'extern int cell; extern int anchor; int main(void) { return sizeof cell==4 && anchor==0 && aligned(&cell,16)?cell:1; }',
          {'anchor':Object(4,4,contents=ints(0)), 'cell':Object(4,16,contents=ints(42))},features=('typeof',)))
    # The independently native-built companion measures actual addresses. KCC
    # intentionally has no pointer-to-integer conversion; no compiler extension
    # or source substitution is needed in the owned translation unit.
    for case in out:
        case.owner='int aligned(const void *, unsigned long);\n'+case.owner
        case.companion='int aligned(const void *, unsigned long);\n'+case.companion
        case.companion+='\nint aligned(const void *p, unsigned long n) { return (unsigned long)p%n==0; }'
    assert len({c.name for c in out})==len(out)
    return out


# Real native constraints. Ordinary type-name placement is a syntax constraint.
CONSTRAINTS = [
    ('nonpower', '_Alignas(3) int cell;'),
    ('weakening', '_Alignas(2) int cell;'),
    ('typedef', '_Alignas(16) typedef int T;'),
    ('function', '_Alignas(16) int f(void);'),
    ('register', 'int f(void) { _Alignas(16) register int x; return 0; }'),
    ('nonICE', 'int n; _Alignas(n) int cell;'),
    ('incomplete', 'struct S; _Alignas(struct S) int cell;'),
]
# No native execution or constraint-agreement claim for implementation policies.
POLICIES = [
    ('record alignment padding exceeds storage budget','struct R { char a[1048561]; _Alignas(16) int n; };'),
    ('alignment operand query-depth budget','_Alignas('+'typeof('*65+'int'+')'*65+') int x;'),
    ('extended target alignment', '_Alignas(32) int cell;'),
    ('full definition missing request', '_Alignas(16) extern int cell; int cell=42;'),
    ('full definition zero request', '_Alignas(16) extern int cell; _Alignas(0) int cell=42;'),
    ('different explicit requests', '_Alignas(8) extern int cell; _Alignas(16) int cell=42;'),
    ('natural explicit still conflicts', '_Alignas(4) extern int cell; _Alignas(16) int cell=42;'),
    ('extern cannot upgrade tentative', '_Alignas(16) extern int cell; int cell;'),
    ('plain tentative then extern cannot upgrade', 'int cell; _Alignas(16) extern int cell;'),
    ('later extern conflicts full definition', 'int cell=42; _Alignas(16) extern int cell;'),
    ('TLS full definition missing request', '_Alignas(16) extern _Thread_local int cell; _Thread_local int cell=42;'),
    ('block extern conflict', '_Alignas(16) int cell=42; int f(void) { _Alignas(8) extern int cell; return 0; }'),
]
PLACEMENT = [
    ('function alias alignment','typedef int F(void); _Alignas(16) F f;'),
    ('unevaluated literal weakening','unsigned long cell=sizeof((_Alignas(2) int){42});'),
    ('unevaluated static thread literal target request','int f(void) { return sizeof((static _Thread_local _Alignas(32) int){42}); }'),
    ('zero alignment typedef still forbidden','_Alignas(0) typedef int T;'),
    ('zero alignment register still forbidden','int f(void) { _Alignas(0) register int x; return 0; }'),
    ('void alignment type operand','_Alignas(void) int cell;'),
    ('function alignment type operand','_Alignas(int(void)) int cell;'),
    ('local alignment cannot see later core enum','int f(void) { _Alignas(A) enum { A=16 } x; return 0; }'),
    ('member alignment cannot see later core enum','struct R { _Alignas(A) enum { A=16 } x; };'),
    ('parameter alignment cannot see later core enum','int f(_Alignas(A) enum { A=16 } x) { return 0; }'),
    ('literal alignment cannot see later core enum','int f(void) { return (_Alignas(A) enum { A=16 }){42}; }'),
    ('alignment cannot see later core enumerator','_Alignas(A) enum { A=16 } x;'),
    ('later operand enum not visible earlier','_Alignas(A) _Alignas(sizeof(enum E { A=4 })) enum E x;'),
    ('macro source-order refusal','#define REQUEST _Alignas(A)\nREQUEST enum { A=16 } x;'),
    ('ordinary cast alignment','int f(void) { return (_Alignas(16) int)42; }'),
    ('ordinary sizeof type alignment','unsigned long cell=sizeof(_Alignas(16) int);'),
    ('ordinary alignof type alignment','unsigned long cell=_Alignof(_Alignas(16) int);'),
    ('void parameter marker alignment','int f(_Alignas(16) void);'),
    ('invalid3 not rescued by16','_Alignas(3) _Alignas(16) int cell;'),
    ('negative not rescued by16','_Alignas(-1) _Alignas(16) int cell;'),
    ('huge request no truncation','_Alignas(4294967296UL) int cell;'),
    ('literal weakening','int f(void) { return (_Alignas(2) int){42}; }'),
    ('parameter weakening after adjustment','int f(_Alignas(4) int a[2]) { return a[0]; }'),
]

# Version-bound full streams, populated from independently observed originals.
NATIVE_ERRORS = {('gcc11', 'nonpower'): (('error', "requested alignment '3' is not a positive power of 2"),),
 ('gcc11', 'weakening'): (('error', "'_Alignas' specifiers cannot reduce alignment of 'cell'"),),
 ('gcc11', 'typedef'): (('error', "alignment specified for typedef 'T'"),),
 ('gcc11', 'function'): (('error', "alignment specified for function 'f'"),),
 ('gcc11', 'register'): (('error', "alignment specified for 'register' object 'x'"),),
 ('gcc11', 'nonICE'): (('error', 'requested alignment is not an integer constant'),),
 ('gcc11', 'incomplete'): (('error',
                            "invalid application of '__alignof__' to incomplete type 'struct S'"),),
 ('gcc13', 'nonpower'): (('error', "requested alignment '3' is not a positive power of 2"),),
 ('gcc13', 'weakening'): (('error', "'_Alignas' specifiers cannot reduce alignment of 'cell'"),),
 ('gcc13', 'typedef'): (('error', "alignment specified for typedef 'T'"),),
 ('gcc13', 'function'): (('error', "alignment specified for function 'f'"),),
 ('gcc13', 'register'): (('error', "alignment specified for 'register' object 'x'"),),
 ('gcc13', 'nonICE'): (('error', 'requested alignment is not an integer constant'),),
 ('gcc13', 'incomplete'): (('error',
                            "invalid application of '__alignof__' to incomplete type 'struct S'"),),
 ('clang18', 'nonpower'): (('error', 'requested alignment is not a power of 2'),),
 ('clang18', 'weakening'): (('error',
                             "requested alignment is less than minimum alignment of 4 for type 'int'"),),
 ('clang18', 'typedef'): (('error', "'_Alignas' attribute only applies to variables and fields"),),
 ('clang18', 'function'): (('error', "'_Alignas' attribute only applies to variables and fields"),),
 ('clang18', 'register'): (('error',
                            "'_Alignas' attribute cannot be applied to a variable with 'register' "
                            'storage class'),),
 ('clang18', 'nonICE'): (('error', "'aligned' attribute requires integer constant"),),
 ('clang18', 'incomplete'): (('error',
                              "invalid application of '_Alignas' to an incomplete type 'struct S'"),
                             ('note', "forward declaration of 'struct S'"))}
CAPABILITY_ERRORS = {('gcc11', 'alignas'): (('error', "expected declaration specifiers or '...' before numeric constant"),),
 ('gcc11', 'parameter'): (('error', "alignment specified for parameter 'x'"),),
 ('gcc11', 'parameter-array'): (('error', "alignment specified for parameter 'a'"),),
 ('gcc11', 'literal-storage'): (('error', "expected expression before 'static'"),
                                ('error', "expected ';' before '{' token")),
 ('gcc11', 'literal-thread'): (('error', "expected expression before 'static'"),
                               ('error', "expected ';' before '{' token")),
 ('gcc13', 'parameter'): (('error', "alignment specified for parameter 'x'"),),
 ('gcc13', 'parameter-array'): (('error', "alignment specified for parameter 'a'"),),
 ('clang18', 'parameter'): (('error',
                             "'_Alignas' attribute cannot be applied to a function parameter"),),
 ('clang18', 'parameter-array'): (('error',
                                   "'_Alignas' attribute cannot be applied to a function parameter"),),
 ('clang18', 'literal'): (('error', 'expected expression'),),
 ('clang18', 'literal-storage'): (('error', 'expected expression'),),
 ('clang18', 'literal-thread'): (('error', 'expected expression'),)}
CAPABILITY_ERRORS[('clang18','post-enum-alignment')] = (('error', "expected ';' after enum"), ('error', 'a type specifier is required for all declarations'))
CAPABILITIES = {
    'post-enum-alignment':'int f(void) { enum { A=16 } _Alignas(A) x; return 0; }',
    'alignas':'alignas(16) int cell;',
    'parameter':'int f(_Alignas(16) int x) { return x; }',
    'parameter-array':'int f(_Alignas(16) int a[2]) { return a[0]; }',
    'literal':'int f(void) { return (_Alignas(16) int){42}; }',
    'literal-storage':'int f(void) { return (static _Alignas(16) int){42}; }',
    'literal-thread':'int f(void) { return (static _Thread_local _Alignas(16) int){42}; }',
}


CAPABILITY_ORIGINAL_SHA = {'alignas': '06bb4605cd5b5fa34423e8ec05f9c35e814ccef39280bdc832ce761f1ac47e8e',
 'literal': 'bfc930a7bc07236f2005f791dbc60472cbfdba797bbb211da56cf4db7b6b6147',
 'literal-storage': '069c076e4b568e9b9ea508774d11b6d6bd4cab49748f9c0b5a8e3cc38b8ad1b3',
 'literal-thread': '127f356327b81f889c4ba31cf5f4803d314a5d45dda99db5e92308804c4f48d8',
 'parameter': '1c41f2b258295cea60ab5f5297f3132bb2909231970e0d70ee573db0dc5135f6',
 'parameter-array': '5b96f6472f2573b5e8e951f18797f423f4e5f87edaa8342448a9c99d1bfa89ff',
 'post-enum-alignment': '94d85003413582ea0602e6703be2b3f3ca46b61aac16ef3374addb1021d892ff'}

# Valid C23 originals rejected by legacy Clang; NEVER native constraints.
CLANG_VALID_DISAGREEMENTS = {'aligned tentative then plain': ('7b917829e886eee4c9e300e401a0e4d1bd3c88a2bf04b931dceeb5016d4c278b',
                                  (('error',
                                    "'_Alignas' must be specified on definition if it is specified on "
                                    'any declaration'),
                                   ('note', "declared with '_Alignas' attribute here"))),
 'zero extern then definition': ('7c4e0e2e8058fbfec84227daef0d7f01fa78337c3bb630f5e1385be3b1ca7ed1',
                                 (('error',
                                   'redeclaration has different alignment requirement (16 vs 4)'),
                                  ('note', 'previous declaration is here'))),
 'zero only tentative': ('0963d7d79c067531cce6a0354fab750aa9d41f1a527332ae7efcd89c73df6af4',
                         (('error',
                           "'_Alignas' must be specified on definition if it is specified on any "
                           'declaration'),
                          ('note', "declared with '_Alignas' attribute here"))),
 'extern request later aligned tentative': ('919eae5753fb6b24e7aa8321552ad713c911748905306090a22086a1e36a9bd5',
                                            (('error',
                                              "'_Alignas' must be specified on definition if it is "
                                              'specified on any declaration'),
                                             ('note', "declared with '_Alignas' attribute here")))}

def family(cc):
    version=native_version(cc)
    if clang_style(cc):
        r=invoke([cc,'-dumpversion'])
        assert r.returncode==0 and not r.stderr and r.stdout.endswith('\n'), ('version probe',cc,r)
        version=r.stdout.strip()
        assert version in ('18.1.3','18.1.8'), ('unreviewed Clang',cc,version)
        return 'clang18'
    assert version in ('11.5.0','13.3.0'), ('unreviewed GCC',cc,version)
    return 'gcc'+version.split('.')[0]


def native_target(cc):
    r=invoke([cc,'-dumpmachine'])
    assert r.returncode==0 and not r.stderr and r.stdout in (
        'x86_64-amazon-linux\n', 'x86_64-amazon-linux-gnu\n',
        'x86_64-linux-gnu\n', 'x86_64-pc-linux-gnu\n',
    ), ('unreviewed native target',cc,r)


def native_result(cc, source, output):
    output.unlink(missing_ok=True)
    flags=diagnostic_flags(cc)+([] if clang_style(cc) else ['-fno-diagnostics-show-caret'])
    return invoke([cc,*flags,'-std=c2x','-pedantic-errors','-fno-common','-O0','-c',source,'-o',output])


def exact_refusal(cc, source, output, result, expected, original):
    assert source.read_text()==original+'\n', 'changed native original'
    actual=native_diagnostics(result.stderr,source,source.read_text(),clang_style(cc))
    assert result.returncode==1 and not result.stdout and not output.exists(), (cc,result,output)
    assert actual==expected, (cc,original,actual,expected,result.stderr)


def capability(cc, source, output, feature):
    original=CAPABILITIES[feature]; source.write_text(original+'\n')
    result=native_result(cc,source,output)
    if result.returncode==0:
        assert not result.stdout and not result.stderr and output.is_file() and output.stat().st_size
        OffsetRelocations(output)  # Success requires an actual target ELF object.
        return True
    assert hashlib.sha256(original.encode()).hexdigest()==CAPABILITY_ORIGINAL_SHA[feature], 'changed capability original'
    expected=CAPABILITY_ERRORS[(family(cc),feature)]
    exact_refusal(cc,source,output,result,expected,original)
    return False


def valid_native_disagreement(cc, source, output, case, result):
    assert family(cc)=='clang18', 'unreviewed disagreement compiler/version'
    assert case.name in CLANG_VALID_DISAGREEMENTS, 'unreviewed disagreement original'
    digest,expected=CLANG_VALID_DISAGREEMENTS[case.name]
    assert hashlib.sha256((case.owner+'\n'+case.companion).encode()).hexdigest()==digest, 'changed disagreement original'
    exact_refusal(cc,source,output,result,expected,case.owner)


def check_storage(elf, case, qbe=False, text=''):
    blocks=il_extents(text) if qbe else None
    public={s['name'] for s in elf.symbols if s['binding']==1 and 0<s['section']<len(elf.sections)
            and elf.sections[s['section']][2]&2 and not elf.sections[s['section']][2]&4
            and s['kind'] in (0,1,6)}
    assert public=={n for n,o in case.objects.items() if o.public}, ('unexpected/missing public storage',case.name,public)
    def verify(sym,wanted):
        assert 0<sym['section']<len(elf.sections), ('undefined/common object',sym)
        sec=elf.sections[sym['section']]
        assert sym['binding']==int(wanted.public) and sym['kind']==(6 if wanted.tls else 0 if qbe else 1), sym
        assert sym['size']==(0 if qbe else wanted.size), (sym,wanted)
        assert sec[1] in (1,8) and sec[2]&3==3 and not sec[2]&4
        assert bool(sec[2]&0x400)==wanted.tls, ('wrong TLS mode',sym,sec)
        assert sec[8]>=wanted.alignment and sym['value']%wanted.alignment==0
        assert sym['value']+wanted.size<=sec[5]
        if wanted.contents is not None:
            assert len(wanted.contents)==wanted.size
            value=bytes(wanted.size) if sec[1]==8 else elf.section_bytes(sym['section'])[sym['value']:sym['value']+wanted.size]
            assert value==wanted.contents, (case.name,sym,value,wanted.contents)
        if qbe:
            assert blocks[sym['name']]==(wanted.public,wanted.alignment,wanted.size), (case.name,sym,blocks)
            assert bool(re.search(r'^(?:export )?thread data \$'+re.escape(sym['name'])+r'\s*=',text,re.M))==wanted.tls
    for name,wanted in case.objects.items(): verify(elf.symbol(name),wanted)
    if case.private_object:
        private=[s for s in elf.symbols if s['binding']==0 and s['kind'] in (0,1,6)
                 and 0<s['section']<len(elf.sections) and elf.sections[s['section']][2]&3==3
                 and not elf.sections[s['section']][2]&4 and s['name']]
        assert len(private)==1, (case.name,'one private aligned object',private)
        verify(private[0],case.private_object)
    for name,wanted in case.roots.items(): literal_evidence(elf,elf.slot_relocation(name),wanted,qbe=qbe,il_blocks=blocks)
    elf.check(case.references)
    if any(o.tls for o in case.objects.values()) or (case.private_object and case.private_object.tls):
        wanted_tls={n for n,o in case.objects.items() if o.tls}
        if case.private_object and case.private_object.tls: wanted_tls.add(private[0]['name'])
        tls=[r for r in elf.relocations if r['kind'] in (19,20,21,22,23)]
        assert tls and {r['symbol']['name'] for r in tls}==wanted_tls, ('missing/wrong TLS target',case.name,tls)
        # All owned TLS definitions use the milestone's local-exec executable
        # model, not an opaque dynamic-TLS relocation or invented static address.
        assert all(r['kind']==23 and r['addend']==0 and r['symbol']['kind']==6 for r in tls), ('wrong TLS relocation mode/addend',case.name,tls)
    if case.no_data:
        assert not [s for s in elf.symbols if s['kind'] in (0,1,6) and s['name'] and 0<s['section']<len(elf.sections)
                    and elf.sections[s['section']][2]&2 and not elf.sections[s['section']][2]&4], ('unevaluated/extern emitted storage',case.name)
        if qbe: assert not blocks
    if qbe:
        # Literal children/private slots are checked above; no unaccounted storage.
        assert len(blocks)==len(case.objects)+len(case.roots)+int(case.private_object is not None), (case.name,blocks)


KCC_MESSAGES = {'function alias alignment':'alignment is not permitted on a function',
 'unevaluated literal weakening': 'alignment specification weakens natural type alignment',
 'unevaluated static thread literal target request': 'alignment is not supported by target (supported: 0, 1, 2, 4, 8, 16; no extended alignment)',
 'zero alignment typedef still forbidden': 'alignment is not permitted with typedef',
 'zero alignment register still forbidden': 'alignment is not permitted with register',
 'void alignment type operand': 'alignment type requires a complete object type',
 'function alignment type operand': 'alignment type requires a complete object type',
 'record alignment padding exceeds storage budget': 'record must contain members and fit record layout storage limit (1 MiB)',
 'alignment operand query-depth budget': 'type query nesting exceeds limit (64)',
 'extended target alignment': 'alignment is not supported by target (supported: 0, 1, 2, 4, 8, 16; no '
                              'extended alignment)',
 'full definition missing request': 'conflicting object declaration/definition alignment',
 'full definition zero request': 'conflicting object declaration/definition alignment',
 'different explicit requests': 'conflicting object declaration/definition alignment',
 'natural explicit still conflicts': 'conflicting object declaration/definition alignment',
 'extern cannot upgrade tentative': 'tentative definition does not carry required object alignment',
 'plain tentative then extern cannot upgrade': 'tentative definition does not carry required object '
                                               'alignment',
 'later extern conflicts full definition': 'conflicting object declaration/definition alignment',
 'TLS full definition missing request': 'conflicting object declaration/definition alignment',
 'block extern conflict': 'conflicting object declaration/definition alignment',
 'nonpower': 'alignment is not supported by target (supported: 0, 1, 2, 4, 8, 16; no extended '
             'alignment)',
 'weakening': 'alignment specification weakens natural type alignment',
 'typedef': 'alignment is not permitted with typedef',
 'function': 'alignment is not permitted on a function',
 'register': 'alignment is not permitted with register',
 'nonICE': 'operand is not an integer constant expression',
 'incomplete': 'alignment type requires a complete object type',
 'local alignment cannot see later core enum': 'use of undeclared identifier',
 'member alignment cannot see later core enum': 'use of undeclared identifier',
 'parameter alignment cannot see later core enum': 'use of undeclared identifier',
 'literal alignment cannot see later core enum': 'use of undeclared identifier',
 'alignment cannot see later core enumerator': 'use of undeclared identifier',
 'later operand enum not visible earlier': 'use of undeclared identifier',
 'macro source-order refusal': 'use of undeclared identifier',
 'ordinary cast alignment': 'alignment specifier in a type name requires a compound literal initializer',
 'ordinary sizeof type alignment': 'alignment specifier in a type name requires a compound literal '
                                   'initializer',
 'ordinary alignof type alignment': 'alignment specifier is not permitted in this type name',
 'void parameter marker alignment': 'alignment is not permitted on register or void parameter',
 'invalid3 not rescued by16': 'alignment is not supported by target (supported: 0, 1, 2, 4, 8, 16; no '
                              'extended alignment)',
 'negative not rescued by16': 'alignment must not be negative',
 'huge request no truncation': 'alignment is not supported by target (supported: 0, 1, 2, 4, 8, 16; no '
                               'extended alignment)',
 'literal weakening': 'alignment specification weakens natural type alignment',
 'parameter weakening after adjustment': 'alignment specification weakens natural type alignment',
 'TU alignment budget': 'alignment specifier resource limit exceeded'}
KCC_ORIGINAL_SHA = {'function alias alignment':'6639cadc755a3692914d8bf2eff5ea3680814c3a31d4ef2525490a764adca5dd',
 'unevaluated literal weakening': 'cca77bcb45edcd254a132b60d0495e5bdd0b97a2055e1773ce5b3d5c58b985e5',
 'unevaluated static thread literal target request': '523e9805f251a28e84621eef0d662533db49bed2af5e6f55121649a5ed89caff',
 'zero alignment typedef still forbidden': 'b57cf8d4e318427fe0bef2e38a45566a041401d8eec0de7ddb136292f395c463',
 'zero alignment register still forbidden': '01ef0c39be34d60f7ee31498439b87e8904942c74d6c4c1981665135c69592ee',
 'void alignment type operand': 'ee98f5c3744157af536e1cf024807601d2a9a7a42ad13d30a71d556966e2c055',
 'function alignment type operand': '13da5879c1b8ffabe048e38022487207a5ff24cd0e6c1b6968f2f8b4abaf0d94',
 'record alignment padding exceeds storage budget': '29622eef589ed593b9eadb51e968149d07ef2ff11cf69fe8dc5be1c33d8df534',
 'alignment operand query-depth budget': '05c25a252c6bfba615ea89bd9537a2acae998b14e1d153507710a85159ca68e5',
 'nonpower': '6b5d0e11b8249a13d5f6f46e93d73c0053dcffd8648e759049b01ba4fdc5b559',
 'weakening': '06e5e66de93528d9da2a2bc0531b18ba2c2c48aab14f52d3525f004ec3a947c0',
 'typedef': '92269a2422f352e8e7ebc4db37d5e11e9f8ee5b36b0a58e17e8ed86a10222c3c',
 'function': 'd5e51eeb9bee37eb99d4260c80f381b31a02f7e941bbb744c5a6d941a3645fcb',
 'register': '59b866e420c509c8af98a3eeaa17ce106d2c845872f186add306144ada2301ee',
 'nonICE': 'ff7e085921c42571cb54b16a5dfa36c12fd1982519d213b7727d764b3f641589',
 'incomplete': 'e9f73b1c6dd5383ef03a08ce1b2b00d1801f7d801d6c0144068e86d6e1a6d03b',
 'extended target alignment': 'fa26243443694b25cd93dfff70c0b8f16eaf754ca7bb97483aee76c02921f23b',
 'full definition missing request': '5f7846066237e9fe40cbba83c5e4df53e43b8d0206203909ddb626fbfd3fb562',
 'full definition zero request': '98e0edf88557c34e78ca37c47ecf5d790ed545237636bfe5bf215e911365e0cd',
 'different explicit requests': '0ff6ddd6f99eec265cb0e0ec87859be53e904eb636aa31f4af740a0974b6a795',
 'natural explicit still conflicts': 'b01e037143157e64de1666e0651977c88ca6b263f017cf5ef03afef6570c84f7',
 'extern cannot upgrade tentative': '761661beb9a645982a1a7a593bda430d490015645b13238d2567528f0df64ac0',
 'plain tentative then extern cannot upgrade': '274629ab2997eb2c91878a012a966859db53165979575fa5a810a15bcb61d5d4',
 'later extern conflicts full definition': 'a03ce1c07cb1c0adfdbfeea576ebb5afc1ae14a6b45779f46fb153951ed5d3d9',
 'TLS full definition missing request': 'fa827e607689b732249432feb7b90b892211746ccac10582c3ac76c5fc2b85c8',
 'block extern conflict': '1cd7252acc5eafb5aea0245a3cf14c7f448579bda7a926ff1a4f1c21ba6325c8',
 'local alignment cannot see later core enum': '520003efe1d8f198dcb9b3951ea366101815640d73b2c7d4e489a0e42f8cf37c',
 'member alignment cannot see later core enum': 'cc0d5f72fffe1a4e9fb78e729aae95fb6a3598b4273f2255028810e485ad4eeb',
 'parameter alignment cannot see later core enum': '6a6da8bdffe637c3f746cf459624043ea376e35b80a733b534216fd1036e7748',
 'literal alignment cannot see later core enum': 'a326ec39e940ab45ec8c89ebd39e3f809f0e2b32e391ce998022a11b11fa0f62',
 'alignment cannot see later core enumerator': '33282b8c9def05001eee3f5253f7dbc8edbbe2edd438243b69f8e6f8d295d2ed',
 'later operand enum not visible earlier': '2ab3dfe227db5235c9c515eff57520c3182e8df1073e45f4be25449a16f5728c',
 'macro source-order refusal': '09531297afd2df32b7f90f77539da2e6147189121f6a11795cfc02e3609ed59d',
 'ordinary cast alignment': '0eacadd8d990cd3e0ed6a2296136548d12aa18353ad5aa68a1424e416b22fb76',
 'ordinary sizeof type alignment': 'c77b465149c233cc0b33d29b1503937fd26906d42a509aafa45c3d76e34289c8',
 'ordinary alignof type alignment': '3c7cd95364973153a39c22ca99b35c64a09a93b66d412eac3fc9dbc073e6c5e3',
 'void parameter marker alignment': 'e50e4253ac4bb58d18d6109d5cff2458a0d960bf854abd16db528fe699e411a9',
 'invalid3 not rescued by16': '9d089d73015db0a4b3a6d03f8ed7efde0bbb4566c56ea228e01ba4f60ee60719',
 'negative not rescued by16': '3ea55b1dd31a7bc411af0b77f7ee48ab2d35a9b302b7cc8b1e0513b91d3306de',
 'huge request no truncation': 'cf6e5ce23b45df36a7a00ba735fead6dd5a2c4ea9a16339ea723adb876160b20',
 'literal weakening': '7b407ddf7c6b971645bb6635fcf0ebf3670d554634e6e2e632766ec6cdb29a91',
 'parameter weakening after adjustment': 'd9fd899d47d7822b141ef9a8b97eac5b05470b61c20f5236f6d9c784153ed23f'}

def kcc_refusal(source, name, result):
    # Complete exact message stream; no IL, tool chatter or cascading errors.
    assert result.returncode==1 and not result.stdout, (name,result)
    expected=KCC_MESSAGES[name]
    actual=native_diagnostics(result.stderr,source,source.read_text(),False)
    assert actual==(('error',expected),), (name,result,expected)
    if name in KCC_ORIGINAL_SHA:
        assert hashlib.sha256(source.read_bytes()).hexdigest()==KCC_ORIGINAL_SHA[name], 'changed refusal original'


def controls(d):
    source,output=d/'control.c',d/'control.o'
    case=next(c for c in fixtures() if c.name=='initialized global')
    source.write_text(case.owner+'\n'); compile_native(HOST,source,output)
    elf=OffsetRelocations(output); check_storage(elf,case)
    for mutation in ('alignment','offset','size','binding','kind','missing','duplicate','bytes','tls'):
        bad=copy.deepcopy(elf); sym=bad.symbol('cell'); section=sym['section']
        if mutation=='alignment': sec=list(bad.sections[section]); sec[8]=4; bad.sections[section]=tuple(sec)
        elif mutation=='offset': sym['value']+=1
        elif mutation=='size': sym['size']=8
        elif mutation=='binding': sym['binding']=0
        elif mutation=='kind': sym['kind']=0
        elif mutation=='missing': bad.symbols.remove(sym)
        elif mutation=='duplicate': bad.symbols.append(copy.copy(sym))
        elif mutation=='tls': sec=list(bad.sections[section]); sec[2]|=0x400; bad.sections[section]=tuple(sec)
        else:
            at=bad.sections[section][4]+sym['value']; bad.data=bad.data[:at]+b'X'+bad.data[at+1:]
        must_fail(lambda:check_storage(bad,case),'alignment ELF '+mutation)
    qbe=copy.deepcopy(elf); qbe.symbol('cell').update(kind=0,size=0)
    text='export data $cell = align 16 { w 42 }\n'
    check_storage(qbe,case,True,text)
    for bad in (text.replace('align 16','align 8'),text.replace('w 42','l 42'),text+text,text+'data $extra = align 4 { w 0 }\n',text.replace('w 42','garbage')):
        must_fail(lambda:check_storage(qbe,case,True,bad),'wrong/extra IL object')
    tls_case=next(c for c in fixtures() if c.name=='TLS initialized')
    source.write_text(tls_case.owner+'\n'); compile_native(HOST,source,output)
    tls_elf=OffsetRelocations(output); check_storage(tls_elf,tls_case)
    for mutation in ('target','addend','mode','missing'):
        bad=copy.deepcopy(tls_elf); refs=[r for r in bad.relocations if r['kind']==23]; assert refs
        if mutation=='target': refs[0]['symbol']=dict(refs[0]['symbol'],name='wrong_TLS_object')
        elif mutation=='addend': refs[0]['addend']=4
        elif mutation=='mode': refs[0]['kind']=19
        else:
            bad.relocations=[r for r in bad.relocations if r['kind']!=23]
        must_fail(lambda:check_storage(bad,tls_case),'TLS relocation '+mutation)
    for key,expected in NATIVE_ERRORS.items():
        fam,name=key; cc='clang-18' if fam=='clang18' else 'gcc'; original=dict(CONSTRAINTS)[name]
        source.write_text(original+'\n'); output.unlink(missing_ok=True)
        stderr=''.join(f'{source}:1:1: {kind}: {msg}\n' for kind,msg in expected)
        if fam=='clang18': stderr+=str(sum(k=='error' for k,_ in expected))+' error'+('s' if sum(k=='error' for k,_ in expected)!=1 else '')+' generated.\n'
        good=subprocess.CompletedProcess([],1,'',stderr)
        exact_refusal(cc,source,output,good,expected,original)
        for mutation in ('status','stdout','stderr','missing-newline','note','object','original'):
            bad=copy.copy(good)
            if mutation=='status': bad.returncode=0
            elif mutation=='stdout': bad.stdout='partial IL'
            elif mutation=='stderr': bad.stderr+='unparsed tool text\n'
            elif mutation=='missing-newline': bad.stderr=bad.stderr.rstrip('\n')
            elif mutation=='note': bad.stderr+=f'{source}:1:1: note: unrelated\n'
            elif mutation=='object': output.write_bytes(b'stale')
            else: source.write_text(original+' \n')
            must_fail(lambda:exact_refusal(cc,source,output,bad,expected,original),'native constraint '+mutation)
            output.unlink(missing_ok=True); source.write_text(original+'\n')


    # Capability and valid-case discrepancy waivers are exact-original and
    # exact-stream, with version checking independently exercised below.
    def diagnostic_result(expected, clang):
        stderr=''.join(f'{source}:1:1: {kind}: {message}\n' for kind,message in expected)
        if clang:
            n=sum(kind=='error' for kind,_ in expected)
            stderr+=f'{n} error'+('s' if n!=1 else '')+' generated.\n'
        return subprocess.CompletedProcess([],1,'',stderr)
    for (fam,feature),expected in CAPABILITY_ERRORS.items():
        cc='clang-18' if fam=='clang18' else 'gcc'
        good=diagnostic_result(expected,fam=='clang18'); output.unlink(missing_ok=True)
        with patch.dict(globals(),{'native_result':lambda *args:good,'family':lambda _:fam}):
            assert capability(cc,source,output,feature) is False
            for mutation in ('status','stdout','junk','note','missing-newline','object','original'):
                bad=copy.copy(good)
                if mutation=='status': bad.returncode=0
                elif mutation=='stdout': bad.stdout='unwanted'
                elif mutation=='junk': bad.stderr+='unknown tool text\n'
                elif mutation=='note': bad.stderr+=f'{source}:1:1: note: unrelated\n'
                elif mutation=='missing-newline': bad.stderr=bad.stderr.rstrip('\n')
                elif mutation=='object': output.write_bytes(b'poison')
                else:
                    with patch.dict(CAPABILITIES,{feature:CAPABILITIES[feature]+' '}):
                        must_fail(lambda:capability(cc,source,output,feature),'changed capability fingerprint')
                    continue
                with patch.dict(globals(),{'native_result':lambda *args:bad}):
                    must_fail(lambda:capability(cc,source,output,feature),'capability '+mutation)
                output.unlink(missing_ok=True)
    for name,(_,expected) in CLANG_VALID_DISAGREEMENTS.items():
        case=next(c for c in fixtures() if c.name==name)
        source.write_text(case.owner+'\n'); output.unlink(missing_ok=True)
        good=diagnostic_result(expected,True)
        with patch.dict(globals(),{'family':lambda _:'clang18'}):
            valid_native_disagreement('clang-18',source,output,case,good)
            for mutation in ('owner','companion','name','stdout','status','junk','object'):
                badcase=copy.copy(case); bad=copy.copy(good)
                if mutation=='owner': badcase.owner+=' '
                elif mutation=='companion': badcase.companion+=' '
                elif mutation=='name': badcase.name='different source'
                elif mutation=='stdout': bad.stdout='unexpected'
                elif mutation=='status': bad.returncode=0
                elif mutation=='junk': bad.stderr+='unparsed text\n'
                else: output.write_bytes(b'stale')
                must_fail(lambda:valid_native_disagreement('clang-18',source,output,badcase,bad),'valid-case disagreement '+mutation)
                output.unlink(missing_ok=True)
        with patch.dict(globals(),{'family':lambda _:'gcc13'}):
            must_fail(lambda:valid_native_disagreement('gcc',source,output,case,good),'wrong disagreement family')
    for version in ('10.5.0','11.4.0','12.3.0','13.4.0','14.0.0','13.3.0junk','clang'):
        with patch.dict(globals(),{'native_version':lambda _:version}):
            must_fail(lambda:family('gcc'),'unreviewed GCC version')
    for version in ('17.0.0','18.0.0','18.2.0','19.0.0','18.0.0junk'):
        r=subprocess.CompletedProcess([],0,version+'\n','')
        with patch.dict(globals(),{'invoke':lambda _:r}):
            must_fail(lambda:family('clang-18'),'unreviewed Clang version')
    for triple in ('aarch64-linux-gnu\n','x86_64-linux-gnu','x86_64-linux-gnu\nunparsed\n'):
        r=subprocess.CompletedProcess([],0,triple,'')
        with patch.dict(globals(),{'invoke':lambda _:r}):
            must_fail(lambda:native_target('gcc'),'unreviewed/poisoned native target')
    # The custom native capability producer must unlink stale output itself.
    fake=d/'fake-gcc'; fake.write_text('#!/bin/sh\nexit 0\n'); fake.chmod(0o755)
    output.write_bytes(b'stale')
    must_fail(lambda:capability(str(fake),source,output,'alignas'),'stale/missing capability object')
    assert not output.exists()
    for name,text in CONSTRAINTS+POLICIES+PLACEMENT:
        source.write_text(text+'\n'); expected=KCC_MESSAGES[name]
        good=subprocess.CompletedProcess([],1,'',f'{source}:1:1: error: {expected}\n')
        kcc_refusal(source,name,good)
        for mutation in ('message','stdout','status','extra','newline','source'):
            bad=copy.copy(good)
            if mutation=='message': bad.stderr=bad.stderr.replace(expected,'unrelated failure')
            elif mutation=='stdout': bad.stdout='partial IL'
            elif mutation=='status': bad.returncode=0
            elif mutation=='extra': bad.stderr+=f'{source}:1:1: note: unrelated\n'
            elif mutation=='newline': bad.stderr=bad.stderr.rstrip('\n')
            else: source.write_text(text+' \n')
            must_fail(lambda:kcc_refusal(source,name,bad),'KCC refusal '+mutation)
            source.write_text(text+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-only',action='store_true')
    parser.add_argument('--harness-self-test',action='store_true')
    parser.add_argument('--frozen-hash')
    args=parser.parse_args()
    if not args.native_only and not args.harness_self_test:
        assert args.frozen_hash and re.fullmatch('[0-9a-f]{40}',args.frozen_hash), 'exact --frozen-hash required'
        checkout=Path(KCC).resolve().parent.parent
        head=invoke(['git','-C',checkout,'rev-parse','HEAD'])
        assert head.returncode==0 and head.stdout.strip()==args.frozen_hash, ('compiler freeze mismatch',head)
        assert Path(KCC).resolve().is_relative_to(checkout/'build')
        dirty=invoke(['git','-C',checkout,'status','--porcelain','--','src'])
        assert dirty.returncode==0 and not dirty.stdout, ('dirty production sources',dirty)
        assert QBE, 'real QBE required'
    with tempfile.TemporaryDirectory(prefix='kcc alignment ') as tmp:
        d=Path(tmp); harness_self_test(d); compiler_selection_self_test(d); controls(d)
        if args.harness_self_test:
            print('M18 alignment HARNESS CONTROLS ONLY; no production PASS'); return
        compilers=selected_compilers(); counts={cc:0 for cc in compilers}; gaps={cc:[] for cc in compilers}
        disagreements={cc:[] for cc in compilers}
        source,host,native,other,il,assembly,obj,exe=[d/n for n in ('owner.c','host.c','native.o','host.o','align.ssa','align.s','align.o','program')]
        available={}
        for cc in compilers:
            family(cc); native_target(cc)
            available[cc]=features_for(cc,source,native)
            available[cc].update(f for f in CAPABILITIES if capability(cc,source,native,f))
        kcc_count=0
        for case in fixtures():
            source.write_text(case.owner+'\n'); host.write_text(case.companion+'\n')
            for cc in compilers:
                if any(f not in available[cc] for f in case.features): gaps[cc].append(case.name); continue
                result=native_result(cc,source,native)
                if result.returncode and family(cc)=='clang18' and case.name in CLANG_VALID_DISAGREEMENTS:
                    valid_native_disagreement(cc,source,native,case,result)
                    disagreements[cc].append(case.name); continue
                assert result.returncode==0 and not result.stdout and not result.stderr and native.is_file() and native.stat().st_size, (case.name,cc,result)
                check_storage(OffsetRelocations(native),case)
                compile_native(cc,host,other); run_program(cc,[native,other]+(['-pthread'] if case.pthread else []),exe); counts[cc]+=1
            if args.native_only: continue
            r=invoke([KCC,source]); assert r.returncode==0 and not r.stderr and r.stdout, (case.name,r)
            il.write_text(r.stdout)
            producer([QBE,'-t','amd64_sysv','-o',assembly,il],assembly)
            producer([HOST,'-Wa,-L','-c',assembly,'-o',obj],obj)
            check_storage(OffsetRelocations(obj),case,True,r.stdout)
            compile_native(HOST,host,other); run_program(HOST,[obj,other]+(['-pthread'] if case.pthread else []),exe); kcc_count+=1
        for name,text in CONSTRAINTS:
            source.write_text(text+'\n')
            assert hashlib.sha256(source.read_bytes()).hexdigest()==KCC_ORIGINAL_SHA[name]
            for cc in compilers:
                r=native_result(cc,source,native)
                exact_refusal(cc,source,native,r,NATIVE_ERRORS[(family(cc),name)],text)
            if not args.native_only: kcc_refusal(source,name,invoke([KCC,source]))
        if not args.native_only:
            for name,text in POLICIES+PLACEMENT:
                source.write_text(text+'\n'); kcc_refusal(source,name,invoke([KCC,source]))
            source.write_text('_Alignas(0) '*4096+'int cell;\n')
            r=invoke([KCC,source]); assert r.returncode==0 and not r.stderr and r.stdout
            source.write_text('_Alignas(0) '*4097+'int cell;\n')
            kcc_refusal(source,'TU alignment budget',invoke([KCC,source]))
        print(f'M18 alignment: {len(fixtures())} unchanged originals; KCC/QBE/ELF/runtime {kcc_count}; {len(CONSTRAINTS)} exact native constraints per compiler')
        for cc in compilers:
            print(f'{cc}: {counts[cc]} agreements; {len(gaps[cc])} capability gaps: {gaps[cc]}; '
                  f'{len(disagreements[cc])} exact valid-case Clang18 disagreements (NOT agreements): {disagreements[cc]}')
        if args.native_only: print('NATIVE-ONLY: no frozen KCC coverage/PASS claimed')
        else: print('Frozen production hash: '+args.frozen_hash+f'; {len(POLICIES)} compile-only target/UB-policy refusals')


if __name__=='__main__': main()

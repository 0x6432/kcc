"""M15 genuine TLS: unchanged originals, STT_TLS/SHF_TLS/relocs, pthread lifetime.

KCC=... QBE=... HOST_CC=cc CLANG_CC=... python3 tests/test_thread_storage.py
--native-only never claims KCC coverage. --harness-self-test runs imported adversarial producer controls.
Native sources are never rewritten, macro-adapted, or run when invalid. Only
curated defined programs execute; constraint/deferred sources compile only.
The host pthread companion declares TLS with _Thread_local, not ordinary extern.
AST oracle: compile test_thread_storage_ast.c with the selected source checkout's
src/*.c excluding main.c (no Makefile modifications are needed).
"""
import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile

from test_integer_initializers import (
    KCC, HOST, QBE, invoke, producer, clang_style, native_diagnostics,
    harness_self_test, reject, features_for,
)
from test_null_initializers import native_compilers, compiler_selection_self_test
from test_direct_address_initializers import ElfRelocations, Reference


@dataclass(frozen=True)
class Case:
    name: str
    units: tuple
    # Per unit: (source name or None for block-generated, width, value, public).
    objects: tuple
    values: tuple
    declarations: str = ''
    binding: str = '1'
    keyword: str = '_Thread_local'
    ctype: str = 'int'
    features: tuple = ()
    references: tuple = ()
    addresses: tuple = ()


def fixtures():
    cases = []
    for kw in ('_Thread_local', 'thread_local'):
        def add(name, units, objects, values, declarations='', binding='1', ctype='int', features=(), references=(), addresses=()):
            cases.append(Case(kw+' '+name, tuple(units), tuple(objects), tuple(values),
                              declarations, binding, kw, ctype, features, references, addresses))
        add('external initialized and implicit zero',
            [f'{kw} int cell=40; {kw} int zero; extern {kw} int absent; '
             'int *slot(int n) { return n?&zero:&cell; }'],
            [(('cell', 4, 40, True), ('zero', 4, 0, True))], [40, 0],
            'extern _Thread_local int cell,zero;', 'slot(0)==&cell && slot(1)==&zero')
        add('private initialized explicit zero and extern inheritance',
            [f'static {kw} int cell=41; extern {kw} int cell; '
             f'{kw} static int zero=0; '
             'int *slot(int n) { return n?&zero:&cell; }'],
            [(('cell', 4, 41, False), ('zero', 4, 0, False))], [41, 0])
        add('redeclarations and one initialized owner',
            [f'extern {kw} int cell; {kw} int cell=42; '
             f'extern {kw} int cell; '
             'int *slot(int n) { return &cell; }'],
            [(('cell', 4, 42, True),)], [42],
            'extern _Thread_local int cell;', 'slot(0)==&cell')
        add('external two compiled translation units',
            [f'{kw} int cell=43; int *owner_slot(void) {{ return &cell; }}',
             f'extern {kw} int cell; int *owner_slot(void); '
             'int *slot(int n) { return owner_slot()==&cell?&cell:0; }'],
            [(('cell', 4, 43, True),), ()], [43],
            'extern _Thread_local int cell;', 'slot(0)==&cell')
        add('private same spelling across translation units',
            [f'static {kw} int cell=44; int *owner_slot(void) {{ return &cell; }}',
             f'static {kw} int cell=45; int *owner_slot(void); '
             'int *slot(int n) { return n?&cell:owner_slot(); }'],
            [(('cell', 4, 44, False),), (('cell', 4, 45, False),)], [44, 45])
        add('block static same spelling nested scopes and functions',
            [f'int *other(void) {{ static {kw} int cell=48; return &cell; }} '
             f'int *slot(int n) {{ {kw} static int cell=46; '
             f'if(n==1) {{ static {kw} int cell=47; return &cell; }} '
             'return n==2?other():&cell; }'],
            [((None, 4, 48, False), (None, 4, 46, False), (None, 4, 47, False))], [46, 47, 48])
        add('block zero initialization and no reinitialization',
            [f'int *slot(int n) {{ static {kw} int cell; '
             f'{{ static {kw} int zero=0; if(n) return &zero; }} return &cell; }}'],
            [((None, 4, 0, False), (None, 4, 0, False))], [0, 0])
        add('automatic parameter and TLS shadow source bindings',
            [f'{kw} int cell=49; int take(int cell) {{ return cell; }} '
             f'int *slot(int n) {{ int *saved=&cell; {{ int cell=3; '
             'if(take(cell)!=3) return 0; } '
             f'if(n) {{ static {kw} int cell=50; return &cell; }} return saved; }}'],
            [(('cell', 4, 49, True), (None, 4, 50, False))], [49, 50],
            'extern _Thread_local int cell;', 'slot(0)==&cell')
        add('block extern aliases file TLS and scope restores',
            [f'{kw} int cell=51; int *slot(int n) {{ int *saved=&cell; '
             f'{{ extern {kw} int cell; if(saved!=&cell) return 0; }} '
             'return &cell; }'], [(('cell', 4, 51, True),)], [51],
            'extern _Thread_local int cell;', 'slot(0)==&cell')
        add('block extern before later file declaration',
            [f'int *slot(int n) {{ extern {kw} int cell; return &cell; }} '
             f'{kw} int cell=52;'], [(('cell', 4, 52, True),)], [52],
            'extern _Thread_local int cell;', 'slot(0)==&cell')
        add('typedef source root and placement',
            [f'typedef int I; {kw} I cell=53; I {kw} zero; '
             'int *slot(int n) { return n?&zero:&cell; }'],
            [(('cell', 4, 53, True), ('zero', 4, 0, True))], [53, 0])
        add('TLS null pointer initialized once per thread',
            [f'{kw} int cell=54; {kw} int *pointer=0; '
             'int *slot(int n) { if(!pointer) pointer=&cell; return pointer; }'],
            [(('cell', 4, 54, True), ('pointer', 8, 0, True))], [54])
        add('TLS null pointer zero definition',
            [f'{kw} int cell=55; {kw} int *pointer; '
             'int *slot(int n) { if(!pointer) pointer=&cell; return pointer; }'],
            [(('cell', 4, 55, True), ('pointer', 8, 0, True))], [55])
        add('TLS array zero storage and element identity',
            [f'{kw} int cells[3]; int *slot(int n) {{ return &cells[n]; }}'],
            [(('cells', 12, 0, True),)], [0, 0, 0],
            'extern _Thread_local int cells[3];',
            'slot(0)==&cells[0] && slot(1)==&cells[1] && slot(2)==&cells[2]')
        add('visible complete bound before zero definition',
            [f'extern {kw} int cells[3]; {kw} int cells[]; '
             'int *slot(int n) { return &cells[n]; }'],
            [(('cells', 12, 0, True),)], [0, 0, 0])
        for typ,width,expression,value,features in (
                ('char',1,'-7',-7,()),
                ('short',2,'-12345',-12345,()),
                ('long',8,'4294967297L',4294967297,()),
                ('unsigned long long',8,'18446744073709551615ULL',18446744073709551615,()),
                ('_Bool',1,'1',1,()),
                ('bool',1,'true',1,('bool',)),
                ('typeof(nullptr)',8,'nullptr',0,('typeof','nullptr'))):
            add('typed initialized and zero '+typ,
                [f'{kw} {typ} cell={expression}; static {kw} {typ} zero; '
                 f'{typ} *slot(int n) {{ return n?&zero:&cell; }}'],
                [(('cell',width,value,True),('zero',width,0,False))],
                [expression,'nullptr' if typ=='typeof(nullptr)' else '0'],
                ctype=typ,features=features)
        for name,target,pointer,check,reference in (
                ('global','int ordinary=42;','int *pointer=&ordinary;',
                 'pointer==&ordinary && *pointer==42',Reference('object','ordinary')),
                ('private','static int ordinary=42;','int *pointer=&ordinary;',
                 'pointer==&ordinary && *pointer==42',Reference('object','ordinary')),
                ('function','static int target(void) { return 42; }',
                 'int (*pointer)(void)=target;',
                 'pointer==target && pointer()==42',Reference('function','target')),
                ('string','','char *pointer="tls";',
                 'pointer[0]==116 && pointer[1]==108 && pointer[2]==115 && pointer[3]==0',
                 Reference('string',contents=b'tls\0'))):
            declaration=('extern _Thread_local int (*pointer)(void);' if name=='function' else
                         'extern _Thread_local char *pointer;' if name=='string' else
                         'extern _Thread_local int *pointer;')
            add('legal static pointer initializer '+name,
                [target+f' {kw} '+pointer+f' {kw} int cell=56; '
                 'const void *pointer_slot(void) { return &pointer; } '
                 f'int *slot(int n) {{ return ({check})?&cell:0; }}'],
                [(('pointer',8,0,True),('cell',4,56,True))], [56],
                declaration+' const void *pointer_slot(void);',
                'pointer_slot()==&pointer', references=({'pointer':reference},),addresses=('&pointer',))
    return cases


def companion(case):
    """No thread ever indirectly accesses another thread's TLS object.

    All three live threads mutate separate copies concurrently. Joining and
    then starting a fresh thread also tests reinitialization of the new copy.
    Published addresses are compared only while both lifetime barriers hold;
    no published pointer is read after its owning thread can exit.
    """
    count = len(case.values)
    typ=case.ctype
    marker='nullptr' if typ=='typeof(nullptr)' else '(id+i+round)%2' if typ in ('_Bool','bool') else 'id*10+i+round%7'
    address_count=count+len(case.addresses)
    additional=''.join(f'addresses[id-1][{count+i}]={expr};' for i,expr in enumerate(case.addresses))
    return f'''#define _POSIX_C_SOURCE 200809L
#include <pthread.h>
#include <sched.h>
{case.declarations}
{typ} *slot(int);
static {typ} marker(int id,int i,int round) {{ return {marker}; }}
static const void *addresses[3][{address_count}];
static pthread_barrier_t barrier;
struct job {{ int id; int wait; int result; }};
static int exercise(int id, int wait) {{
    {typ} expected[{count}]={{{','.join(map(str, case.values))}}};
    {typ} *saved[{count}]; int bad=0;
    for(int i=0;i<{count};i++) {{
        saved[i]=slot(i);
        if(!saved[i]) bad=1;
        else if(*saved[i]!=expected[i]) bad=1;
        for(int j=0;j<i;j++) if(saved[i]==saved[j]) bad=1;
    }}
    if(!({case.binding})) bad=1;
    if(wait) {{
        for(int i=0;i<{count};i++) addresses[id-1][i]=saved[i];
        {additional}
        int b=pthread_barrier_wait(&barrier);
        if(b && b!=PTHREAD_BARRIER_SERIAL_THREAD) bad=1;
        /* Equality only: no thread indirectly accesses another thread's TLS.
         * Both barriers keep every referenced object's thread alive. */
        for(int other=0;other<3;other++) if(other!=id-1)
            for(int i=0;i<{address_count};i++)
                if(addresses[id-1][i]==addresses[other][i]) bad=1;
        b=pthread_barrier_wait(&barrier);
        if(b && b!=PTHREAD_BARRIER_SERIAL_THREAD) bad=1;
    }}
    for(int round=0;round<400;round++) {{
        for(int i=0;i<{count};i++) {{
            if(!saved[i]) continue;
            if(slot(i)!=saved[i]) bad=1;
            if(round && *saved[i]!=marker(id,i,round-1)) bad=1;
            *saved[i]=marker(id,i,round);
        }}
        sched_yield();
    }}
    for(int i=0;i<{count};i++)
        if(saved[i] && (slot(i)!=saved[i] || *saved[i]!=marker(id,i,399))) bad=1;
    return bad;
}}
static void *worker(void *p) {{ struct job *j=p;
    j->result=exercise(j->id,j->wait); return 0; }}
int main(void) {{
    pthread_t a,b; struct job x={{1,1,1}},y={{2,1,1}},z={{4,0,1}};
    if(pthread_barrier_init(&barrier,0,3)) return 1;
    if(pthread_create(&a,0,worker,&x) || pthread_create(&b,0,worker,&y)) return 2;
    int bad=exercise(3,1);
    if(pthread_join(a,0) || pthread_join(b,0)) return 3;
    if(bad || x.result || y.result) return 4;
    for(int i=0;i<{count};i++) if(*slot(i)!=marker(3,i,399)) return 5;
    if(pthread_create(&a,0,worker,&z) || pthread_join(a,0) || z.result) return 6;
    for(int i=0;i<{count};i++) if(*slot(i)!=marker(3,i,399)) return 7;
    if(pthread_barrier_destroy(&barrier)) return 8;
    return 42;
}}
'''


# True language constraints only; no invalid source is executed. Mixed internal/
# external linkage UB is deliberately NOT a native comparison.
CONSTRAINTS = [
    ('int f(void) { _Thread_local int cell; return 0; }',
     'block-scope thread_local requires static or extern'),
    ('register _Thread_local int cell;', 'thread_local may combine only with static or extern storage'),
    ('typedef _Thread_local int Cell;', 'thread_local may combine only with static or extern storage'),
    ('_Thread_local int f(void);', 'thread_local requires an object type'),
    ('_Thread_local int f(void) { return 0; }', 'thread_local requires an object type'),
    ('int f(_Thread_local int cell) { return cell; }', 'thread_local is not permitted in a type name or parameter declaration'),
    ('int cell; extern _Thread_local int cell;', 'thread_local declaration conflicts with prior storage duration'),
    ('_Thread_local int cell; extern int cell;', 'thread_local declaration conflicts with prior storage duration'),
    ('int f(void) { extern _Thread_local int cell=1; return 0; }', 'block-scope extern declaration cannot have an initializer'),
    ('_Thread_local int cell=1; _Thread_local int cell=2;', 'multiple initialized definitions of object'),
    ('_Thread_local int cell; int f(void) { extern int cell; return cell; }',
     'thread_local declaration conflicts with prior storage duration'),
    ('int cell; int f(void) { extern _Thread_local int cell; return cell; }',
     'thread_local declaration conflicts with prior storage duration'),
    ('_Thread_local int cell; int *p=&cell;', 'thread-local object address is not a static address constant'),
    ('_Thread_local int cell; _Thread_local int *p=&cell;', 'thread-local object address is not a static address constant'),
    ('_Thread_local int cell[2]; int *p=cell;', 'thread-local object address is not a static address constant'),
    ('_Thread_local int cell; int f(void) { static int *p=&cell; return 0; }', 'thread-local object address is not a static address constant'),
    ('int f(void) { static _Thread_local int cell; static _Thread_local int *p=&cell; return 0; }', 'thread-local object address is not a static address constant'),
]
# Address offsets are still not address constants (and need M15 offset support).
ADDRESS_CONSTRAINTS = [
    '_Thread_local int cell[2]; int *p=&cell[1];',
    '_Thread_local int cell[2]; _Thread_local int *p=cell+1;',
    '_Thread_local int cell; void *p=(void *)&cell;',
]


# C23 6.9.2: a non-extern TLS declaration without initializer is a zero
# definition, NOT a tentative definition. Old native implementations admit some
# of these as extensions even with -pedantic-errors: never execute or count them
# as native constraint agreements. TLS+auto is legal C23 but M23e inference is
# a supported-subset refusal, likewise never a native language-constraint claim.
KCC_ONLY = [
    ('_Thread_local int cell; _Thread_local int cell;', 'multiple definitions of thread_local object'),
    ('thread_local int cell=1; thread_local int cell;', 'multiple definitions of thread_local object'),
    ('_Thread_local int cell; _Thread_local int cell=1;', 'multiple initialized definitions of object'),
    ('_Thread_local int cells[];', 'thread_local definition requires a complete object type'),
    ('thread_local int cells[]; extern thread_local int cells[3];', 'thread_local definition requires a complete object type'),
    ('thread_local auto cell=42;', 'thread_local auto inference is not supported yet'),
    ('thread_local auto int cell=42;', 'thread_local auto inference is not supported yet'),
    ('int f(void) { static thread_local auto cell=42; return 0; }', 'thread_local auto inference is not supported yet'),
    ('thread_local int f(void);', 'thread_local requires an object type'),
    ('int f(void) { thread_local int cell; return 0; }', 'block-scope thread_local requires static or extern'),
]


# Exact full native diagnostic streams, keyed by the unchanged original.
NATIVE_CONSTRAINTS = {
    'int f(void) { _Thread_local int cell; return 0; }': (
        (('error', "function-scope 'cell' implicitly auto and declared '_Thread_local'"),),
        (('error', "'_Thread_local' variables must have global storage"),)),
    'register _Thread_local int cell;': (
        (('error', "'_Thread_local' used with 'register'"), ('error', "file-scope declaration of 'cell' specifies 'register' [-Wpedantic]"), ('error', "register name not specified for 'cell'")),
        (('error', "cannot combine with previous 'register' declaration specifier"), ('error', 'illegal storage class on file-scoped variable'))),
    'typedef _Thread_local int Cell;': (
        (('error', "'_Thread_local' used with 'typedef'"),),
        (('error', "cannot combine with previous 'typedef' declaration specifier"),)),
    '_Thread_local int f(void);': (
        (('error', "invalid storage class for function 'f'"),),
        (('error', "'_Thread_local' is only allowed on variable declarations"),)),
    '_Thread_local int f(void) { return 0; }': (
        (('error', "function definition declared '_Thread_local'"),),
        (('error', "'_Thread_local' is only allowed on variable declarations"),)),
    'int f(_Thread_local int cell) { return cell; }': (
        (('error', "storage class specified for parameter 'cell'"),),
        (('error', "'_Thread_local' is only allowed on variable declarations"),)),
    'int cell; extern _Thread_local int cell;': (
        (('error', "thread-local declaration of 'cell' follows non-thread-local declaration"), ('note', "previous declaration of 'cell' with type 'int'")),
        (('error', "thread-local declaration of 'cell' follows non-thread-local declaration"), ('note', 'previous definition is here'))),
    '_Thread_local int cell; extern int cell;': (
        (('error', "non-thread-local declaration of 'cell' follows thread-local declaration"), ('note', "previous declaration of 'cell' with type 'int'")),
        (('error', "non-thread-local declaration of 'cell' follows thread-local declaration"), ('note', 'previous definition is here'))),
    'int f(void) { extern _Thread_local int cell=1; return 0; }': (
        (('error', "'cell' has both 'extern' and initializer"),),
        (('error', 'declaration of block scope identifier with linkage cannot have an initializer'),)),
    '_Thread_local int cell=1; _Thread_local int cell=2;': (
        (('error', "redefinition of 'cell'"), ('note', "previous definition of 'cell' with type 'int'")),
        (('error', "redefinition of 'cell'"), ('note', 'previous definition is here'))),
    '_Thread_local int cell; int f(void) { extern int cell; return cell; }': (
        (('error', "non-thread-local declaration of 'cell' follows thread-local declaration"), ('note', "previous declaration of 'cell' with type 'int'")),
        (('error', "non-thread-local declaration of 'cell' follows thread-local declaration"), ('note', 'previous definition is here'))),
    'int cell; int f(void) { extern _Thread_local int cell; return cell; }': (
        (('error', "thread-local declaration of 'cell' follows non-thread-local declaration"), ('note', "previous declaration of 'cell' with type 'int'")),
        (('error', "thread-local declaration of 'cell' follows non-thread-local declaration"), ('note', 'previous definition is here'))),
    '_Thread_local int cell; int *p=&cell;': (
        (('error', 'initializer element is not constant'),),
        (('error', 'initializer element is not a compile-time constant'),)),
    '_Thread_local int cell; _Thread_local int *p=&cell;': (
        (('error', 'initializer element is not constant'),),
        (('error', 'initializer element is not a compile-time constant'),)),
    '_Thread_local int cell[2]; int *p=cell;': (
        (('error', 'initializer element is not constant'),),
        (('error', 'initializer element is not a compile-time constant'),)),
    '_Thread_local int cell; int f(void) { static int *p=&cell; return 0; }': (
        (('error', 'initializer element is not constant'),),
        (('error', 'initializer element is not a compile-time constant'),)),
    'int f(void) { static _Thread_local int cell; static _Thread_local int *p=&cell; return 0; }': (
        (('error', 'initializer element is not constant'),),
        (('error', 'initializer element is not a compile-time constant'),)),
    '_Thread_local int cell[2]; int *p=&cell[1];': (
        (('error', 'initializer element is not constant'),),
        (('error', 'initializer element is not a compile-time constant'),)),
    '_Thread_local int cell[2]; _Thread_local int *p=cell+1;': (
        (('error', 'initializer element is not constant'),),
        (('error', 'initializer element is not a compile-time constant'),)),
    '_Thread_local int cell; void *p=(void *)&cell;': (
        (('error', 'initializer element is not constant'),),
        (('error', 'initializer element is not a compile-time constant'),)),
}


class TLS(ElfRelocations):
    def check(self, expected, qbe=False, required=(), references=None):
        for name in required:
            symbol=self.symbol(name)
            assert symbol['kind']==6, ('not STT_TLS', symbol)
        defined = [s for s in self.symbols if s['kind']==6 and s['section']]
        assert len(defined)==len(expected), ('TLS definition count', defined, expected)
        for symbol in self.symbols:
            if symbol['kind']!=6:
                continue
            uses=[r for r in self.relocations if r['symbol'] is symbol]
            assert uses, ('TLS symbol without TLS reference', symbol)
            assert all(r['kind'] in (19,22,23) and r['addend']=={19:-4,22:-4,23:0}[r['kind']] for r in uses), uses
            if not symbol['section']:
                assert symbol['binding']==1
        assert not [s for s in self.symbols if s['name']=='absent' and s['section']]
        used = set()
        for name,width,value,public in expected:
            candidates = [s for s in defined if s['name'] not in used and
                          (s['name']==name if name is not None else s['binding']==0)]
            wanted = (value % (1 << (8*width))).to_bytes(width,'little')
            matches=[]
            for s in candidates:
                section=self.sections[s['section']]
                assert section[2] & 0x400, ('missing SHF_TLS', s, section)
                assert section[1] in (1,8) and section[2] & 3 == 3
                assert s['size']==(0 if qbe else width), ('TLS size', s)
                alignment=min(width & -width,8)
                assert section[8]>=alignment and s['value']%alignment==0
                assert s['value']+width<=section[5]
                contents=bytes(width) if section[1]==8 else self.section_bytes(s['section'])[s['value']:s['value']+width]
                if contents==wanted and s['binding']==int(public):
                    matches.append(s)
            assert matches, ('missing TLS bytes/binding', name, wanted, candidates)
            s=matches[0]
            used.add(s['name'])
            # Local block-static symbols may share contents; consume each once.
            relocs=[r for r in self.relocations if r['symbol'] is s and r['kind'] in (19,22,23)]
            assert relocs, ('no actual TLS address relocation', s, self.relocations)
            assert all(r['kind'] in (19,22,23) for r in self.relocations if r['symbol'] is s), (
                'ordinary address relocation against TLS', s, self.relocations)
        assert len(used)==len(defined)
        if references:
            ElfRelocations.check(self,references)
        # No ordinary data definition may stand in for one of the named TLS objects.
        assert not [s for s in self.symbols if s['name'] in {e[0] for e in expected if e[0]}
                    and s['section'] and s['kind']!=6]


def check_il(text, expected, references=None):
    definitions = re.findall(r'^(export )?(thread )?data \$([^\s=]+)\s*=\s*align (\d+)\s*\{([^}]+)\}', text, re.M)
    definitions=[d for d in definitions if d[1]]
    assert len(definitions)==len(expected), (text,expected)
    remaining=list(definitions)
    for name,width,value,public in expected:
        matches=[d for d in remaining if (name is None or d[2]==name) and bool(d[0])==public and d[1]]
        leaf={1:'b',2:'h',4:'w',8:'l'}.get(width)
        value=value % (1 << (width*8))
        wanted=rf'\s*(?:{leaf}\s+{value}|z\s+{width})\s*' if value==0 else rf'\s*{leaf}\s+{value}\s*'
        if references and name in references:
            wanted=r'\s*l\s+\$[^\s,}]+\s*'
        matches=[d for d in matches if int(d[3])==min(width & -width,8) and re.fullmatch(wanted,d[4])]
        assert matches, (name,expected,text)
        d=matches[0]; remaining.remove(d)
        assert re.search(r'\bthread \$'+re.escape(d[2])+r'(?![\w.])', text), text
        # Every runtime use of a known TLS symbol must retain thread decoration.
        body=re.sub(r'^(?:export )?thread data[^\n]*','',text,flags=re.M)
        assert not re.search(r'(?<!thread )\$'+re.escape(d[2])+r'(?![\w.])',body), text
    assert not remaining


def keyword_unavailable(result, source, output):
    text='thread_local int cell;'
    fix='      |             ;\n'
    if result.returncode!=1 or result.stdout or output.exists():
        return False
    if result.stderr.count(fix)>1:
        return False
    diagnostics=native_diagnostics(result.stderr.replace(fix,''),source,text,False)
    return diagnostics==(('error', "expected ';' before 'int'"),)


def keyword_support(cc, directory):
    source,output=directory/'keyword.c',directory/'keyword.o'
    source.write_text('thread_local int cell;\n'); output.unlink(missing_ok=True)
    result=invoke([cc,'-std=c2x','-pedantic-errors','-c',source,'-o',output])
    assert not result.stdout
    if result.returncode==0:
        assert not result.stderr and output.is_file() and output.stat().st_size
        return True
    assert not clang_style(cc) and keyword_unavailable(result,source,output), result
    return False


def controls(directory):
    """Fail closed on poisoned keyword verdicts, TLS bytes/type/flags/relocs."""
    from subprocess import CompletedProcess
    source,output=directory/'tls-control.c',directory/'tls-control.o'
    text='thread_local int cell;'
    good=f"{source}:1:13: error: expected ';' before 'int'\n    1 | {text}\n      |             ^~~~\n      |             ;\n"
    output.unlink(missing_ok=True)
    assert keyword_unavailable(CompletedProcess([],1,'',good),source,output)
    for code in (0,2,127,-6,-9,-11):
        assert not keyword_unavailable(CompletedProcess([],code,'',good),source,output)
    for extra in ('unexpected stderr\n', 'internal compiler error\n',
                  f'{source}:1:1: warning: extra\n', f'{source}:1:1: note: extra\n',
                  '1 error generated.\n','      |             ;\n'):
        assert not keyword_unavailable(CompletedProcess([],1,'',good+extra),source,output)
    assert not keyword_unavailable(CompletedProcess([],1,'stdout',good),source,output)
    output.write_bytes(b'stale')
    assert not keyword_unavailable(CompletedProcess([],1,'',good),source,output)
    source.write_text('_Thread_local int cell=42; int *slot(void) { return &cell; }\n')
    producer([HOST,'-std=c11','-fno-common','-c',source,'-o',output],output)
    expected=(('cell',4,42,True),)
    elf=TLS(output); elf.check(expected,required=('cell',))
    header=struct.unpack_from('<16sHHIQQQIHHHHHH',elf.data)
    symtab=next(section for section in elf.sections if section[1]==2)
    strings=elf.section_bytes(symtab[6])
    position=next(pos for pos in range(symtab[4],symtab[4]+symtab[5],24)
                  if strings[struct.unpack_from('<I',elf.data,pos)[0]:].split(b'\0',1)[0]==b'cell')
    symbol=elf.symbol('cell'); section=elf.sections[symbol['section']]
    reloc=next(section for section in elf.sections if section[1]==4 and
               any(r['symbol']['name']=='cell' and r['section']==section[7] for r in elf.relocations))
    poisoned=[]
    data=bytearray(elf.data); data[position+4]=(1<<4)|1; poisoned.append(data)  # STT_OBJECT
    data=bytearray(elf.data); struct.pack_into('<Q',data,header[6]+64*symbol['section']+8,section[2]&~0x400); poisoned.append(data)
    data=bytearray(elf.data); data[section[4]+symbol['value']]^=1; poisoned.append(data)
    data=bytearray(elf.data); info=struct.unpack_from('<Q',data,reloc[4]+8)[0]; struct.pack_into('<Q',data,reloc[4]+8,(info&~0xffffffff)|1); poisoned.append(data)
    data=bytearray(elf.data); struct.pack_into('<q',data,reloc[4]+16,4); poisoned.append(data)
    for data in poisoned:
        output.write_bytes(data)
        try:
            TLS(output).check(expected,required=('cell',))
        except AssertionError:
            pass
        else:
            raise AssertionError('corrupt TLS ELF accepted')
    il='export thread data $cell = align 4 { w 42 }\nexport function l $slot() {\n@start\n %p =l copy thread $cell\n ret %p\n}\n'
    check_il(il,expected)
    for bad in (il.replace('export thread data','export data'),
                il.replace('copy thread $cell','copy $cell'),
                il.replace('w 42','w 41'), il.replace('align 4','align 8'),
                il.replace('export thread data','thread data'), il+il):
        try:
            check_il(bad,expected)
        except AssertionError:
            pass
        else:
            raise AssertionError('corrupt TLS IL accepted')
    print('TLS-specific keyword, ELF and IL adversarial controls passed')


def run(linker, objects, output):
    producer([linker,*objects,'-pthread','-o',output],output)
    result=invoke([output])
    assert (result.returncode,result.stdout,result.stderr)==(42,'',''), result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-only',action='store_true')
    parser.add_argument('--harness-self-test',action='store_true')
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='kcc TLS ') as temporary:
        d=Path(temporary)
        harness_self_test(d); compiler_selection_self_test(d); controls(d)
        if args.harness_self_test:
            print('TLS imported producer/native-selection adversarial controls passed')
            return
        compilers=native_compilers(HOST,os.environ.get('CLANG_CC') or shutil.which('clang'))
        supported={cc:features_for(cc,d/'probe.c',d/'probe.o') | ({'thread_local'} if keyword_support(cc,d) else set()) for cc in compilers}
        counts={cc:[0,0,0] for cc in compilers}
        kcc_count=qbe_count=refusals=0
        for case in fixtures():
            public={row[0] for rows in case.objects for row in rows if row[3]}
            required=[{name for name in public if re.search(r'\b'+re.escape(name)+r'\b',text)} for text in case.units]
            refs=case.references or tuple({} for _ in case.units)
            sources=[]
            for i,text in enumerate(case.units):
                source=d/f'unit{i}.c'; source.write_text(text+'\n'); sources.append(source)
            host=d/'pthread.c'; host.write_text(companion(case))
            for cc in compilers:
                if not set(case.features+(('thread_local',) if case.keyword=='thread_local' else ())) <= supported[cc]:
                    counts[cc][1]+=1; continue
                objects=[]
                for i,source in enumerate(sources):
                    obj=d/f'native{i}.o'
                    producer([cc,'-std=c2x','-pedantic-errors','-fno-common','-fsigned-char','-O0','-c',source,'-o',obj],obj)
                    TLS(obj).check(case.objects[i],required=required[i],references=refs[i]); objects.append(obj)
                other=d/'pthread.o'
                producer([cc,'-std=c2x','-pedantic-errors','-fno-common','-fsigned-char','-O0','-pthread','-c',host,'-o',other],other)
                run(cc,[*objects,other],d/'native')
                counts[cc][0]+=1
            if args.native_only:
                continue
            objects=[]
            for i,source in enumerate(sources):
                result=invoke([KCC,source])
                assert result.returncode==0 and not result.stderr and result.stdout,(case.name,result)
                check_il(result.stdout,case.objects[i],refs[i])
                if QBE:
                    il,assembly,obj=d/f'{i}.ssa',d/f'{i}.s',d/f'{i}.o'
                    il.write_text(result.stdout)
                    producer([QBE,'-t','amd64_sysv','-o',assembly,il],assembly)
                    producer([HOST,'-c',assembly,'-o',obj],obj)
                    TLS(obj).check(case.objects[i],qbe=True,required=required[i],references=refs[i]); objects.append(obj)
            kcc_count+=1
            if QBE:
                other=d/'pthread.o'
                companion_cc=next((cc for cc in compilers if set(case.features)<=supported[cc]),None)
                assert companion_cc, ('no compiler supports exact pthread companion',case.name)
                producer([companion_cc,'-std=c2x','-pedantic-errors','-fno-common','-fsigned-char','-O0','-pthread','-c',host,'-o',other],other)
                run(companion_cc,[*objects,other],d/'qbe-program'); qbe_count+=1
        for text,message in CONSTRAINTS+[(text,'thread-local object address is not a static address constant') for text in ADDRESS_CONSTRAINTS]:
            source=d/'constraint.c'; source.write_text(text+'\n')
            for cc in compilers:
                output=d/'constraint.o'; output.unlink(missing_ok=True)
                result=invoke([cc,'-std=c2x','-pedantic-errors','-fno-common','-c',source,'-o',output])
                assert result.returncode==1 and not result.stdout and not output.exists(), result
                assert native_diagnostics(result.stderr,source,text,clang_style(cc))==NATIVE_CONSTRAINTS[text][int(clang_style(cc))], result.stderr
                counts[cc][2]+=1
            if not args.native_only:
                reject(source,'error: '+message+'\n'); refusals+=1
        if not args.native_only:
            for text,message in KCC_ONLY:
                source=d/'constraint.c'; source.write_text(text+'\n')
                reject(source,'error: '+message+'\n'); refusals+=1
        print(f'TLS: {len(fixtures())} unchanged originals; KCC {kcc_count}; '
              f'QBE ELF TLS/relocation/pthread {qbe_count}; compile-only refusals {refusals}')
        for cc,(agreements,gaps,constraints) in counts.items():
            print(f'{cc}: {agreements} unchanged ELF TLS/pthread agreements; '
                  f'{gaps} keyword/feature-unavailable (NOT agreements); {constraints} native constraints')
        if args.native_only:
            print('NATIVE-ONLY: no claim of KCC coverage')
        elif not QBE:
            print('QBE unset: no claim of ELF TLS/pthread KCC coverage')


if __name__=='__main__':
    main()

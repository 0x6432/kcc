"""Independent M17 compound literal/runtime composition oracle.

Only unchanged defined originals execute. Automatic pointers are never inspected
past their enclosing block or activation. Const literal merging and aggregate
padding are deliberately unconstrained. --native-only is never a KCC PASS.
KCC=... QBE=... HOST_CC=... CLANG_CC=... [GCC13_CC=...] select tools, not paths.
A production run requires --frozen-hash and a clean exact compiler checkout.
"""
import argparse
import copy
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from unittest.mock import patch

from test_integer_initializers import (
    KCC, HOST, QBE, invoke, producer, clang_style, native_diagnostics,
    harness_self_test, run_program, features_for,
)
from test_null_initializers import native_compilers, compiler_selection_self_test
from test_address_offsets import OffsetRelocations, diagnostic_flags

ROOT = Path(__file__).resolve().parents[1]
S = 'struct S { int x; int a[2]; int *p; }; '


@dataclass(frozen=True)
class Literal:
    width: int
    alignment: int
    # Only value bytes, never nonempty aggregate padding.
    values: tuple = ()
    # (byte offset, referenced child Literal, logical byte addend)
    links: tuple = ()


def ints(*values):
    return b''.join(int(v).to_bytes(4, 'little', signed=True) for v in values)


@dataclass
class Case:
    name: str
    owner: str
    companion: str = 'int test(void); int main(void) { return test(); }'
    # public pointer slot -> (literal object, logical subobject offset)
    roots: dict = field(default_factory=dict)
    features: tuple = ()
    storage: bool = False
    no_data: bool = False
    pthread: bool = False
    tls_literal: bool = False
    expected_exit: int = 42
    gcc11_disagreement: bool = False
    native_optional_pool: bytes | None = None


def fixtures():
    cases = []
    def local(name, body, header='', **kw):
        cases.append(Case(name, header+'int test(void) { '+body+' }', **kw))
    local('scalar literal is modifiable lvalue',
          'int *p=&(int){40}; int old=(*p)++; int now=++*p; '
          'return old==40 && now==42 && *p==42?42:1;')
    local('postfix update literal', 'int n=(int){41}++; int m=++(int){40}; return n+m==82?42:1;')
    local('literal update initializer once',
          'int n=40; int old=(int){n++}++; return n==41 && old==40?42:1;')
    local('scalar pointer literal and null',
          'int x=42; int **p=&(int *){&x}; int *q=(int *){0}; return **p==42 && q==0?42:1;')
    local('integer scalar literal families',
          '_Bool b=(_Bool){7}; signed char c=(signed char){-7}; '
          'unsigned char uc=(unsigned char){250}; short h=(short){-12345}; '
          'unsigned short uh=(unsigned short){60000}; unsigned u=(unsigned){4000000000U}; '
          'long l=(long){-4294967297L}; unsigned long ul=(unsigned long){18446744073709551615UL}; '
          'long long ll=(long long){-9223372036854775807LL}; '
          'unsigned long long ull=(unsigned long long){18446744073709551615ULL}; '
          'return b==1 && c==-7 && uc==250 && h==-12345 && uh==60000 && u==4000000000U && '
          'l==-4294967297L && ul==18446744073709551615UL && ll==-9223372036854775807LL && ull==18446744073709551615ULL?42:1;')
    local('empty supported literal type families',
          'int x=(int){}; int *p=(int *){}; _Bool b=(_Bool){}; '
          'struct S s=(struct S){}; int *a=(int[2]){}; union U u=(union U){}; '
          'return x==0 && p==0 && b==0 && s.x==0 && s.a[0]==0 && s.a[1]==0 && s.p==0 && '
          'a[0]==0 && a[1]==0 && u.l==0?42:1;', S+'union U { long l; int a[2]; }; ', features=('empty',))
    cases.append(Case('file empty scalar literal zero bytes',
        'int *cell=&(int){};', 'extern int *cell; int main(void) { return *cell==0?42:1; }',
        {'cell':(Literal(4,4,((0,bytes(4)),)),0)}, features=('empty',)))
    local('nullptr scalar literal',
          'int *p=(typeof(nullptr)){nullptr}; return p==0?42:1;', features=('typeof','nullptr'))
    local('function pointer scalar literal',
          'int (*p)(int)=(int (*)(int)){add}; return p(40);',
          'int add(int x) { return x+2; } ')
    local('qualified scalar without merging claim',
          'const int *p=&(const int){42}; return *p;')
    local('unknown array completion and decay',
          'int *p=(int[]){19,23}; return p[0]+p[1]==42 && sizeof(int[2])==8?42:1;')
    local('array whole address and extent',
          'int (*p)[3]=&(int[3]){19,23}; return (*p)[0]+(*p)[1]==42 && (*p)[2]==0 && p+1-p==1?42:1;')
    local('array literal postfix subscript', 'return (int[3]){1,19,23}[1]+2[(int[]){1,19,23}];')
    local('character array literal string initialization',
          'char *p=(char[]){"abc"}; p[1]=66; return p[0]==97 && p[1]==66 && p[2]==99 && p[3]==0?42:1;')
    cases.append(Case('file character array literal string bytes',
        'char *cell=(char[5]){"ab"};',
        'extern char *cell; int main(void) { cell[1]=66; return cell[0]==97 && cell[1]==66 && cell[2]==0 && cell[4]==0?42:1; }',
        {'cell':(Literal(5,1,((0,b'ab\0\0\0'),)),0)}))
    local('multidimensional array literal',
          'int (*p)[2]=(int[2][2]){{19,23},{3,4}}; return p[0][0]+p[0][1]==42 && p[1][1]==4?42:1;')
    local('record literal postfix and nested aggregate',
          'int x=7; struct S *p=&(struct S){.x=40,.a={2,3},.p=&x}; '
          'return p->x+p->a[0]==42 && p->a[1]==3 && *p->p==7?42:1;', S)
    local('literal member address survives full expression',
          'int *p=&(struct S){.x=40}.x; *p+=2; return *p;', S)
    local('literal member update initializer once',
          'int n=40; int old=((struct S){.x=n++}).x++; return n==41 && old==40?42:1;', S)
    local('union scalar active member',
          'union U *p=&(union U){.l=40}; p->l+=2; return p->l==42?42:1;',
          'union U { long l; int a[2]; }; ')
    local('union array active member',
          'union U *p=&(union U){.a={19,23}}; return p->a[0]+p->a[1];',
          'union U { long l; int a[2]; }; ')
    local('record copy initialization from literal',
          'struct S a=(struct S){.x=40,.a={2,7}}; struct S b; b=(struct S){.x=19,.a={23}}; '
          'return a.x+a.a[0]==42 && a.a[1]==7 && a.p==0 && b.x+b.a[0]==42?42:1;', S)
    local('copy assignment value member',
          'struct S a; return (a=(struct S){.x=42}).x;', S)
    local('distinct mutable literal occurrences',
          'int *a=&(int){19}; int *b=&(int){23}; *a=40; return a!=b && *a+2==42 && *b==23?42:1;')
    local('live scalar literal self reinitialization',
          'int *p=0; int i=0; again: p=&(int){p?*p+1:1}; ++i; '
          'if(i<3) goto again; return *p==3?42:1;')
    local('live array literal self reinitialization',
          'int *p=0; int i=0; again: p=(int[3]){p?p[0]+1:1,p?p[1]+2:2}; ++i; '
          'if(i<3) goto again; return p[0]==3 && p[1]==6 && p[2]==0?42:1;', gcc11_disagreement=True)
    local('live record literal self reinitialization',
          'struct S *p=0; int i=0; again: p=&(struct S){.x=p?p->x+1:1,.a={p?p->a[0]+2:2}}; ++i; '
          'if(i<3) goto again; return p->x==3 && p->a[0]==6 && p->a[1]==0 && p->p==0?42:1;', S, gcc11_disagreement=True)
    local('same occurrence goto reinitializes same object',
          'int n=0; int *p=0; int *q=0; again: q=&(int){n++}; '
          'if(n==1) { p=q; *p=99; goto again; } return p==q && *p==1 && n==2?42:1;')
    local('loop body lifetime current iteration only',
          'int i=0; int sum=0; for(i=0;i<3;++i) { int *p=&(int){i}; *p+=13; sum+=*p; } return sum;')
    local('loop condition same enclosing block object',
          'int n=0; int *p=0; int *q=0; while((q=&(int){n++}, n<3)) '
          '{ if(p && p!=q) return 1; p=q; *p=99; } return p==q && *p==2 && n==3?42:1;')
    local('nested literal initializer side effects sequenced explicitly',
          'int n=19; int *p=(int[]){n++,23}; int *q=&(int){n+22}; '
          'return n==20 && p[0]+p[1]==42 && *q==42?42:1;')
    local('nested literal addresses remain live',
          'struct S *p=&(struct S){.x=19,.a={23},.p=&(int){7}}; '
          '*p->p+=1; return p->x+p->a[0]==42 && *p->p==8?42:1;', S)
    local('array literal decay through call',
          'return sum((int[]){19,23});', 'int sum(int *p) { return p[0]+p[1]; } ')
    local('compound literal conditional comma composition',
          'int n=0; struct S a=(++n, n?(struct S){.x=40,.a={2}}:(struct S){.x=1}); '
          'return n==1 && a.x+a.a[0]==42?42:1;', S)
    local('sizeof literal no runtime effects',
          'int n=0; unsigned long size=sizeof((struct S){.x=++n}); '
          'return n==0 && size==24?42:1;', S, no_data=True)
    cases.append(Case('file unevaluated nested literal address no owners',
        'typedef char T[sizeof((int *){&(int){1}})]; int test(void) { return sizeof(T)==8?42:1; }', no_data=True))
    local('sizeof character literal emits no string storage',
          'return sizeof((char[]){"abc"})==4?42:1;', no_data=True)
    local('typeof character literal emits no string storage',
          'typeof((char[]){"abc"}) value={19,23}; return sizeof value==4 && value[0]+value[1]==42 && value[2]==0 && value[3]==0?42:1;',
          features=('typeof',), no_data=True, native_optional_pool=bytes((19,23,0,0)))
    local('sizeof inferred array literal no runtime effects',
          'int n=0; return sizeof((int[]){++n,++n})==8 && n==0?42:1;', no_data=True)
    local('typeof literal no runtime effects',
          'int n=0; typeof((int){++n}) x=42; return n==0 && x==42?42:1;',
          features=('typeof',), no_data=True)
    cases.append(Case('file typeof literal creates no storage',
        'typeof((int){42}) test(void) { return 42; }', features=('typeof',), no_data=True))
    cases.append(Case('reviewer exact scalar live reinit original',
        'int main(void) {\n int *p=0; int i=0;\nagain:\n p=&(int){p ? *p+1 : 1};\n i++;\n if(i<3) goto again;\n return *p==3 ? 0 : 1;\n}\n',
        'int companion(void) { return 0; }', expected_exit=0))
    cases.append(Case('recursive activations live nonalias',
        'int recurse(int n,int *outer) { int *p=&(int){n}; '
        'if(outer && p==outer) return 1; if(n && recurse(n-1,p)!=42) return 2; '
        'return *p==n?42:3; } int test(void) { return recurse(5,0); }'))
    cases.append(Case('file scalar private duration identity',
        'int *cell=&(int){40}; int *slot(void) { return cell; }',
        'extern int *cell; int *slot(void); int main(void) { int *p=slot(); '
        '*p+=2; return p==cell && slot()==p && *slot()==42?42:1; }',
        {'cell':(Literal(4,4,((0,ints(40)),)),0)}))
    cases.append(Case('file distinct mutable objects',
        'int *a=&(int){19}; int *b=&(int){23};',
        'extern int *a,*b; int main(void) { *a=40; return a!=b && *a==40 && *b==23?42:1; }',
        {'a':(Literal(4,4,((0,ints(19)),)),0), 'b':(Literal(4,4,((0,ints(23)),)),0)}))
    cases.append(Case('file array interior and onepast address',
        'int *cell=(int[3]){19,23,7}+1; int *end=(int[2]){19,23}+2;',
        'extern int *cell,*end; int main(void) { return cell[-1]+cell[0]==42 && cell[1]==7 && end[-2]+end[-1]==42?42:1; }',
        {'cell':(Literal(12,4,((0,ints(19,23,7)),)),4),
         'end':(Literal(8,4,((0,ints(19,23)),)),8)}))
    cases.append(Case('file record member static address',
        S+'int *cell=&(struct S){.x=40,.a={2,7}}.a[1];',
        'extern int *cell; int main(void) { return *cell==7 && cell[-1]==2?42:1; }',
        {'cell':(Literal(24,8,((0,ints(40,2,7)),(16,bytes(8)))),8)}))
    child=Literal(4,4,((0,ints(42)),))
    cases.append(Case('file nested compound literal dependency graph',
        'struct N { int *p; int x; }; struct N *cell=&(struct N){.p=&(int){42},.x=7};',
        'struct N { int *p; int x; }; extern struct N *cell; '
        'int main(void) { return *cell->p==42 && cell->x==7?42:1; }',
        {'cell':(Literal(16,8,((8,ints(7)),),((0,child,0),)),0)}))
    cases.append(Case('file nested conditional literal dependency',
        'int **cell=&(int *){1?&(int){42}:&(int){7}};',
        'extern int **cell; int main(void) { return **cell; }',
        {'cell':(Literal(8,8,(),((0,Literal(4,4,((0,ints(42)),)),0),)),0)}))
    cases.append(Case('file nested array literal dependency',
        'int **cell=(int *[]){(int[]){19,23}};',
        'extern int **cell; int main(void) { return cell[0][0]+cell[0][1]; }',
        {'cell':(Literal(8,8,(),((0,Literal(8,4,((0,ints(19,23)),)),0),)),0)}))
    cases.append(Case('forward static initialization address dependency',
        'extern int later; int **cell=&(int *){&later}; int later=42;',
        'extern int later; extern int **cell; int main(void) { return *cell==&later && **cell==42?42:1; }'))
    local('block static literal persists activation',
          'int *p=slot(); *p+=2; return slot()==p && *p==42?42:1;',
          'int *slot(void) { return &(static int){40}; } ', storage=True)
    local('block register literal scalar value', 'return (register int){42};', storage=True)
    local('block static thread literal persists',
          'int *p=slot(); *p+=2; return slot()==p && *p==42?42:1;',
          'int *slot(void) { return &(static thread_local int){40}; } ', storage=True, tls_literal=True)
    cases.append(Case('file static literal explicit storage',
        'int *cell=&(static int){42};',
        'extern int *cell; int main(void) { return *cell; }', storage=True))
    cases.append(Case('file thread literal explicit storage',
        'unsigned long size=sizeof((thread_local int){40}); int test(void) { return size==4?42:1; }', storage=True))
    cases.append(Case('block static thread literal per-thread isolation',
        'int *slot(void) { return &(static thread_local int){40}; }',
        '#include <pthread.h>\nint *slot(void); '
        'static void *worker(void *unused) { (void)unused; int *p=slot(); '
        'if(*p!=40) return (void *)1; *p=23; return slot()==p && *p==23?0:(void *)2; } '
        'int main(void) { pthread_t t; void *r; int *p=slot(); if(*p!=40) return 1; *p=42; '
        'if(pthread_create(&t,0,worker,0) || pthread_join(t,&r) || r) return 2; '
        'return slot()==p && *p==42?42:3; }', storage=True, pthread=True, tls_literal=True))
    return cases


def selected_compilers():
    compilers=native_compilers(HOST,os.environ.get('CLANG_CC') or shutil.which('clang'))
    extra=os.environ.get('GCC13_CC')
    if extra:
        # Validate even when extra aliases primary: dedupe must not hide poison.
        path=shutil.which(extra)
        assert path, ('explicit GCC13 unavailable',extra)
        version=invoke([extra,'-dumpfullversion','-dumpversion'])
        assert version.returncode==0 and not version.stderr and re.fullmatch(r'13(?:\.\d+){0,2}\n',version.stdout), ('GCC13 version required',extra,version)
        identity=invoke([extra,'--version'])
        assert identity.returncode==0 and not identity.stderr and 'clang' not in identity.stdout.lower() and re.search(r'\b(?:gcc|GCC)\b',identity.stdout), ('not GCC13',identity)
        if all(os.path.realpath(shutil.which(cc))!=os.path.realpath(path) for cc in compilers):
            compilers.append(extra)
    return compilers


def run_case(linker,objects,executable,case):
    if case.expected_exit==42:
        run_program(linker,objects,executable)
    else:
        producer([linker,*objects,'-o',executable],executable)
        result=invoke([executable])
        assert result.returncode==case.expected_exit and not result.stdout and not result.stderr, (case.name,result)


def native_version(cc):
    if clang_style(cc): return 'clang'
    r=invoke([cc,'-dumpfullversion','-dumpversion'])
    assert r.returncode==0 and not r.stderr and re.fullmatch(r'\d+(?:\.\d+){0,2}\n',r.stdout), ('native version probe',cc,r)
    return r.stdout.strip()


def run_native_case(cc,objects,executable,case,version):
    if case.gcc11_disagreement and version.split('.')[0]=='11':
        # N3096 6.5.2.5p5 and 6.7.10p20/22: old explicitly initialized
        # subobjects remain live; default fill does not clobber them before RHS
        # capture. GCC11 clears too early. Execute the exact original, require
        # this known outcome, report disagreement and NEVER count agreement.
        producer([cc,*objects,'-o',executable],executable)
        r=invoke([executable])
        assert r.returncode==1 and not r.stdout and not r.stderr, ('GCC11 self-reinit discrepancy changed; review required',case.name,r)
        return False
    run_case(cc,objects,executable,case)
    return True


def compile_native(cc, source, output, expected=()):
    producer([cc,*diagnostic_flags(cc),'-std=c2x','-pedantic-errors','-fno-common','-O0','-c',source,'-o',output],output,expected)


def relocation_at(elf, section, offset):
    matches=[r for r in elf.relocations if r['section']==section and r['offset']==offset]
    assert len(matches)==1 and matches[0]['kind']==1, ('exact R_X86_64_64',section,offset,matches)
    return matches[0]


def literal_evidence(elf, relocation, wanted, addend=0, qbe=False, il_blocks=None, seen=None):
    seen=set() if seen is None else seen
    base=relocation['symbol']; section=base['section']
    assert 0<section<len(elf.sections), ('undefined literal storage',base)
    offset=base['value']+relocation['addend']-addend
    candidates=[s for s in elf.symbols if s['section']==section and s['value']==offset and
                s['binding']==0 and s['kind']==(0 if qbe else 1) and s['name']]
    assert len(candidates)==1, ('private compound owner',offset,candidates)
    owner=candidates[0]; sec=elf.sections[section]
    # Only the owner's own symbol or an assembler section-symbol
    # representation may denote it. A different named/public base plus a
    # compensating addend is not the same symbolic C address.
    assert base['name']==owner['name'] or base['kind']==3, ('wrong symbolic literal base',base,owner)
    if base['kind']!=3: assert relocation['addend']==addend
    assert sec[1] in (1,8) and sec[2]&3==3 and not sec[2]&0x404
    assert sec[8]>=wanted.alignment and offset%wanted.alignment==0
    assert owner['size']==(0 if qbe else wanted.width), ('literal width',owner,wanted)
    assert 0<=offset and offset+wanted.width<=sec[5]
    if qbe:
        assert owner['name'] in il_blocks, ('missing IL owner',owner)
        public,alignment,width=il_blocks[owner['name']]
        assert not public and alignment==wanted.alignment and width==wanted.width, ('IL literal extent',owner,il_blocks)
    identity=(section,offset)
    if identity in seen: return identity
    seen.add(identity)
    contents=bytes(sec[5]) if sec[1]==8 else elf.section_bytes(section)
    for at,values in wanted.values:
        assert contents[offset+at:offset+at+len(values)]==values, ('literal value bytes',owner,at,contents,wanted)
    actual_links=[r for r in elf.relocations if r['section']==section and offset<=r['offset']<offset+wanted.width]
    assert {r['offset']-offset for r in actual_links}=={at for at,_,_ in wanted.links}, ('unexpected/missing literal relocations',actual_links,wanted)
    for at,child,child_addend in wanted.links:
        literal_evidence(elf,relocation_at(elf,section,offset+at),child,child_addend,qbe,il_blocks,seen)
    return identity


def il_extents(text):
    """Prove exact QBE data extent; accept only parsed typed atoms/zero runs."""
    result={}
    pattern=r'^(export )?(thread )?data \$([^\s=]+) = align (\d+) \{([^}]*)\}'
    for public,thread,name,alignment,body in re.findall(pattern,text,re.M):
        assert name not in result, ('duplicate IL data',name)
        total=0
        fragments=body.strip().split(',')
        if not fragments[-1].strip(): fragments.pop()  # QBE permits one trailing comma.
        assert fragments, ('empty IL data block',name)
        for fragment in fragments:
            atom=fragment.strip(); match=re.fullmatch(r'([bhwlsdz])\s+(.+)',atom)
            assert match, ('unparsed IL data atom',atom)
            kind,value=match.groups()
            total+=int(value) if kind=='z' else {'b':1,'h':2,'w':4,'l':8,'s':4,'d':8}[kind]
        result[name]=(bool(public),int(alignment),total)
    assert len(re.findall(r'\bdata \$',text))==len(result), ('unparsed IL data block',text)
    return result


def check_object(path, case, qbe=False, text=''):
    elf=OffsetRelocations(path); blocks=il_extents(text) if qbe else None
    identities=[]
    if case.roots:
        exported={s['name'] for s in elf.symbols if s['binding']==1 and s['section'] and
                  elf.sections[s['section']][2]&3==3 and not elf.sections[s['section']][2]&4}
        assert exported==set(case.roots), ('unexpected exported literal data',case.name,exported)
    for slot,(wanted,addend) in case.roots.items():
        sym=elf.symbol(slot)
        assert sym['binding']==1 and sym['size']==(0 if qbe else 8) and sym['kind']==(0 if qbe else 1)
        identities.append(literal_evidence(elf,elf.slot_relocation(slot),wanted,addend,qbe,blocks))
    assert len(set(identities))==len(identities), ('mutable occurrences merged',case.name,identities)
    if case.tls_literal:
        tls=[s for s in elf.symbols if s['kind']==6 and s['section']]
        assert len(tls)==1, ('one private TLS literal',tls)
        symbol=tls[0]; sec=elf.sections[symbol['section']]
        assert symbol['binding']==0 and symbol['size']==(0 if qbe else 4)
        assert sec[2]&0x403==0x403 and sec[8]>=4 and symbol['value']%4==0
        assert elf.section_bytes(symbol['section'])[symbol['value']:symbol['value']+4]==ints(40)
        if qbe: assert blocks[symbol['name']]==(False,4,4)
    if case.no_data:
        data=[s for s in elf.symbols if s['kind']==1 and s['section'] and elf.sections[s['section']][2]&2]
        if not qbe and case.native_optional_pool is not None:
            # A native compiler may constant-pool this evaluated local array's
            # {19,23} initializer. It must NOT contain the unevaluated "abc".
            assert len(data)<=1, ('unexpected native local-value pools',case.name,data)
            for pool in data:
                assert pool['binding']==0 and pool['size']==len(case.native_optional_pool)
                sec=elf.sections[pool['section']]
                assert sec[1]==1 and sec[2]&7==2
                assert elf.section_bytes(pool['section'])[pool['value']:pool['value']+pool['size']]==case.native_optional_pool
        else: assert not data, ('unevaluated literal storage',case.name,data)
        if qbe: assert not blocks, ('unevaluated IL storage',case.name,blocks)
    return elf


# Meaningful native C constraints, never executed; no extension acceptance used.
CONSTRAINTS = [
    ('const literal assignment', 'int f(void) { return ((const int){1}=2); }'),
    ('excess scalar literal', 'int f(void) { return (int){1,2}; }'),
    ('excess array literal', 'int f(void) { return (int[1]){1,2}[0]; }'),
    ('incomplete record literal', 'struct S; void f(void) { (void)&(struct S){1}; }'),
    ('function literal', 'void f(void) { (void)&(int(void)){0}; }'),
    ('VLA literal', 'void f(int n) { (void)&(int[n]){1}; }'),
    ('unknown member literal', 'struct S { int x; }; int f(void) { return (struct S){.y=1}.x; }'),
    ('negative literal designator', 'int f(void) { return (int[]){[-1]=1}[0]; }'),
    ('nonconstant file literal content', 'int f(void); int *p=&(int){f()};'),
    ('automatic address in static initializer', 'void f(void) { static int *p=&(int){42}; (void)p; }'),
]
# Populated from these exact originals, with all headers/notes retained.
NATIVE_CONSTRAINTS = {'const literal assignment': ((('error', "assignment of read-only location '1'"),),
                              (('error', 'read-only variable is not assignable'),)),
 'excess scalar literal': ((('error', 'excess elements in scalar initializer'),
                            ('note', "(near initialization for '(anonymous)')")),
                           (('error',
                             'excess elements in scalar initializer [-Werror,-Wexcess-initializers]'),)),
 'excess array literal': ((('error', 'excess elements in array initializer'),
                           ('note', "(near initialization for '(anonymous)')")),
                          (('error',
                            'excess elements in array initializer [-Werror,-Wexcess-initializers]'),)),
 'incomplete record literal': ((('error', 'excess elements in struct initializer'),
                                ('note', "(near initialization for '(anonymous)')"),
                                ('error', "invalid use of undefined type 'struct S'")),
                               (('error', "variable has incomplete type 'struct S'"),
                                ('note', "forward declaration of 'struct S'"))),
 'function literal': ((('error', 'invalid initializer'), ('note', "(near initialization for '(anonymous)')")),
                      (('error', "illegal initializer type 'int (void)'"),)),
 'VLA literal': ((('error', 'compound literal has variable size'),),
                 (('error', 'variable-sized object may not be initialized'),)),
 'unknown member literal': ((('error', "'struct S' has no member named 'y'"),),
                            (('error',
                              "field designator 'y' does not refer to any field in type 'struct S'"),)),
 'negative literal designator': ((('error', 'array index in initializer exceeds array bounds'),
                                  ('note', "(near initialization for '(anonymous)')")),
                                 (('error', "array designator value '-1' is negative"),)),
 'nonconstant file literal content': ((('error', 'initializer element is not constant'),
                                       ('note', "(near initialization for 'p')"),
                                       ('error',
                                        'initializer element is not a constant expression [-Wpedantic]')),
                                      (('error', 'initializer element is not a compile-time constant'),)),
 'automatic address in static initializer': ((('error', 'initializer element is not constant'),),
                                             (('error',
                                               'initializer element is not a compile-time constant'),))}


def native_constraint(cc, source, output, name):
    output.unlink(missing_ok=True)
    flags=diagnostic_flags(cc)+([] if clang_style(cc) else ['-fno-diagnostics-show-caret'])
    result=invoke([cc,*flags,'-std=c2x','-pedantic-errors','-fno-common','-c',source,'-o',output])
    validate_native_constraint(cc,source,output,name,result)


def validate_native_constraint(cc,source,output,name,result):
    actual=native_diagnostics(result.stderr,source,source.read_text(),clang_style(cc))
    expected=NATIVE_CONSTRAINTS[name][int(clang_style(cc))]
    assert result.returncode==1 and not result.stdout and not output.exists(), (name,cc,result)
    assert actual==expected, (name,cc,actual,expected,result.stderr)


# These native-valid types/features are later milestones, NOT native constraints.
LATER = [
    ('M20 floating literal', 'double f(void) { return (double){1.5}; }'),
    ('M22 bitfield literal', 'struct S { unsigned x:3; }; int f(void) { return (struct S){.x=2}.x; }'),
    ('M21 aggregate by value', 'struct S { int x; }; int f(struct S); int g(void) { return f((struct S){42}); }'),
]
# C23 storage errors require the grammar; legacy hosts' parser failures are
# capability gaps, not native C23 constraint agreements. Checked by KCC only.
STORAGE_CONSTRAINTS = [
    ('file register literal', 'unsigned long n=sizeof((register int){1});'),
    ('block bare thread literal', 'int f(void) { return (thread_local int){1}; }'),
    ('register literal address', 'int f(void) { int *p=&(register int){1}; return *p; }'),
    ('static register literal combination', 'int f(void) { return (static register int){1}; }'),
]
# N3096 6.3.2.1: register array decay is undefined behavior, NOT a C
# constraint. KCC's conservative proof refusal is compile-only; no execution or
# native constraint agreement is claimed.
UB_PROOF_REFUSALS = [
    ('register array literal decay', 'int f(void) { int *p=(register int[1]){1}; return *p; }'),
]
STATIC_REFUSALS = [
    ('ordinary static record literal copy', 'struct S { int x; }; static struct S s=(struct S){42};'),
    ('ordinary object load literal content', 'int value=42; int *p=&(int){value};'),
    ('file unevaluated static literal content', 'int f(void); unsigned long n=sizeof((int){f()});'),
    ('constexpr literal M23h dependency', 'int f(void) { return (constexpr int){42}; }'),
]
# Exact KCC diagnostics are frozen only after production integration.
KCC_REFUSALS = {'const literal assignment': (1, 23, 'assignment requires a modifiable lvalue'),
 'excess scalar literal': (1, 30, 'excess elements in initializer'),
 'excess array literal': (1, 33, 'excess elements in initializer'),
 'incomplete record literal': (1, 43, 'initializer requires a complete object or unknown outer array bound'),
 'function literal': (1, 34, 'initializer requires a complete object or unknown outer array bound'),
 'VLA literal': (1,
                 29,
                 'array bound must be an integer constant expression; variable-length arrays are not '
                 'supported yet'),
 'unknown member literal': (1, 54, 'initializer designates an unknown member'),
 'negative literal designator': (1, 30, 'array initializer index exceeds bound or storage limit (1 MiB)'),
 'nonconstant file literal content': (1, 28, 'static initializer must be a constant expression'),
 'automatic address in static initializer': (1,
                                             31,
                                             'file-scope pointer initializer requires a supported null or '
                                             'direct address constant expression'),
 'file register literal': (1, 24, 'invalid storage class combination or scope for compound literal'),
 'block bare thread literal': (1, 22, 'invalid storage class combination or scope for compound literal'),
 'register literal address': (1, 22, 'cannot take the address of a register object'),
 'register array literal decay': (1, 22, 'register array-to-pointer conversion is not supported'),
 'static register literal combination': (1, 30, 'duplicate or conflicting compound literal storage class'),
 'ordinary static record literal copy': (1,
                                         40,
                                         'non-integer file-scope object initializers are not supported yet'),
 'ordinary object load literal content': (1, 29, 'static initializer must be a constant expression'),
 'file unevaluated static literal content': (1, 43, 'static initializer must be a constant expression'),
 'constexpr literal M23h dependency': (1, 23, 'constexpr compound literals require M23h constant-object support'),
 'M20 floating literal': (1, 1, 'expected integer type specifier'),
 'M22 bitfield literal': (1, 22, 'bit-fields are not supported yet (M22)'),
 'M21 aggregate by value': (1, 60, 'aggregate function arguments are not supported yet (M21)')}


def validate_kcc_refusal(source,name,result):
    line,column,message=KCC_REFUSALS[name]
    expected=f'{source}:{line}:{column}: error: {message}\n'
    assert result.returncode==1 and not result.stdout and result.stderr==expected, (name,result,expected)


def literal_capability(cc,source,output,feature):
    # Probe exact standard-valid source. Legacy parser rejection is not a C23
    # constraint or semantic agreement, and never suppresses KCC coverage.
    original={'storage':'int f(void) { return (static int){42}; }\n',
              'empty':'int f(void) { return (int){}; }\n'}[feature]
    source.write_text(original); output.unlink(missing_ok=True)
    flags=diagnostic_flags(cc)+([] if clang_style(cc) else ['-fno-diagnostics-show-caret'])
    r=invoke([cc,*flags,'-std=c2x','-pedantic-errors','-c',source,'-o',output])
    if r.returncode==0:
        assert not r.stdout and not r.stderr and output.is_file() and output.stat().st_size>0
        return True
    actual=native_diagnostics(r.stderr,source,original,clang_style(cc))
    expected={
        'storage':((('error', "expected expression before 'static'"), ('error', "expected ';' before '{' token")),
                   (('error','expected expression'),)),
        'empty':((('error','ISO C forbids empty initializer braces [-Wpedantic]'), ('error','empty scalar initializer'), ('note',"(near initialization for '(anonymous)')")), None),
    }[feature]
    assert r.returncode==1 and not r.stdout and not output.exists() and actual==expected[int(clang_style(cc))], (cc,r,actual)
    return False


def must_fail(operation,label):
    try: operation()
    except AssertionError: return
    raise AssertionError('M17 compound negative control escaped: '+label)


def controls(d):
    source,output=d/'control.c',d/'control.o'
    case=next(c for c in fixtures() if c.name=='file scalar private duration identity')
    source.write_text(case.owner+'\n'); compile_native(HOST,source,output)
    elf=check_object(output,case)
    relocation=elf.slot_relocation('cell')
    for mutation in ('byte','addend','kind','duplicate','binding','extent','alignment','missing','named-base'):
        damaged=copy.deepcopy(elf); r=damaged.slot_relocation('cell'); b=r['symbol']
        offset=b['value']+r['addend']
        target=next(s for s in damaged.symbols if s['section']==b['section'] and s['value']==offset and s['kind']==1)
        if mutation=='byte':
            at=damaged.sections[b['section']][4]+offset
            damaged.data=damaged.data[:at]+b'X'+damaged.data[at+1:]
        elif mutation=='addend': r['addend']+=1
        elif mutation=='kind': r['kind']=2
        elif mutation=='duplicate': damaged.relocations.append(copy.deepcopy(r))
        elif mutation=='binding': target['binding']=1
        elif mutation=='extent': target['size']=3
        elif mutation=='alignment':
            sec=list(damaged.sections[b['section']]); sec[8]=1; damaged.sections[b['section']]=tuple(sec)
        elif mutation=='named-base':
            wrong=damaged.symbol('cell'); r['symbol']=wrong
            r['addend']=offset-wrong['value']
            # Put the public pointer slot in the same section solely in the
            # oracle: preserve numeric destination, change symbolic identity.
            wrong['section']=target['section']
        else: damaged.symbols.remove(target)
        must_fail(lambda: literal_evidence(damaged,damaged.slot_relocation('cell'),case.roots['cell'][0]),mutation)
    text='data $literal = align 4 { w 40 }\nexport data $cell = align 8 { l $literal }\n'
    assert il_extents(text)=={'literal':(False,4,4),'cell':(True,8,8)}
    for bad in (text+text,text.replace('w 40','garbage'),text.replace('align 4','align bad')):
        must_fail(lambda:il_extents(bad),'unparsed IL')
    # Explicit GCC13 must be validated BEFORE canonical-executable dedupe.
    gcc13=d/'gcc13'; old=d/'old-gcc'; fakeclang=d/'clang13'; alias=d/'gcc-alias'
    for executable,version,banner in ((gcc13,'13.2.0','gcc (GCC) 13.2.0'),
                                      (old,'12.3.0','gcc (GCC) 12.3.0'),
                                      (fakeclang,'13.0.0','clang version 13.0.0')):
        executable.write_text('#!/bin/sh\ncase "$1" in\n-dumpfullversion) echo "'+version+'";;\n--version) echo "'+banner+'";;\n*) exit 9;;\nesac\n')
        executable.chmod(0o755)
    alias.symlink_to(gcc13)
    with patch.dict(globals(),{'HOST':str(gcc13)}), patch.dict(os.environ,{'CLANG_CC':str(alias),'GCC13_CC':str(alias)}):
        assert selected_compilers()==[str(gcc13)]
    for bad in (old,fakeclang,d/'missing-gcc13'):
        with patch.dict(globals(),{'HOST':str(bad) if bad.exists() else str(gcc13)}), patch.dict(os.environ,{'CLANG_CC':str(bad) if bad.exists() else str(gcc13),'GCC13_CC':str(bad)}):
            must_fail(selected_compilers,'explicit GCC13 validation before dedupe')
    # Complete diagnostic streams, not arbitrary error substrings.
    name,text=CONSTRAINTS[0]; source.write_text(text+'\n')
    expected=NATIVE_CONSTRAINTS[name][0]
    stderr=''.join(f'{source}:1:1: {kind}: {message}\n' for kind,message in expected)
    clean=subprocess.CompletedProcess([],1,'',stderr); output.unlink(missing_ok=True)
    validate_native_constraint(str(old),source,output,name,clean)
    for mutation in ('message','note','junk','stdout','status','missing-newline','poison'):
        bad=copy.copy(clean)
        if mutation=='message': bad.stderr=bad.stderr.replace(expected[0][1],'wrong reason')
        elif mutation=='note': bad.stderr+=f'{source}:1:1: note: unexpected note\n'
        elif mutation=='junk': bad.stderr+='unparsed compiler text\n'
        elif mutation=='stdout': bad.stdout='partial output\n'
        elif mutation=='status': bad.returncode=0
        elif mutation=='missing-newline': bad.stderr=bad.stderr.rstrip('\n')
        else: output.write_bytes(b'poison object')
        must_fail(lambda:validate_native_constraint(str(old),source,output,name,bad),'native fullstream '+mutation)
        output.unlink(missing_ok=True)
    line,column,message=KCC_REFUSALS[name]
    clean=subprocess.CompletedProcess([],1,'',f'{source}:{line}:{column}: error: {message}\n')
    validate_kcc_refusal(source,name,clean)
    for mutation in ('message','column','note','junk','stdout','status','missing-newline'):
        bad=copy.copy(clean)
        if mutation=='message': bad.stderr=bad.stderr.replace(message,'wrong reason')
        elif mutation=='column': bad.stderr=bad.stderr.replace(f':{column}:',f':{column+1}:')
        elif mutation=='note': bad.stderr+=f'{source}:1:1: note: unexpected note\n'
        elif mutation=='junk': bad.stderr+='unparsed tool noise\n'
        elif mutation=='stdout': bad.stdout='partial emitted IL\n'
        elif mutation=='status': bad.returncode=0
        else: bad.stderr=bad.stderr.rstrip('\n')
        must_fail(lambda:validate_kcc_refusal(source,name,bad),'KCC fullstream '+mutation)
    print('M17 compound controls: hardened producer, GCC13-before-dedupe, fullstream diagnostics, ELF graph and IL')


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
        assert head.returncode==0 and head.stdout.strip()==args.frozen_hash, ('compiler freeze mismatch',head,args.frozen_hash)
        assert Path(KCC).resolve().is_relative_to(checkout/'build'), 'compiler must be inside frozen checkout build'
        dirty=invoke(['git','-C',checkout,'status','--porcelain','--','src'])
        assert dirty.returncode==0 and not dirty.stdout, ('dirty production sources',dirty)
        assert QBE, 'QBE required, never skip ELF/runtime silently'
    with tempfile.TemporaryDirectory(prefix='kcc compound literal ') as tmp:
        d=Path(tmp); harness_self_test(d); compiler_selection_self_test(d); controls(d)
        if args.harness_self_test: return
        compilers=selected_compilers(); counts={cc:0 for cc in compilers}; gaps={cc:[] for cc in compilers}
        disagreements={cc:[] for cc in compilers}; versions={cc:native_version(cc) for cc in compilers}
        source,host,native,other,il,assembly,obj,exe=[d/n for n in ('owner.c','host.c','native.o','host.o','literal.ssa','literal.s','literal.o','program')]
        storage={cc:literal_capability(cc,source,native,'storage') for cc in compilers}
        features={cc:features_for(cc,source,native) for cc in compilers}
        for cc in compilers:
            if literal_capability(cc,source,native,'empty'): features[cc].add('empty')
        cases=fixtures(); assert len({c.name for c in cases})==len(cases)
        kcc_count=0
        for case in cases:
            source.write_text(case.owner if case.owner.endswith('\n') else case.owner+'\n'); host.write_text(case.companion+'\n')
            for cc in compilers:
                if (case.storage and not storage[cc]) or any(f not in features[cc] for f in case.features):
                    gaps[cc].append(case.name); continue
                warnings=((('warning','expression with side effects has no effect in an unevaluated context [-Wunevaluated-expression]'),) if clang_style(cc) and case.name in ('sizeof literal no runtime effects','sizeof inferred array literal no runtime effects') else ())
                compile_native(cc,source,native,warnings); check_object(native,case)
                compile_native(cc,host,other)
                if run_native_case(cc,[native,other]+(['-pthread'] if case.pthread else []),exe,case,versions[cc]): counts[cc]+=1
                else: disagreements[cc].append(case.name)
            if args.native_only: continue
            r=invoke([KCC,source]); assert r.returncode==0 and not r.stderr and r.stdout, (case.name,r)
            il.write_text(r.stdout); il_extents(r.stdout)
            producer([QBE,'-t','amd64_sysv','-o',assembly,il],assembly)
            producer([HOST,'-Wa,-L','-c',assembly,'-o',obj],obj); check_object(obj,case,True,r.stdout)
            compile_native(HOST,host,other); run_case(HOST,[obj,other]+(['-pthread'] if case.pthread else []),exe,case); kcc_count+=1
        for name,text in CONSTRAINTS:
            source.write_text(text+'\n')
            for cc in compilers: native_constraint(cc,source,native,name)
            if not args.native_only: validate_kcc_refusal(source,name,invoke([KCC,source]))
        if not args.native_only:
            for name,text in STORAGE_CONSTRAINTS+STATIC_REFUSALS+UB_PROOF_REFUSALS+LATER:
                source.write_text(text+'\n'); validate_kcc_refusal(source,name,invoke([KCC,source]))
        print(f'M17 compound: {len(cases)} unchanged originals; KCC/QBE/ELF/runtime {kcc_count}; {len(CONSTRAINTS)} exact native constraints per compiler')
        for cc in compilers:
            print(f'{cc}: {counts[cc]} unchanged runtime agreements; {len(gaps[cc])} explicit capability gaps: {gaps[cc]}; '
                  f'{len(disagreements[cc])} explicit GCC11 semantic disagreements (expected42/observed1, NOT agreements): {disagreements[cc]}')
        if args.native_only: print('NATIVE-ONLY: no frozen KCC coverage/PASS claimed')
        else: print('Frozen production hash: '+args.frozen_hash)


if __name__=='__main__': main()

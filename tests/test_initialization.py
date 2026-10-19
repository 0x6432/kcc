"""M17 independent initializer oracle (compound literals deliberately separate).

Unchanged originals, strict native compilation, defined runtime only. Explicit
KCC_SOURCE + --frozen-hash are required for production claims. GCC13_CC and
CLANG_CC are optional selections; invalid explicit selections fail closed.
No /data tool defaults, source rewrites, warning waivers or padding mandates.
"""
import argparse
import ast
import hashlib
from collections import Counter
import copy
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from test_integer_initializers import (
    HOST, KCC, QBE, invoke, producer, clang_style, native_diagnostics,
    harness_self_test, run_program, features_for,
)
from test_null_initializers import native_compilers, compiler_selection_self_test
from test_direct_address_initializers import ElfRelocations, controls as address_controls
from test_address_offsets import OffsetReference, diagnostic_flags, controls as offset_controls


@dataclass
class Object:
    name: str | None
    size: int
    align: int
    fields: tuple  # (offset, exact bytes); unspecified padding intentionally absent
    public: bool = True
    tls: bool = False
    refs: dict = field(default_factory=dict)  # byte offset -> logical reference
    typed: dict = field(default_factory=dict)  # exact widths for nonzero scalar leaves


@dataclass
class Case:
    name: str
    owner: str
    objects: tuple = ()
    features: tuple = ()
    warnings: tuple = ((), ())
    compact: bool = False
    gcc_discrepancy: bool = False
    bounded_work: bool = False
    standalone: bool = False
    success_exit: int = 42
    companion: str = 'int test(void); int main(void) { return test(); }\n'


def integer(n, width=4):
    return (n % (1 << (width*8))).to_bytes(width, 'little')


def vector(values, width=4):
    return b''.join(integer(n, width) for n in values)


def shared_union_initializer(depth):
    """Compact shared TYPE DAG, not exponentially expanded source/storage."""
    assert 0<=depth<=40
    text='union U0{int a,b;};\n'
    text+=''.join(f'union U{level}{{union U{level-1} a,b;}};\n' for level in range(1,depth+1))
    text+=f'union O{{union U{depth} d;int z;}}o={{.d={{0}}}};'
    assert len(text)<2048
    return text


def compile_only_fixtures():
    # Standard-valid pre-C23 acceptance, NOT an expected resource refusal.
    # Deep case compiles through QBE/ELF under the same hard work deadline;
    # only the separate depth4 equivalent is ever executed.
    return (Case('bounded initialized shared union DAG depth40',shared_union_initializer(40),
                 (Object('o',4,4,((0,bytes(4)),)),),compact=True,bounded_work=True),)


def fixtures():
    cases=[]
    def add(name, declarations, expression, objects=(), features=(), warnings=((),()), compact=False):
        cases.append(Case(name,declarations+' int test(void) { return ('+expression+')?42:1; }',
                          tuple(objects),features,warnings,compact))
    def array(name,decl,values,checks='',typ='int',width=4,features=(),warnings=((),())):
        expr=' && '.join(f'cell[{i}]=={v}' for i,v in enumerate(values))
        if checks: expr+=' && '+checks
        add(name,decl,expr,[Object('cell',len(values)*width,width,((0,vector(values,width)),))],features,warnings)
    array('nested braces scalar','int cell[3]={{19},{23},{0}};', [19,23,0], warnings=(tuple(item for i in range(3) for item in (('warning','braces around scalar initializer'),('note',f"(near initialization for 'cell[{i}]')"))), (('warning','braces around scalar initializer [-Wbraced-scalar-init]'),)*3))
    array('partial zero tail','int cell[5]={19,23};',[19,23,0,0,0])
    array('designator continuation','int cell[6]={[2]=19,23,[0]=7};',[7,0,19,23,0,0])
    array('inferred sparse continuation','int cell[]={[4]=19,23,[1]=7};',[0,7,0,0,19,23], 'sizeof cell==24')
    array('inferred nonmonotonic','int cell[]={[5]=23,[1]=19};',[0,19,0,0,0,23], 'sizeof cell==24')
    override=((),(('warning','initializer overrides prior initialization of this subobject [-Winitializer-overrides]'),('note','previous initialization is here')))
    array('duplicate array designation','int cell[3]={[1]=5,[1]=42};',[0,42,0],warnings=override)
    for suffix,init,values in (
        ('explicit','{{1,2,3},{4,5,6}}',[1,2,3,4,5,6]),
        ('elided','{1,2,3,4,5,6}',[1,2,3,4,5,6]),
        ('chained continuation','{[0][1]=19,23,7}',[0,19,23,7,0,0]),
        ('subaggregate reset','{[1]={19,23}}',[0,0,0,19,23,0]),
        ('inferred','{{19},{23,7}}',[19,0,0,23,7,0])):
        bound='' if suffix=='inferred' else '2'
        checks=' && '.join(f'cell[{i//3}][{i%3}]=={v}' for i,v in enumerate(values))
        add('matrix '+suffix,f'int cell[{bound}][3]={init};',checks+' && sizeof cell==24',
            [Object('cell',24,4,((0,vector(values)),))])
    nested='struct I { short x; int y; }; struct R { char c; struct I in; int a[3]; }; '
    for name,init,vals in (
        ('nested explicit','{1,{19,23},{7,8}}',(1,19,23,7,8,0)),
        ('nested elision','{1,19,23,7,8}',(1,19,23,7,8,0)),
        ('member continuation','{.in.x=19,23,7,8}',(0,19,23,7,8,0)),
        ('nested array continuation','{.a[1]=19,23,.c=7}',(7,0,0,0,19,23))):
        c,x,y,a,b,d=vals
        add(name,nested+'struct R cell='+init+';',
            f'cell.c=={c} && cell.in.x=={x} && cell.in.y=={y} && cell.a[0]=={a} && cell.a[1]=={b} && cell.a[2]=={d} && sizeof cell==24',
            [Object('cell',24,4,((0,integer(c,1)),(4,integer(x,2)),(8,integer(y)),(12,vector([a,b,d]))))])
    add('nested aggregate override',nested+'struct R cell={.in={1,2},.in={19,23}};',
        'cell.c==0 && cell.in.x==19 && cell.in.y==23 && cell.a[2]==0',
        [Object('cell',24,4,((0,b'\0'),(4,integer(19,2)),(8,integer(23)),(12,bytes(12))))],warnings=override)
    for name,decl,expr,size,align,fields,warn in (
        ('union selected array','union U { long l; int a[2]; }; union U cell={.a={19,23}};', 'cell.a[0]+cell.a[1]==42',8,8,((0,vector([19,23])),),((),())),
        ('union selected scalar','union U { char c; long l; }; union U cell={.l=42};','cell.l==42',8,8,((0,integer(42,8)),),((),())),
        ('union switches member','union U { long l; int a[2]; }; union U cell={.l=9,.a={19,23}};', 'cell.a[0]+cell.a[1]==42',8,8,((0,vector([19,23])),),override),
        ('anonymous member designation','struct R { int lead; union { int x; long y; }; int tail; }; struct R cell={.y=42,.tail=7};','cell.lead==0 && cell.y==42 && cell.tail==7 && sizeof cell==24',24,8,((0,bytes(4)),(8,integer(42,8)),(16,integer(7))), ((),()))):
        add(name,decl,expr,[Object('cell',size,align,fields)],warnings=warn)
    for name,bound,literal,wanted in (
        ('inferred string','','"abc"',b'abc\0'),('embedded NUL','','"a\\0bc"',b'a\0bc\0'),
        ('exact truncation','3','"abc"',b'abc'),('string padded','6','"abc"',b'abc\0\0\0'),
        ('braced string','','{"a\\0b"}',b'a\0b\0'),('empty string','','""',b'\0')):
        checks=' && '.join(f'(unsigned char)cell[{i}]=={n}' for i,n in enumerate(wanted))
        add(name,f'char cell[{bound}]={literal};',checks+f' && sizeof cell=={len(wanted)}',
            [Object('cell',len(wanted),1,((0,wanted),))])
    add('nested character arrays','char cell[2][4]={"a","bc"};',
        'cell[0][0]==97 && cell[0][3]==0 && cell[1][1]==99 && cell[1][3]==0',
        [Object('cell',8,1,((0,b'a\0\0\0bc\0\0'),))])
    for scope,prefix,tls,public,block in (
        ('global','',False,True,False),('private','static ',False,False,False),
        ('TLS','_Thread_local ',True,True,False),('private TLS','static _Thread_local ',True,False,False),
        ('block static','static ',False,False,True),('block TLS','static _Thread_local ',True,False,True)):
        header='int target[3]={19,23,42}; static int fun(void) { return 42; } struct R { const int n; int *p; int (*f)(void); char *s; int *z; }; '
        decl=prefix+'struct R cell={.n=42,.p=target+2,.f=fun,.s="a\\0b",.z=0}; '
        check='cell.n==42 && cell.p==target+2 && *cell.p==42 && cell.f()==42 && cell.s[0]==97 && cell.s[1]==0 && cell.s[2]==98 && cell.s[3]==0 && !cell.z'
        owner=header+(('int test(void) { '+decl+'return ('+check+')?42:1; }') if block else decl+'int test(void) { return ('+check+')?42:1; }')
        refs={8:OffsetReference('object','target',byte_addend=8),16:OffsetReference('function','fun'),24:OffsetReference('string',contents=b'a\0b\0')}
        cases.append(Case(scope+' pointer/function/string/const/null',owner,(
            Object('target',12,4,((0,vector([19,23,42])),)),
            Object(None if block else 'cell',40,8,((0,integer(42)),(32,bytes(8))),public,tls,refs))))
    for decl,expr,objs in (
        ('int cell[3]={};','cell[0]==0 && cell[2]==0',[Object('cell',12,4,((0,bytes(12)),))]),
        ('struct R { int n; int *p; }; struct R cell={};','!cell.n && !cell.p',[Object('cell',16,8,((0,bytes(4)),(8,bytes(8))))]),
        ('int cell={};','cell==0',[Object('cell',4,4,((0,bytes(4)),))])):
        add('C23 empty '+decl,decl,expr,objs,features=('empty',))
    add('C23 nullptr aggregate','struct R { int *p; int (*f)(void); typeof(nullptr) n; }; struct R cell={nullptr,nullptr,nullptr};',
        '!cell.p && !cell.f && cell.n==nullptr',[Object('cell',24,8,((0,bytes(24)),))],features=('nullptr','typeof'))
    add('large sparse compact zero','unsigned char cell[1048576]={[1048575]=42};',
        'cell[0]==0 && cell[1048574]==0 && cell[1048575]==42 && sizeof cell==1048576',
        [Object('cell',1048576,1,((0,bytes(1048575)),(1048575,b'*')))],compact=True)
    # Automatic initialization uses runtime expressions, no undefined evaluation order.
    for name,body in (
        ('automatic nested expressions','int n=19; int a[2][2]={{n,n+4},{}}; return a[0][0]+a[0][1]==42 && a[1][1]==0?42:1;'),
        ('automatic designated expressions','int n=19; int a[4]={[2]=n,n+4}; return a[0]==0 && a[1]==0 && a[2]+a[3]==42?42:1;'),
        ('automatic record expression copy','struct R { int x; int y; }; struct R a={19,23}; struct R b=a; return b.x+b.y==42?42:1;'),
        ('automatic string bounds','char a[3]="abc"; return a[0]==97 && a[2]==99 && sizeof a==3?42:1;')):
        cases.append(Case(name,'int test(void) { '+body+' }',features=('empty',) if name=='automatic nested expressions' else ()))
    add('partial repeated designation retains siblings',
        'struct I { int x; int y; }; struct R { struct I in; int tail; }; struct R cell={.in.x=19,.in.y=23};',
        'cell.in.x+cell.in.y==42 && cell.tail==0',
        [Object('cell',12,4,((0,vector([19,23,0])),))])
    add('whole designation resets implicit remainder',
        'struct I { int x; int y; }; struct R { struct I in; int tail; }; struct R cell={.in={1,2},.in={42}};',
        'cell.in.x==42 && cell.in.y==0 && cell.tail==0',
        [Object('cell',12,4,((0,vector([42,0,0])),))],warnings=override)
    add('nested designation retains explicit sibling',
        'struct I { int x; int y; }; struct R { struct I in; int tail; }; struct R cell={.in={19,23},.in.y=42};',
        'cell.in.x==19 && cell.in.y==42 && cell.tail==0',
        [Object('cell',12,4,((0,vector([19,42,0])),))],warnings=override)
    add('inferred bound next declarator capture','int cell[]={19,23}, other[sizeof cell]={7};',
        'sizeof cell==8 && sizeof other==32 && cell[0]+cell[1]==42 && other[0]==7 && other[7]==0',
        [Object('cell',8,4,((0,vector([19,23])),)),Object('other',32,4,((0,vector([7]+[0]*7)),))])
    add('prior complete bound composite','extern int cell[4]; int cell[]={19,23};',
        'sizeof cell==16 && cell[0]+cell[1]==42 && cell[3]==0',
        [Object('cell',16,4,((0,vector([19,23,0,0])),))])
    for typ in ('signed char','unsigned char'):
        add(typ+' braced string',typ+' cell[3]={"abc"};',
            'cell[0]==97 && cell[2]==99 && sizeof cell==3',
            [Object('cell',3,1,((0,b'abc'),))])
    add('concatenated embedded NUL','char cell[]="a\\0" "bc";',
        'sizeof cell==5 && cell[0]==97 && cell[1]==0 && cell[3]==99 && cell[4]==0',
        [Object('cell',5,1,((0,b'a\0bc\0'),))])
    for name,expr in (('conditional address','1?target+2:target'),
                      ('conditional skipped call','1?target+2:missing()'),
                      ('conditional skipped load','1?target+2:other'),
                      ('conditional skipped comma','1?target+2:(0,target)'),
                      ('pointer through void','(int *)(void *)(target+2)')):
        decl='int target[3]={19,23,42}; int *other; int *missing(void); int *cell='+expr+';'
        warnings=((),())
        if name=='conditional skipped comma':
            warnings=((),(('warning','left operand of comma operator has no effect [-Wunused-value]'),))
        add(name,decl,'cell==target+2 && *cell==42',
            [Object('target',12,4,((0,vector([19,23,42])),)),Object('other',8,8,((0,bytes(8)),)),
             Object('cell',8,8,(),refs={0:OffsetReference('object','target',byte_addend=8)})],warnings=warnings)
    cases.append(Case('N3096 p37 partial aggregate copy',
        'struct T { int l; int k; }; struct S { int i; struct T t; }; '
        'int test(void) { struct T x={3,42}; struct S y={.i=9,.t=x,.t.l=41}; '
        'return y.i==9 && y.t.l==41 && y.t.k==42?42:1; }',
        warnings=((),(('warning','initializer partially overrides prior initialization of this subobject [-Winitializer-overrides]'),('note','previous initialization is here'))),gcc_discrepancy=True))
    add('one MiB compact allzero','unsigned char cell[1048576]={0};',
        'cell[0]==0 && cell[1048575]==0 && sizeof cell==1048576',
        [Object('cell',1048576,1,((0,bytes(1048576)),))],compact=True)
    for name,expr in (
        ('static address truth','target?target+2:0'),
        ('static samebase equality','(target+1==&target[1])?target+2:target'),
        ('static null equality','((int*)0==0)?target+2:target'),
        ('static address logical','(!target || target+1)?target+2:target'),
        ('static equality arithmetic','((target+1==&target[1])+1==2)?target+2:target')):
        add(name,'int target[3]={19,23,42}; int *cell='+expr+';',
            'cell==target+2 && *cell==42',
            [Object('target',12,4,((0,vector([19,23,42])),)),
             Object('cell',8,8,(),refs={0:OffsetReference('object','target',byte_addend=8)})])
    for name,header,expression,expected,offset,size,align,fields in (
        ('struct initial member forward','struct S { int x,y; }; struct S target={19,23};',
         '(int*)&target+1','&target.x+1',4,8,4,((0,vector([19,23])),)),
        ('struct initial member reciprocal','struct S { int x,y; }; struct S target={19,23};',
         '(struct S*)&target.x+1','&target+1',8,8,4,((0,vector([19,23])),)),
        ('union member forward','union U { int x; long y; }; union U target={.x=42};',
         '(int*)&target+1','&target.x+1',4,8,8,((0,integer(42)),)),
        ('union member reciprocal','union U { int x; long y; }; union U target={.x=42};',
         '(union U*)&target.x+1','&target+1',8,8,8,((0,integer(42)),)),
        ('character whole array actual element','int target[3]={19,23,42};',
         '(int*)((char*)&target+4)+1','&target[2]',8,12,4,((0,vector([19,23,42])),)),
        ('character record actual member','struct S { int x,y; }; struct S target={19,23};',
         '(int*)((char*)&target+4)+1','&target.y+1',8,8,4,((0,vector([19,23])),))):
        typ='struct S *' if name=='struct initial member reciprocal' else 'union U *' if name=='union member reciprocal' else 'int *'
        add(name,header+typ+'cell='+expression+';', 'cell=='+expected,
            [Object('target',size,align,fields),Object('cell',8,8,(),refs={0:OffsetReference('object','target',byte_addend=offset)})])
    cases.append(Case('initialized shared union DAG depth4 runtime',
        shared_union_initializer(4)+' int test(void) { if(o.d.a.a.a.a.a!=0) return 1; '
        'o.d.a.a.a.a.a=42; return o.d.a.a.a.a.a; }',
        (Object('o',4,4,((0,bytes(4)),)),),compact=True,bounded_work=True))
    cases.append(Case('automatic one MiB compact zero',
        'int test(void) { unsigned char cell[1048576]={0}; return cell[0]==0 && cell[1048575]==0?42:1; }',compact=True))
    cases.append(Case('automatic one MiB compact string',
        'int test(void) { char cell[1048576]="hello"; return cell[0]==104 && cell[4]==111 && cell[5]==0 && cell[1048575]==0?42:1; }',compact=True))
    predicate='&g'
    for _ in range(60): predicate='('+predicate+'?&g:(int*)0)'
    cases.append(Case('bounded nested pointer predicate depth60',
        'int g; int *p='+predicate+'; int test(void) { return p==&g?42:1; }',
        (Object('g',4,4,((0,bytes(4)),)),Object('p',8,8,(),refs={0:OffsetReference('object','g')})),
        compact=True,bounded_work=True))
    add('promoted exact conditional null','int *cell=1?(int *)0:(int *)0;', '!cell', [Object('cell',8,8,((0,bytes(8)),))])
    cases.append(Case('N3096 union retention exact reviewer original','union U{struct S{int x,y;}s;long l;};struct R{union U u;};int main(void){union U seed={.s={3,4}};struct R r={.u=seed,.u.s.x=9};return r.u.s.x==9&&r.u.s.y==4?0:1;}',
        warnings=((), (('warning', 'initializer partially overrides prior initialization of this subobject [-Winitializer-overrides]'), ('note', 'previous initialization is here'))),gcc_discrepancy=True,standalone=True,success_exit=0,compact=True,companion=''))
    cases.append(Case('N3096 union retention direct union destination struct member copy','union U{struct S{int x,y;}s;long l;};int main(void){union U seed={.s={3,4}};union U r={.s=seed.s,.s.x=9};return r.s.x==9&&r.s.y==4?0:1;}',
        warnings=((), (('warning', 'initializer partially overrides prior initialization of this subobject [-Winitializer-overrides]'), ('note', 'previous initialization is here'))),gcc_discrepancy=True,standalone=True,success_exit=0,compact=True,companion=''))
    cases.append(Case('N3096 union retention whole parent record containing union','union U{struct S{int x,y;}s;long l;};struct R{union U u;};struct O{struct R r;};int main(void){struct R seed={.u.s={3,4}};struct O o={.r=seed,.r.u.s.x=9};return o.r.u.s.x==9&&o.r.u.s.y==4?0:1;}',
        warnings=((), (('warning', 'initializer partially overrides prior initialization of this subobject [-Winitializer-overrides]'), ('note', 'previous initialization is here'))),gcc_discrepancy=True,standalone=True,success_exit=0,compact=True,companion=''))
    cases.append(Case('N3096 union retention copy fragment evaluation once','union U{struct S{int x,y,z;}s;long l;};struct R{union U u;};int main(void){int n=0;union U seed={.s={3,4,5}};struct R r={.u=(++n,seed),.u.s.y=9};return n==1&&r.u.s.x==3&&r.u.s.y==9&&r.u.s.z==5?0:1;}',
        warnings=((), (('warning', 'initializer partially overrides prior initialization of this subobject [-Winitializer-overrides]'), ('note', 'previous initialization is here'))),gcc_discrepancy=True,standalone=True,success_exit=0,compact=True,companion=''))
    for case in cases:
        for obj in case.objects:
            for offset,contents in obj.fields:
                width=min(obj.align,len(contents)&-len(contents),8)
                if case.name in ('union selected array','union switches member'): width=4
                for position in range(0,len(contents),width):
                    if any(contents[position:position+width]): obj.typed[offset+position]=width
    return cases


def optional_compiler(variable,names):
    if variable in os.environ:
        value=os.environ[variable]
        assert value and shutil.which(value),('explicit compiler unavailable',variable,value)
        return value
    return next((shutil.which(name) for name in names if shutil.which(name)),None)


def selected_compilers():
    compilers=native_compilers(HOST,optional_compiler('CLANG_CC',('clang-18','clang')))
    gcc11=optional_compiler('GCC11_CC',('gcc-11','gcc'))
    if gcc11:
        version=invoke([gcc11,'-dumpversion'])
        assert version.returncode==0 and not version.stderr
        if version.stdout.strip().split('.')[0]!='11':
            assert 'GCC11_CC' not in os.environ,('GCC11_CC is not GCC11',version)
            gcc11=None
    gcc13=optional_compiler('GCC13_CC',('gcc-13',))
    if gcc13:
        version=invoke([gcc13,'-dumpversion'])
        assert version.returncode==0 and not version.stderr and version.stdout.strip().split('.')[0]=='13',('GCC13_CC is not GCC13',version)
    else: print('GCC13 unavailable (optional): NOT an agreement')
    for extra in (gcc11,gcc13):
        if extra:
            for cc in native_compilers(HOST,extra):
                if all(os.path.realpath(shutil.which(cc))!=os.path.realpath(shutil.which(old)) for old in compilers): compilers.append(cc)
    if not gcc11: print('GCC11 unavailable: NOT an agreement')
    if not any(clang_style(cc) for cc in compilers): print('Clang unavailable: NOT an agreement')
    return compilers


def match_object(elf,obj,qbe=False,used=None):
    used=set() if used is None else used
    matches=[]
    for s in elf.symbols:
        if not s['section'] or s['section']>=len(elf.sections) or s['name'] in used: continue
        if obj.name is not None and s['name']!=obj.name: continue
        if obj.name is None and (s['binding']!=0 or s['kind'] not in (0,1,6)): continue
        if s['kind']!=(6 if obj.tls else 0 if qbe else 1): continue
        if s['binding']!=int(obj.public) or s['size']!=(0 if qbe else obj.size): continue
        sec=elf.sections[s['section']]
        if sec[1] not in (1,8) or not sec[2]&2 or bool(sec[2]&0x400)!=obj.tls: continue
        if sec[8]<obj.align or s['value']%obj.align or s['value']+obj.size>sec[5]: continue
        data=bytes(obj.size) if sec[1]==8 else elf.section_bytes(s['section'])[s['value']:s['value']+obj.size]
        if not all(data[o:o+len(b)]==b for o,b in obj.fields): continue
        matches.append(s)
    assert len(matches)==1, ('ELF object extent/type/bytes/alignment/binding',obj,matches)
    used.add(matches[0]['name']); return matches[0]


def check_references(elf,s,obj):
    rels=[r for r in elf.relocations if r['section']==s['section'] and s['value']<=r['offset']<s['value']+obj.size]
    assert len(rels)==len(obj.refs),('unexpected/missing initializer relocations',s,rels,obj.refs)
    for offset,expected in obj.refs.items():
        found=[r for r in rels if r['offset']==s['value']+offset]
        assert len(found)==1 and found[0]['kind']==1, ('exact R_X86_64_64 slot',offset,found)
        r=found[0]; base=r['symbol']
        if expected.kind=='string':
            assert 0<base['section']<len(elf.sections)
            sec=elf.sections[base['section']]; assert sec[2]&2 and not sec[2]&4
            start=base['value']+r['addend']-expected.byte_addend
            assert start>=0 and elf.section_bytes(base['section'])[start:start+len(expected.contents)]==expected.contents
        else:
            target=elf.symbol(expected.name)
            if base['name']==expected.name: actual=r['addend']
            else:
                assert base['kind']==3 and target['section'] and base['section']==target['section']
                actual=base['value']+r['addend']-target['value']
            assert actual==expected.byte_addend,('logical base/addend',expected,r)
            if target['section']: assert bool(elf.sections[target['section']][2]&4)==(expected.kind=='function')


def check_elf(elf,case,qbe=False):
    used=set()
    for obj in case.objects:
        s=match_object(elf,obj,qbe,used); check_references(elf,s,obj)
        if obj.tls:
            uses=[r for r in elf.relocations if r['symbol']['name']==s['name'] and r['kind'] in (19,22,23)]
            allowed={0,*obj.refs,*[offset for offset,_ in obj.fields]}
            assert uses and all((r['addend'] in allowed if r['kind']==23 else r['addend']==-4) for r in uses),(case.name,uses,allowed)


def parse_data(text):
    pattern=r'^(export )?(thread )?data \$([^\s=]+) = align (\d+) \{([^}]+)\}\s*$'
    blocks={}
    for public,tls,name,alignment,body in re.findall(pattern,text,re.M):
        assert name not in blocks,('duplicate data',name)
        data=bytearray(); refs={}; types={}
        body=body.strip()
        if body.endswith(','): body=body[:-1]  # QBE's single optional trailing comma.
        for item in body.split(','):
            item=item.strip(); m=re.fullmatch(r'([bhwlz])\s+(.+)',item); assert m,('unparsed typed IL fragment',item)
            kind,value=m.groups(); pos=len(data)
            if kind=='z':
                assert re.fullmatch(r'[0-9]+',value) and 0<int(value)<=1048576
                data.extend(bytes(int(value))); continue
            width={'b':1,'h':2,'w':4,'l':8}[kind]; types[pos]=width
            ref=re.fullmatch(r'\$([^\s+]+)(?:\s*\+\s*(-?\d+))?',value)
            if ref:
                assert kind=='l'; refs[pos]=(ref[1],int(ref[2] or 0)); data.extend(bytes(width))
            else:
                assert re.fullmatch(r'-?\d+',value); data.extend(integer(int(value),width))
            assert len(data)<=1048576, 'IL storage bound'
        blocks[name]=(bool(public),bool(tls),int(alignment),bytes(data),refs,types)
    # Every data introducer must be parsed; malformed/untyped blocks never hide.
    assert len(blocks)==len(re.findall(r'^.*\bdata\s+\$',text,re.M)),('unparsed data block',text)
    return blocks


def check_il(text,case):
    if case.compact:
        assert len(text.encode())<20000 and len(text.splitlines())<400,'initializer IL source explosion'
        assert not re.search(r'\bcall \$(?:memset|memcpy|memmove)\b',text)
        assert all(int(n)<=64 for n in re.findall(r'\bblit[^\n]*,\s*(\d+)\s*$',text,re.M))
    blocks=parse_data(text); used=set()
    # Decoded source literals can be emitted even for array-copy initialization.
    # Accept only exact private, align-1 literal blobs from these unchanged
    # originals, with multiplicity bounded by source occurrences (no wildcard).
    literals=Counter()
    for group in re.findall(r'"(?:\\.|[^"\\])*"(?:\s*"(?:\\.|[^"\\])*")*',case.owner):
        pieces=re.findall(r'"(?:\\.|[^"\\])*"',group)
        literal=''.join(ast.literal_eval(piece) for piece in pieces).encode('latin1')+b'\0'
        literals[literal]+=1
    for name,block in blocks.items():
        if re.fullmatch(r'\.Lkcc\.string\.\d+',name):
            assert block[:3]==(False,False,1) and not block[4] and literals[block[3]]>0,('unexpected literal storage',name,block)
            literals[block[3]]-=1; used.add(name)
    for obj in case.objects:
        candidates=[]
        for name,(public,tls,align,data,refs,types) in blocks.items():
            if name in used or (obj.name is not None and name!=obj.name): continue
            if (public,tls,align,len(data))!=(obj.public,obj.tls,obj.align,obj.size): continue
            if not all(data[o:o+len(b)]==b for o,b in obj.fields): continue
            if set(refs)!=set(obj.refs): continue
            if any(types.get(o)!=width and not all(types.get(o+i)==1 for i in range(width)) for o,width in obj.typed.items()): continue
            candidates.append(name)
        assert len(candidates)==1,('typed IL extent/alignment/binding/member bytes',case.name,obj,candidates,text)
        name=candidates[0]; used.add(name)
        for offset,expected in obj.refs.items():
            base,addend=blocks[name][4][offset]
            assert blocks[name][5][offset]==8 and addend==expected.byte_addend
            if expected.kind=='string':
                assert base in blocks
                b=blocks[base]; assert b[:3]==(False,False,1) and b[3]==expected.contents and not b[4]
                used.add(base)
            else: assert base==expected.name
    assert used==set(blocks),('unexpected initialized storage',set(blocks)-used)


# These are constraints, not implementation subset gaps or UB demonstrations.
CONSTRAINTS={
    'excess array': 'int cell[1]={1,2};',
    'excess struct': 'struct R { int x; }; struct R cell={1,2};',
    'negative index': 'int cell[2]={[-1]=42};',
    'index outside bound': 'int cell[2]={[2]=42};',
    'missing member': 'struct R { int x; }; struct R cell={.missing=42};',
    'nonconstant designator': 'int n; int cell[2]={[n]=42};',
    'string over bound': 'char cell[2]="abc";',
    'nonconstant static leaf': 'int n; struct R { int x; }; struct R cell={n};',
}
CONSTRAINTS.update({
    'self incomplete sizeof': 'int cell[]={sizeof cell};',
    'excess scalar': 'int cell={1,2};',
    'designator on scalar': 'int cell={.x=42};',
    'incompatible pointer member': 'struct R { int *p; }; char target; struct R cell={&target};',
})

# Valid language forms outside the explicit M17 supported type/ABI set. These
# compile unchanged on natives, never run, and never become native constraints.
SUBSET={
    'M21 aggregate argument': 'struct S { int x; }; int f(struct S s) { return s.x; }',
    'M21 aggregate return': 'struct S { int x; }; struct S f(struct S *p) { return *p; }',
    'M22 bitfield': 'struct S { unsigned int x:3; }; struct S s;',
    'M22 flexible array': 'struct S { int n; int a[]; }; struct S *p;',
}
# No native compilation or execution for UB/proof-boundary/resource refusals.
# Acceptance by a native is deliberately not an oracle for these cases.
PROOF_AND_RESOURCE={
    'array beyond onepast': 'int target[3]; struct R { int *p; }; struct R cell={target+4};',
    'null arithmetic': 'struct R { int *p; }; struct R cell={(int*)0+0};',
    'no fabricated short subobject': 'int target; struct R { short *p; }; struct R cell={(short*)&target+1};',
    'member cast beyond domain': 'struct S { int x,y; } target; int *cell=(int*)&target+2;',
    'character scalar cannot widen domain': 'int target[3]; int *cell=(int*)((char*)&target[0]+8);',
    'row onepast cast cannot cross row': 'int target[2][3]; int *cell=(int*)((char*)&target[0]+12)+1;',
    'one MiB plus one': 'unsigned char cell[1048577]={0};',
    'long array storage boundary': 'long cell[131073]={0};',
    'index extent overflow': 'int cell[]={[18446744073709551615ULL]=42};',
}

NATIVE_CONSTRAINTS={
'excess array': (
(('error', 'excess elements in array initializer'), ('note', "(near initialization for 'cell')")),
(('error', 'excess elements in array initializer [-Werror,-Wexcess-initializers]'),),
),
'excess struct': (
(('error', 'excess elements in struct initializer'), ('note', "(near initialization for 'cell')")),
(('error', 'excess elements in struct initializer [-Werror,-Wexcess-initializers]'),),
),
'negative index': (
(('error', 'array index in initializer exceeds array bounds'), ('note', "(near initialization for 'cell')")),
(('error', "array designator value '-1' is negative"),),
),
'index outside bound': (
(('error', 'array index in initializer exceeds array bounds'), ('note', "(near initialization for 'cell')")),
(('error', 'array designator index (2) exceeds array bounds (2)'),),
),
'missing member': (
(('error', "'struct R' has no member named 'missing'"),),
(('error', "field designator 'missing' does not refer to any field in type 'struct R'"),),
),
'nonconstant designator': (
(('error', 'nonconstant array index in initializer'), ('note', "(near initialization for 'cell')")),
(('error', 'expression is not an integer constant expression'),),
),
'string over bound': (
(('error', "initializer-string for array of 'char' is too long"),),
(('error', 'initializer-string for char array is too long [-Werror,-Wexcess-initializers]'),),
),
'nonconstant static leaf': (
(('error', 'initializer element is not constant'), ('note', "(near initialization for 'cell.x')")),
(('error', 'initializer element is not a compile-time constant'),),
),
}



NATIVE_CONSTRAINTS.update({'self incomplete sizeof': ((('error', "invalid application of 'sizeof' to incomplete type 'int[]'"),),
                            (('error', "invalid application of 'sizeof' to an incomplete type 'int[]'"),)),
 'excess scalar': ((('error', 'excess elements in scalar initializer'),
                    ('note', "(near initialization for 'cell')")),
                   (('error', 'excess elements in scalar initializer [-Werror,-Wexcess-initializers]'),)),
 'designator on scalar': ((('error', 'field name not in record or union initializer'),
                           ('note', "(near initialization for 'cell')")),
                          (('error',
                            "initialization of non-aggregate type 'int' with a designated initializer list"),)),
 'incompatible pointer member': ((('error',
                                   "initialization of 'int *' from incompatible pointer type 'char *' "
                                   '[-Wincompatible-pointer-types]'),
                                  ('note', "(near initialization for 'cell.p')")),
                                 (('error',
                                   "incompatible pointer types initializing 'int *' with an expression of type "
                                   "'char *' [-Werror,-Wincompatible-pointer-types]"),))})

KCC_REFUSALS={'excess array': (1, 16, 'excess elements in initializer'),
 'excess struct': (1, 39, 'excess elements in initializer'),
 'negative index': (1, 14, 'array initializer index exceeds bound or storage limit (1 MiB)'),
 'index outside bound': (1, 14, 'array initializer index exceeds bound or storage limit (1 MiB)'),
 'missing member': (1, 37, 'initializer designates an unknown member'),
 'nonconstant designator': (1, 21, 'array designator requires an integer constant expression'),
 'string over bound': (1, 14, 'string initializer is too long for character array'),
 'nonconstant static leaf': (1, 44, 'static initializer must be a constant expression'),
 'self incomplete sizeof': (1, 13, 'sizeof requires a complete object type'),
 'excess scalar': (1, 13, 'excess elements in initializer'),
 'designator on scalar': (1, 11, 'member designator requires a struct or union'),
 'incompatible pointer member': (1,
                                 51,
                                 'unsupported pointer conversion (incompatible pointers or integer/pointer '
                                 'conversion)'),
 'M21 aggregate argument': (1, 26, 'aggregate function arguments are not supported yet (M21)'),
 'M21 aggregate return': (1, 31, 'aggregate function returns are not supported yet (M21)'),
 'M22 bitfield': (1, 26, 'bit-fields are not supported yet (M22)'),
 'M22 flexible array': (1, 24, 'flexible array members are not supported yet (M22)'),
 'array beyond onepast': (1, 59, 'static pointer offset is outside its captured object bounds'),
 'null arithmetic': (1,45,'pointer arithmetic on null is not a static address constant'),
 'no fabricated short subobject': (1,
                                   67,
                                   'file-scope pointer initializer requires a supported null or direct address '
                                   'constant expression'),
 'member cast beyond domain': (1, 54, 'static pointer offset is outside its captured object bounds'),
 'character scalar cannot widen domain': (1, 50, 'static pointer offset is outside its captured object bounds'),
 'row onepast cast cannot cross row': (1, 57, 'static pointer offset is outside its captured object bounds'),
 'one MiB plus one': (1, 20, 'array bound must be positive and fit array type storage limit (1 MiB)'),
 'long array storage boundary': (1, 11, 'array bound must be positive and fit array type storage limit (1 MiB)'),
 'index extent overflow': (1, 13, 'array initializer index exceeds bound or storage limit (1 MiB)')}


# Compact type DAGs: unsupported-domain refusals, NEVER native evidence.
# At most 42 source lines (<2 KiB), constant four-byte object size.
UNION_DOMAIN_CASES={}
for _depth in (12,20,26,40):
    _name=f'union domain work depth {_depth}'
    _text='union U0{int a,b;};\n'
    _text+=''.join(f'union U{level}{{union U{level-1} a,b;}};\n' for level in range(1,_depth+1))
    _text+=f'union U{_depth} u;short*p=(short*)&u+1;'
    assert len(_text)<2048
    UNION_DOMAIN_CASES[_name]=_text
    KCC_REFUSALS[_name]=(_depth+2,31,'file-scope pointer initializer requires a supported null or direct address constant expression')


def validate_kcc_refusal(source,name,result):
    line,column,message=KCC_REFUSALS[name]
    assert result.returncode==1 and not result.stdout,(name,result)
    assert result.stderr==f'{source}:{line}:{column}: error: {message}\n',(name,result.stderr)


def kcc_refusal(source,name):
    validate_kcc_refusal(source,name,invoke([KCC,source]))


def bounded_kcc_work(source,name,compiler=KCC,runner=subprocess.run):
    try:
        result=runner([str(compiler),str(source)],capture_output=True,text=True,timeout=3)
    except subprocess.TimeoutExpired as error:
        raise AssertionError(('static pointer proof exceeded 3-second work bound',name)) from error
    return result


def bounded_domain_refusal(source,name,compiler=KCC,runner=subprocess.run):
    validate_kcc_refusal(source,name,bounded_kcc_work(source,name,compiler,runner))


def native_constraint(cc,source,output,name):
    output.unlink(missing_ok=True)
    r=invoke([cc,*diagnostic_flags(cc),'-std=c2x','-pedantic-errors','-fno-common','-c',source,'-o',output])
    validate_native_constraint(cc,source,output,name,r)


def validate_native_constraint(cc,source,output,name,r):
    actual=native_diagnostics(r.stderr,source,source.read_text(),clang_style(cc))
    expected=NATIVE_CONSTRAINTS[name][int(clang_style(cc))]
    assert r.returncode==1 and not r.stdout and not output.exists(),(cc,name,r)
    assert actual==expected,(cc,name,actual,expected,r.stderr)


def empty_probe(cc,source,output):
    text='int cell[1]={};\n'; source.write_text(text); output.unlink(missing_ok=True)
    r=invoke([cc,*diagnostic_flags(cc),'-std=c2x','-pedantic-errors','-c',source,'-o',output])
    if r.returncode==0:
        assert not r.stdout and not r.stderr and output.is_file() and output.stat().st_size
        return True
    assert r.returncode==1 and not r.stdout and not output.exists()
    assert native_diagnostics(r.stderr,source,text,clang_style(cc))==(('error','ISO C forbids empty initializer braces [-Wpedantic]'),),(cc,r)
    return False


# These hashes are immutable observations, NOT derived from mutable fixtures at
# test runtime. Exact owner bytes include their terminating newline; standalone
# originals have an empty companion. Only these two observed GCC releases may
# explain their exact defined-runtime exit1 discrepancy.
KNOWN_GCC_DISCREPANCY_FIXTURES={'N3096 p37 partial aggregate copy': ('f0257e0e0a17f0334056e1a1e3c7545c0d01c8fd4a819f9c37d45f097b6a1513',
                                      'ad332b625bcde878c4f9d19f89c1554aa8ee022df9dd7e4c6aed6d16a1467b21',
                                      42,
                                      False),
 'N3096 union retention exact reviewer original': ('392a2525fa830e6af58af354f67372eb51c3e78dd8c0b5eafe570225525bb0be',
                                                   'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
                                                   0,
                                                   True),
 'N3096 union retention direct union destination struct member copy': ('69aa5732d23ae5f0d846b41702eeabfe36b3ff40b8f88cd6e30eead008e95a18',
                                                                       'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
                                                                       0,
                                                                       True),
 'N3096 union retention whole parent record containing union': ('2998788e698ee19bbb1a6732609e5209ba7ce40ea77557a740cbc1f6591fa5ca',
                                                                'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
                                                                0,
                                                                True),
 'N3096 union retention copy fragment evaluation once': ('049b262c2af1c1600c450cfbee2696ffae5cea1ed6f33e68f3f7adec6c9fe6ea',
                                                         'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
                                                         0,
                                                         True)}
KNOWN_GCC_DISCREPANCY_VERSIONS=frozenset(('11.5.0','13.4.0'))


def observed_gcc_discrepancy_version(compiler):
    banner=invoke([compiler,'--version'])
    version=invoke([compiler,'-dumpfullversion','-dumpversion'])
    assert banner.returncode==0 and not banner.stderr and banner.stdout.endswith('\n'),('GCC identity banner',compiler,banner)
    assert version.returncode==0 and not version.stderr and version.stdout.endswith('\n'),('GCC identity version',compiler,version)
    value=version.stdout.removesuffix('\n')
    assert value in KNOWN_GCC_DISCREPANCY_VERSIONS,('unobserved GCC discrepancy version',compiler,value)
    first=banner.stdout.splitlines()[0]
    assert ('(GCC)' in first or ('gcc' in first.lower() and '(Ubuntu ' in first)) and 'clang' not in first.lower(),('not observed GNU compiler identity',compiler,first)
    assert re.search(r'(?<![0-9.])'+re.escape(value)+r'(?![0-9.])',first),('GCC banner/version mismatch',compiler,first,value)
    return value


def validate_case_runtime(case,compiler,result,native=False):
    assert not result.stdout and not result.stderr,(case.name,compiler,result)
    if native and case.gcc_discrepancy:
        expected=KNOWN_GCC_DISCREPANCY_FIXTURES.get(case.name)
        actual=(hashlib.sha256((case.owner+'\n').encode()).hexdigest(),
                hashlib.sha256(case.companion.encode()).hexdigest(),case.success_exit,case.standalone)
        assert expected is not None and actual==expected,('uncurated discrepancy fixture bytes/name/protocol',case.name,actual,expected)
        assert result.returncode in (1,case.success_exit),(case.name,compiler,result)
        if result.returncode==case.success_exit: return True
        observed_gcc_discrepancy_version(compiler)
        return False
    assert result.returncode==case.success_exit,(case.name,compiler,result)
    return True


def run_case_program(compiler,objects,executable,case,native=False):
    producer([compiler,*objects,'-o',executable],executable)
    agreement=validate_case_runtime(case,compiler,invoke([executable]),native)
    if native and not agreement:
        print(f'{compiler}: {case.name}: N3096 6.7.10p37 defined-runtime DISCREPANCY (not agreement)')
    return agreement


def must_fail(fn,label):
    try: fn()
    except (AssertionError,KeyError,ValueError,struct_error): return
    raise AssertionError('poison accepted: '+label)


# struct.error is included without hiding unrelated infrastructure exceptions.
from struct import error as struct_error


def controls(d):
    harness_self_test(d); compiler_selection_self_test(d); address_controls(d); offset_controls(d)
    c=Case('control','', (Object('cell',16,8,((0,integer(42)),(8,bytes(8))),typed={0:4}),))
    text='export data $cell = align 8 { w 42, z 4, l 0 }\n'
    check_il(text,c)
    for bad in (text.replace('w 42','h 42'),text.replace('w 42','b 42, z 3'),text.replace('w 42','w 41'),text.replace('z 4','z 3'),text.replace('align 8','align 1'),text.replace('export ',''),text.replace('data','thread data'),text+text,text+'data $extra = align 1 { b 7 }\n',text.replace('l 0','l $wrong')):
        must_fail(lambda:check_il(bad,c),'typed IL')
    source=d/'init-control.c'; output=d/'init-control.o'
    source.write_text('struct R { int x; long *p; }; struct R cell={42,0};\n')
    producer([HOST,'-std=c2x','-pedantic-errors','-fno-common','-c',source,'-o',output],output)
    elf=ElfRelocations(output); check_elf(elf,c)
    for kind in ('size','binding','type','offset','alignment','bytes','relocation'):
        bad=copy.deepcopy(elf); s=bad.symbol('cell')
        if kind=='size': s['size']=12
        elif kind=='binding': s['binding']=0
        elif kind=='type': s['kind']=6
        elif kind=='offset': s['value']+=1
        elif kind=='alignment':
            sec=list(bad.sections[s['section']]); sec[8]=1; bad.sections[s['section']]=tuple(sec)
        elif kind=='bytes':
            at=bad.sections[s['section']][4]+s['value']; bad.data=bad.data[:at]+b'X'+bad.data[at+1:]
        else: bad.relocations.append(dict(section=s['section'],offset=s['value']+8,kind=1,symbol=s,addend=0))
        must_fail(lambda:check_elf(bad,c),'ELF '+kind)
    qbe=copy.deepcopy(elf); qbe.symbol('cell')['kind']=0; qbe.symbol('cell')['size']=0
    check_elf(qbe,c,True)
    must_fail(lambda:check_elf(elf,c,True),'native symbol cannot impersonate QBE widthless label')
    referenced=next(c for c in fixtures() if c.name=='global pointer/function/string/const/null')
    source.write_text(referenced.owner+'\n')
    producer([HOST,'-std=c2x','-pedantic-errors','-fno-common','-O0','-c',source,'-o',output],output)
    refs=ElfRelocations(output); check_elf(refs,referenced)
    for kind in ('kind','slot','addend','base','missing','duplicate','literal'):
        bad=copy.deepcopy(refs); sym=bad.symbol('cell')
        r=next(r for r in bad.relocations if r['section']==sym['section'] and r['offset']==sym['value']+8)
        if kind=='kind': r['kind']=2
        elif kind=='slot': r['offset']+=1
        elif kind=='addend': r['addend']+=4
        elif kind=='base': r['symbol']={**r['symbol'],'name':'wrong','kind':1}
        elif kind=='missing': bad.relocations.remove(r)
        elif kind=='duplicate': bad.relocations.append(copy.deepcopy(r))
        else:
            r=next(r for r in bad.relocations if r['section']==sym['section'] and r['offset']==sym['value']+24)
            r['addend']+=1
        must_fail(lambda:check_elf(bad,referenced),'initializer own relocation '+kind)
    pointer=Case('pointer control','char *cell=\"ab\";',(Object('cell',8,8,(),refs={0:OffsetReference('string',contents=b'ab\0')}),))
    pointer_il='export data $cell = align 8 { l $literal }\ndata $literal = align 1 { b 97, b 98, b 0 }\n'
    check_il(pointer_il,pointer)
    for bad in (pointer_il.replace('l $literal','w $literal'),pointer_il.replace('l $literal','l $literal + 1'),pointer_il.replace('b 98','b 99'),pointer_il.replace('align 1','align 2'),pointer_il.replace('data $literal','export data $literal')):
        must_fail(lambda:check_il(bad,pointer),'typed IL string/reference')
    # The earlier exact object remains the subject of the padding controls.
    source.write_text('struct R { int x; long *p; }; struct R cell={42,0};\n')
    # Explicit aggregate padding remains unconstrained in both IL and ELF.
    padding=text.replace('z 4','w 12345'); check_il(padding,c)
    bad=copy.deepcopy(elf); s=bad.symbol('cell'); at=bad.sections[s['section']][4]+s['value']+4
    bad.data=bad.data[:at]+b'X'+bad.data[at+1:]; check_elf(bad,c)
    for cc in (HOST,):
        clean='int cell[1]={1,2};\n'; source.write_text(clean)
        r=invoke([cc,'-std=c2x','-pedantic-errors','-c',source,'-o',output])
        assert native_diagnostics(r.stderr+'tool noise\n',source,clean,clang_style(cc)) is None
        output.unlink(missing_ok=True)
        validate_native_constraint(cc,source,output,'excess array',r)
        for kind in ('status','stdout','noise','missing-newline','wrong-reason','extra-note','missing-diagnostic'):
            bad=copy.copy(r)
            if kind=='status': bad.returncode=0
            elif kind=='stdout': bad.stdout='partial IL\n'
            elif kind=='noise': bad.stderr+='tool noise\n'
            elif kind=='missing-newline': bad.stderr=bad.stderr.rstrip('\n')
            elif kind=='wrong-reason': bad.stderr=bad.stderr.replace('excess elements','different elements')
            elif kind=='extra-note': bad.stderr+=f'{source}:1:1: note: unexpected note\n'
            else: bad.stderr=''
            must_fail(lambda:validate_native_constraint(cc,source,output,'excess array',bad),'native fullstream '+kind)
    for name in ('CLANG_CC','GCC11_CC','GCC13_CC'):
        previous=os.environ.get(name)
        try:
            for bad in ('',str(d/'missing-compiler')):
                os.environ[name]=bad
                must_fail(lambda:optional_compiler(name,()),'explicit invalid '+name)
        finally:
            if previous is None: os.environ.pop(name,None)
            else: os.environ[name]=previous

    label='excess array'; line,column,message=KCC_REFUSALS[label]
    clean=subprocess.CompletedProcess([],1,'',f'{source}:{line}:{column}: error: {message}\n')
    validate_kcc_refusal(source,label,clean)
    for kind in ('status','stdout','message','column','note','junk','newline'):
        bad=copy.copy(clean)
        if kind=='status': bad.returncode=0
        elif kind=='stdout': bad.stdout='partial IL\n'
        elif kind=='message': bad.stderr=bad.stderr.replace(message,'wrong semantic reason')
        elif kind=='column': bad.stderr=bad.stderr.replace(f':{column}:',f':{column+1}:')
        elif kind=='note': bad.stderr+=f'{source}:1:1: note: unexpected note\n'
        elif kind=='junk': bad.stderr+='unparsed noise\n'
        else: bad.stderr=bad.stderr.rstrip('\n')
        must_fail(lambda:validate_kcc_refusal(source,label,bad),'KCC fullstream '+kind)
    domain_name='union domain work depth 40'
    line,column,message=KCC_REFUSALS[domain_name]
    bounded_clean=subprocess.CompletedProcess([],1,'',f'{source}:{line}:{column}: error: {message}\n')
    calls=[]
    def successful_refusal(args,**kwargs):
        calls.append((args,kwargs)); return bounded_clean
    bounded_domain_refusal(source,domain_name,compiler='fixture-kcc',runner=successful_refusal)
    assert calls==[(['fixture-kcc',str(source)],{'capture_output':True,'text':True,'timeout':3})]
    def expired(args,**kwargs):
        raise subprocess.TimeoutExpired(args,kwargs['timeout'])
    must_fail(lambda:bounded_domain_refusal(source,domain_name,runner=expired),'domain proof timeout is failure, not refusal')
    bad_domain=copy.copy(bounded_clean); bad_domain.stdout='partial IL\n'
    must_fail(lambda:bounded_domain_refusal(source,domain_name,runner=lambda *a,**k:bad_domain),'domain refusal no partial IL')
    valid_dag=compile_only_fixtures()[0]
    valid_dag_il='export data $o = align 4 { z 4 }\n'
    check_il(valid_dag_il,valid_dag)
    for bad in (valid_dag_il.replace('z 4','z 3'),valid_dag_il.replace('align 4','align 1'),valid_dag_il.replace('export ',''),valid_dag_il.replace('z 4','w 1')):
        must_fail(lambda:check_il(bad,valid_dag),'initialized DAG exact acceptance storage')
    identity=d/'gcc-observed-identity-control'
    identity.write_text('#!/bin/sh\ncase "$1" in\n--version) printf "gcc (GCC) 13.4.0\\n";;\n-dumpfullversion) printf "13.4.0\\n";;\n*) exit 90;;\nesac\n')
    identity.chmod(0o755)
    exact_runtime=next(c for c in fixtures() if c.name=='N3096 union retention exact reviewer original')
    normative=subprocess.CompletedProcess([],0,'','')
    discrepancy=subprocess.CompletedProcess([],1,'','')
    assert validate_case_runtime(exact_runtime,str(identity),normative,native=True)
    assert not validate_case_runtime(exact_runtime,str(identity),discrepancy,native=True)
    must_fail(lambda:validate_case_runtime(exact_runtime,str(identity),discrepancy),'KCC may not inherit native discrepancy')
    ordinary=Case('ordinary source','',success_exit=0)
    must_fail(lambda:validate_case_runtime(ordinary,str(identity),discrepancy,native=True),'no generic GCC waiver')
    for kind in ('signal','stdout','stderr','wrong-exit'):
        bad=copy.copy(discrepancy)
        if kind=='signal': bad.returncode=-11
        elif kind=='stdout': bad.stdout='tool noise\n'
        elif kind=='stderr': bad.stderr='unexpected diagnostic\n'
        else: bad.returncode=42
        must_fail(lambda:validate_case_runtime(exact_runtime,str(identity),bad,native=True),'exact discrepancy fullstream '+kind)
    for kind in ('name','owner','companion','marker','exit','standalone'):
        changed=copy.copy(exact_runtime)
        if kind=='name': changed.name+=' changed'
        elif kind=='owner': changed.owner+=' '
        elif kind=='companion': changed.companion+=' '
        elif kind=='marker': changed.gcc_discrepancy=False
        elif kind=='exit': changed.success_exit=42
        else: changed.standalone=False
        must_fail(lambda:validate_case_runtime(changed,str(identity),discrepancy,native=True),'changed discrepancy '+kind)
    unknown=copy.copy(exact_runtime); unknown.name='unregistered marked source'
    must_fail(lambda:validate_case_runtime(unknown,str(identity),discrepancy,native=True),'unregistered true marker')
    for fake_version,banner_version in (('12.4.0','12.4.0'),('17.0.1','17.0.1'),('13.4.0','11.5.0')):
        fake=d/'gcc-identity-control'
        fake.write_text('#!/bin/sh\ncase "$1" in\n--version) printf "gcc (GCC) '+banner_version+'\\n";;\n-dumpfullversion) printf "'+fake_version+'\\n";;\n*) exit 90;;\nesac\n')
        fake.chmod(0o755)
        must_fail(lambda:validate_case_runtime(exact_runtime,str(fake),discrepancy,native=True),'unobserved/mismatched compiler version')
    print('M17 poison controls: imported fresh producers/fullstream/selection/relocations; initializer IL/ELF/padding')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native-only',action='store_true'); p.add_argument('--harness-self-test',action='store_true')
    p.add_argument('--frozen-hash'); args=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='kcc initialization ') as tmp:
        d=Path(tmp); controls(d)
        if args.harness_self_test: return
        compilers=selected_compilers()
        source,other,obj,peer,ssa,asm,kobj,exe=[d/n for n in ('owner.c','peer.c','native.o','peer.o','k.ssa','k.s','k.o','program')]
        features={cc:features_for(cc,source,obj) for cc in compilers}
        for cc in compilers:
            if empty_probe(cc,source,obj): features[cc].add('empty')
        if not args.native_only:
            assert args.frozen_hash and re.fullmatch('[0-9a-f]{40}',args.frozen_hash),'explicit frozen hash required'
            root=Path(os.environ['KCC_SOURCE']).resolve()
            h=invoke(['git','-C',root,'rev-parse','HEAD']); assert h.returncode==0 and h.stdout.strip()==args.frozen_hash
            dirty=invoke(['git','-C',root,'status','--porcelain','--','src']); assert dirty.returncode==0 and not dirty.stdout
            assert Path(KCC).resolve().is_relative_to(root),'KCC must be built in frozen source checkout'
            assert QBE and shutil.which(QBE),'real explicit QBE required'
        counts={cc:[0,0,0] for cc in compilers}; kcount=0
        cases=fixtures(); assert len({c.name for c in cases})==len(cases)
        for case in cases:
            source.write_text(case.owner+'\n')
            other.write_text(case.companion)
            for cc in compilers:
                if not set(case.features)<=features[cc]: counts[cc][1]+=1; continue
                producer([cc,*diagnostic_flags(cc),'-std=c2x','-pedantic-errors','-fno-common','-O0','-c',source,'-o',obj],obj,case.warnings[int(clang_style(cc))])
                check_elf(ElfRelocations(obj),case)
                native_objects=[obj]
                if not case.standalone:
                    producer([cc,'-std=c2x','-pedantic-errors','-fno-common','-O0','-c',other,'-o',peer],peer)
                    native_objects.append(peer)
                if run_case_program(cc,native_objects,exe,case,native=True): counts[cc][0]+=1
            if args.native_only: continue
            r=bounded_kcc_work(source,case.name) if case.bounded_work else invoke([KCC,source]); assert r.returncode==0 and not r.stderr and r.stdout,(case.name,r)
            check_il(r.stdout,case); ssa.write_text(r.stdout)
            producer([QBE,'-t','amd64_sysv','-o',asm,ssa],asm)
            producer([HOST,'-Wa,-L','-c',asm,'-o',kobj],kobj); check_elf(ElfRelocations(kobj),case,True)
            kcc_objects=[kobj]
            if not case.standalone:
                producer([HOST,'-std=c2x','-pedantic-errors','-fno-common','-c',other,'-o',peer],peer)
                kcc_objects.append(peer)
            run_case_program(HOST,kcc_objects,exe,case); kcount+=1
        if not args.native_only:
            for case in compile_only_fixtures():
                source.write_text(case.owner+'\n')
                r=bounded_kcc_work(source,case.name)
                assert r.returncode==0 and not r.stderr and r.stdout,(case.name,r)
                check_il(r.stdout,case); ssa.write_text(r.stdout)
                producer([QBE,'-t','amd64_sysv','-o',asm,ssa],asm)
                producer([HOST,'-Wa,-L','-c',asm,'-o',kobj],kobj)
                check_elf(ElfRelocations(kobj),case,True)
            print(f'{len(compile_only_fixtures())} bounded standard-valid compile-only KCC/QBE/ELF acceptance (NOT runtime)')
        for name,text in CONSTRAINTS.items():
            source.write_text(text+'\n')
            for cc in compilers: native_constraint(cc,source,obj,name); counts[cc][2]+=1
            if not args.native_only: kcc_refusal(source,name)
        for name,text in SUBSET.items():
            source.write_text(text+'\n')
            for cc in compilers:
                producer([cc,*diagnostic_flags(cc),'-std=c2x','-pedantic-errors','-fno-common','-c',source,'-o',obj],obj)
            if not args.native_only: kcc_refusal(source,name)
        if not args.native_only:
            for name,text in PROOF_AND_RESOURCE.items():
                source.write_text(text+'\n'); kcc_refusal(source,name)
            for name,text in UNION_DOMAIN_CASES.items():
                source.write_text(text+'\n'); bounded_domain_refusal(source,name)
        print(f'Separate compile-only categories: {len(CONSTRAINTS)} constraints; {len(SUBSET)} native-valid unsupported; '
              f'{0 if args.native_only else len(PROOF_AND_RESOURCE)+len(UNION_DOMAIN_CASES)} KCC-only proof/resource refusals (never native oracles)')
        print(f'M17: {len(cases)} unchanged originals; frozen KCC/QBE/ELF/runtime {kcount}')
        for cc,(passed,gaps,constraints) in counts.items():
            print(f'{cc}: {passed} ELF/runtime agreements; {gaps} capability gaps NOT agreements; {constraints} exact native constraints')
        if args.native_only: print('NATIVE ONLY: no KCC production claim')
        else: print('Frozen source: '+args.frozen_hash)


if __name__=='__main__': main()

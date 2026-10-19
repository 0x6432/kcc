"""Independent M18 ordinary-enum oracle: unchanged C, fresh ELF and real ABI runs.

KCC=... QBE=... HOST_CC=... CLANG_CC=... [GCC13_CC=...] python3 tests/test_enumerations.py
--native-only does NOT claim KCC coverage. --harness-self-test only tests controls.
Fixed-underlying/out-of-int C23 enumerations belong to M23f, not constraints.
Only defined acceptance originals execute; rejected/deferred programs never do.
No native adapters, rewritten originals, optional QBE, or warning waivers.
"""
import argparse
import copy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from unittest.mock import patch

from test_integer_initializers import (
    invoke, producer, run_program, harness_self_test, native_diagnostics, clang_style,
)
from test_null_initializers import native_compilers, compiler_selection_self_test
from test_address_offsets import OffsetRelocations, OffsetReference
from test_compound_literals import il_extents

ROOT = Path(__file__).resolve().parents[1]
KCC = Path(os.environ.get('KCC', ROOT/'build'/'kcc'))
HOST = os.environ.get('HOST_CC', 'cc')
QBE = os.environ.get('QBE') or shutil.which('qbe')


@dataclass
class Case:
    name: str
    units: tuple
    # Per original: symbol -> (width, intrinsic alignment, initialized bytes, public).
    objects: tuple = ()
    references: tuple = ()
    forbidden: tuple = ()


def integer(value, public=True):
    return (4, 4, (value & 0xffffffff).to_bytes(4, 'little'), public)


def fixtures():
    cases = []
    def add(name, text, objects=None, forbidden=()):
        cases.append(Case(name, (text,), (objects or {},), ({},), forbidden))
    def local(name, body, header=''):
        add(name, header+'int main(void) { '+body+' }')
    local('anonymous sequential and duplicate values',
          'enum { ZERO, ONE, AGAIN=ONE, ANSWER=6*7, NEXT, }; '
          'return ZERO==0 && ONE==1 && AGAIN==1 && ANSWER==42 && NEXT==43?42:1;')
    local('negative extrema and no overflow successor',
          'enum E { LOW=-2147483647-1, NEXT, NEG=-1, ZERO, HIGH=2147483647 }; '
          'enum E e=LOW; return e==(-2147483647-1) && NEXT==(-2147483647) && NEG==-1 && ZERO==0 && HIGH==2147483647?42:1;')
    local('enumerator int versus unsigned enum object promotion',
          'enum E { TOP=2147483647 }; enum E e=TOP; '
          'return sizeof e==4 && sizeof TOP==4 && (+e < -1) && !(TOP < -1) && '
          '(e+0 < -1) && ((enum E)0-1 > 0)?42:1;')
    local('negative enum object promotes signed int',
          'enum E { NEG=-1, TOP=2147483647 }; enum E e=NEG; '
          'return +e<0 && e+0<0 && sizeof e==4 && _Alignof(enum E)==4?42:1;')
    local('all zero enum remains unsigned compatible',
          'enum E { ZERO=0 }; enum E e=ZERO; return (+e < -1) && !(ZERO < -1)?42:1;')
    local('earlier constants strict ICE and assertions',
          'enum E { A=6, B=A*7, C=sizeof(int *) }; '
          '_Static_assert(sizeof A==4,"enumerator int"); _Static_assert(B==42,"value"); '
          'int a[B]; a[A]=B; return sizeof a==168 && a[6]==42 && C==8?42:1;')
    local('enumerator controls switch',
          'enum { A=40, B=A+2 }; int x=B; switch(x) {case A:return 1;case B:return 42;default:return 2;}')
    local('skipped arithmetic and opaque sizeof',
          'enum { A=1?42:1/0, B=sizeof(1/0), C=1 || (1,2) }; '
          'return A==42 && B==4 && C==1?42:1;')
    local('tag and ordinary namespaces independent',
          'enum E { E=42 }; enum E x=E; return x;')
    local('nested tag definition shadows and restores',
          'enum E x=A; { enum E { A=7 }; enum E y=A; if(y!=7) return 1; } return x==A?42:2;',
          'enum E { A=42 }; ')
    local('enumerator ordinary object shadow restores',
          'int saved=A; { int A=7; if(A!=7) return 1; } return saved==A?42:2;',
          'enum { A=42 }; ')
    local('inner initializer resolves outer enumerator',
          'enum { A=A+2 }; return A;', 'enum { A=40 }; ')
    local('defining expression sees outer typedef',
          'enum { T=sizeof(T)+38 }; return T;', 'typedef int T; ')
    local('later initializer sees enum mask not outer typedef',
          'enum { T=40, U=T+2 }; return U;', 'typedef int T; ')
    local('for scope restores enumerator',
          'int n=0; for(enum { A=1 } i=A;i<3;i++) n+=i; return A==42 && n==3?42:1;',
          'enum { A=42 }; ')
    local('record member list has enclosing enumerator scope',
          'struct S { enum { A=42 } x; }; struct S s; s.x=A; return s.x;')
    local('typedef enum array pointer function interoperability',
          'E a[2]={A,B}; E (*p)[2]=&a; E (*fp)(E)=identity; '
          'return sizeof a==8 && _Alignof(E[2])==4 && fp((*p)[1])==B?42:1;',
          'typedef enum E { A=40, B=42 } E; E identity(E x) { return x; } ')
    local('same nominal enum pointer redeclarations',
          'enum E e=A; enum E *p=&e; enum E *q=p; return *q;',
          'enum E { A=42 }; enum E *identity(enum E *); enum E *identity(enum E *p) { return p; } ')
    local('qualified enum and unsigned compatible pointers',
          'enum E e=A; const enum E *p=&e; const unsigned int *q=p; return *q;',
          'enum E { A=42 }; ')
    local('signed compatible pointers',
          'enum E e=A; enum E *p=&e; int *q=p; *q=42; return e;', 'enum E { NEG=-1, A=40 }; ')
    local('enum explicit casts and bool conversion',
          'enum E e=(enum E)42; _Bool b=(_Bool)e; return b && (unsigned char)e==42?42:1;',
          'enum E { A=0, B=42 }; ')
    local('unevaluated enum object updates and missing function',
          'enum E e=A; return sizeof(e=B)==4 && sizeof missing()==4 && e==A?42:1;',
          'enum E { A=40, B=42 }; enum E missing(void); ')
    add('enumerator alone has no data',
        'enum E { NO_STORAGE_A=40, NO_STORAGE_B=NO_STORAGE_A+2 }; int main(void) { return NO_STORAGE_B; }',
        forbidden=('NO_STORAGE_A','NO_STORAGE_B','E'))
    add('enum initialized globals byte representations',
        'enum U { A=42 }; enum S { NEG=-1 }; enum U u=A; enum S s=NEG; '
        'enum U zero; static enum S private=NEG; '
        'int main(void) { return u==42 && s==-1 && zero==0 && private==-1?42:1; }',
        {'u':integer(42),'s':integer(-1),'zero':integer(0),'private':integer(-1,False)})
    add('enum constants initialize data and null pointer',
        'enum { ANSWER=42, ZERO=ANSWER-42 }; int value=ANSWER; int *null_slot=ZERO; '
        'int main(void) { return value==42 && null_slot==0?42:1; }',
        {'value':integer(42),'null_slot':(8,8,bytes(8),True)}, forbidden=('ANSWER','ZERO'))
    add('enum constant relocation offset',
        'enum { INDEX=2 }; int values[3]={40,41,42}; int *slot=values+INDEX; '
        'int main(void) { return slot==&values[2] && *slot==42?42:1; }',
        {'values':(12,4,b''.join(n.to_bytes(4,'little') for n in (40,41,42)),True),
         'slot':(8,8,bytes(8),True)}, forbidden=('INDEX',))
    cases[-1].references=({'slot':OffsetReference('object','values',byte_addend=8)},)
    local('record layout and enum array stride',
          'struct S { char c; enum E e; enum E a[2]; }; struct S s; '
          's.e=A; s.a[1]=A; return sizeof s==16 && _Alignof(struct S)==4 && '
          '(char *)&s.e-(char *)&s==4 && '
          '(char *)&s.a[1]-(char *)&s.a[0]==4 && s.e==s.a[1]?42:1;',
          'enum E { A=42 }; ')
    # Enumerator masking from a function definition's parameter scope survives
    # into its body; the enum tag does not leak from a declaration prototype.
    local('definition parameter enumeration remains visible', 'return f(0);',
          'int f(enum P { PARAM_A=42 } x) { return PARAM_A+x; } ')
    local('prototype enumerator does not leak ordinary name',
          'int HIDDEN=42; return HIDDEN;', 'int prototype(enum P { HIDDEN=7 } x); ')
    local('macro enum grammar and exact keywords',
          'enum E e=ANSWER; return e;',
          '#define ENUM enum\n#define VALUE(x) x\nENUM E { ANSWER=VALUE(42), };\n')
    # Each pair is compiled natively, all-KCC, and KCC/native in BOTH directions.
    # Nine mixed args force both integer registers and stack ABI positions.
    for signed in (False,True):
        tag='enum E { NEG=-1, ANSWER=42 }; ' if signed else 'enum E { ZERO=0, ANSWER=42 }; '
        value='NEG' if signed else 'ANSWER'
        params='enum E a,int b,long c,enum E d,unsigned e,long long f,enum E g,int h,enum E i'
        args=f'{value},2,3L,ANSWER,5U,6LL,ANSWER,8,ANSWER'
        checks=f'a=={value} && b==2 && c==3 && d==ANSWER && e==5 && f==6 && g==ANSWER && h==8 && i==ANSWER'
        owner=tag+f'enum E cell={value}; enum E pick({params}) {{ return {checks}?cell:0; }} enum E *address(void) {{ return &cell; }}'
        driver=tag+f'extern enum E cell; enum E pick({params}); enum E *address(void); int main(void) {{ '
        driver+=f'if(pick({args})!={value} || address()!=&cell) return 1; cell=ANSWER; return *address()==ANSWER?42:2; }}'
        cases.append(Case(('signed' if signed else 'unsigned')+' enum multiTU ABI',
                          (owner,driver), ({'cell':integer(-1 if signed else 42)},{}), ({},{})))
    return cases


# GENUINE constraints: syntax/namespace/constant-form/completeness, never UB runs.
CONSTRAINTS = [
    ('standalone completed enum reference', 'enum E { A=42 }; int main(void) { enum E; enum E x=A; return x; }', 'declar'),
    ('unknown enum reference', 'enum Missing *p;', 'enum'),
    ('unknown standalone enum', 'enum Missing;', 'enum'),
    ('own list incomplete enum even through pointer', 'enum E { A=sizeof(enum E *) };', 'enum'),
    ('own list incomplete enum sizeof', 'enum E { A=sizeof(enum E) };', 'enum'),
    ('duplicate enumerator', 'enum { A=1, A=2 };', 'conflict'),
    ('enumerator conflicts ordinary object', 'int A; enum { A=1 };', 'conflict'),
    ('enumerator conflicts typedef', 'typedef int A; enum { A=1 };', 'conflict'),
    ('later object conflicts enumerator', 'enum { A=1 }; int A;', 'conflict'),
    ('later typedef conflicts enumerator', 'enum { A=1 }; typedef int A;', 'conflict'),
    ('function conflicts enumerator', 'enum { A=1 }; int A(void);', 'conflict'),
    ('wrong kind record tag', 'struct E {int x;}; enum E *p;', 'tag'),
    ('wrong kind enum tag', 'enum E { A }; struct E *p;', 'tag'),
    ('forward enumerator value', 'enum { A=B, B=1 };', 'undeclared'),
    ('self enumerator value', 'enum { A=A };', 'undeclared'),
    ('non ICE const object', 'const int x=42; enum { A=x };', 'constant'),
    ('non ICE ordinary call', 'int f(void); enum { A=f() };', 'constant'),
    ('skipped ordinary call not ICE', 'int f(void); enum { A=1||f() };', 'constant'),
    ('skipped ordinary name not ICE', 'int x; enum { A=1?42:x };', 'constant'),
    ('evaluated comma not ICE', 'enum { A=(1,42) };', 'comma'),
    ('write enumerator', 'enum { A=42 }; int f(void) { A=1; return A; }', 'modifiable'),
    ('take enumerator address', 'enum { A=42 }; int *p=&A;', 'lvalue'),
    ('increment enumerator', 'enum { A=42 }; int f(void) { return A++; }', 'modifiable'),
    ('switch duplicate after conversion', 'enum { A=-1 }; int f(unsigned x) {switch(x){case A:return 1;case 4294967295U:return 2;}return 0;}', 'duplicate'),
    ('prototype scope not exported', 'int prototype(enum E { HIDDEN=42 } x); int x=HIDDEN;', 'undeclared'),
    ('inner enumerator not exported', 'int f(void) {{ enum { HIDDEN=42 }; } return HIDDEN;}', 'undeclared'),
    ('empty enum list', 'enum E {};', 'expected'),
    ('missing enum name', 'enum { =1 };', 'expected'),
    ('missing enum value', 'enum { A= };', 'expected'),
    ('missing enum delimiter', 'enum { A=1 B=2 };', 'expected'),
]
# The strict evaluator's invalid arithmetic remains KCC-only; no native UB claim.
INVALID_ARITHMETIC = [
    ('enum { A=1/0 };','division by zero'),
    ('enum { A=2147483647+1 };','signed overflow'),
    ('enum { A=1ULL<<64 };','invalid shift count'),
    ('enum { A=-1<<1 };','negative left operand'),
]
# Valid broader C23 cases; NOT a native constraint-rejection oracle.
DEFERRED = [
    ('enum E : unsigned int { A=42 };', 'M23f'),
    ('enum E { A=2147483648U };', 'M23f'),
    ('enum E { A=2147483647, B };', 'M23f'),
    ('enum E { A=-2147483649LL };', 'M23f'),
]
# Nominal pointer identity is stricter than native warnings: KCC-only checks.
NOMINAL = [
    'enum E { A }; enum F { B }; enum E *f(enum F *p) { return p; }',
    'enum E { A }; enum F { B }; enum E *p; enum F *p;',
]


def fixture_digest(cases):
    value=[{'name':c.name,'units':c.units,'objects':[
        {n:(w,a,b.hex(),p) for n,(w,a,b,p) in unit.items()} for unit in c.objects],
        'references':[{n:vars(r) for n,r in unit.items()} for unit in c.references],
        'forbidden':c.forbidden} for c in cases]
    # Reference.contents is empty for the enum suite. Convert bytes explicitly.
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=lambda b:b.hex()).encode()).hexdigest()


FIXTURE_SHA256 = 'a62376771b4c1512c2f9022baf95123dcd10046cdc43faff12b75c298bf73d8d'


def guarded_fixtures():
    cases=fixtures()
    assert fixture_digest(cases)==FIXTURE_SHA256, 'enum original fixture/version guard changed'
    assert len({c.name for c in cases})==len(cases)
    for c in cases:
        assert len(c.units)==len(c.objects)==len(c.references), c.name
    return cases


def object_evidence(path, objects, references, forbidden=(), il=None):
    elf=OffsetRelocations(path)
    blocks=il_extents(il) if il is not None else None
    for name,(width,alignment,wanted,public) in objects.items():
        s=elf.symbol(name)
        assert 0<s['section']<len(elf.sections), ('not allocated',name,s)
        section=elf.sections[s['section']]
        assert section[1] in (1,8) and section[2]&3==3 and not section[2]&0x404, (name,section)
        assert s['binding']==int(public), (name,s)
        assert s['kind']==(0 if il is not None else 1), (name,s)
        assert s['size']==(0 if il is not None else width), (name,s)
        assert section[8]>=alignment and s['value']%alignment==0, ('alignment',name,s,section)
        assert s['value']+width<=section[5]
        contents=bytes(width) if section[1]==8 else elf.section_bytes(s['section'])[s['value']:s['value']+width]
        assert contents==wanted, ('bytes',name,contents,wanted)
        if blocks is not None:
            assert name in blocks and blocks[name]==(public,alignment,width), (name,blocks)
        relocs=[r for r in elf.relocations if r['section']==s['section'] and s['value']<=r['offset']<s['value']+width]
        if name not in references:
            assert not relocs, ('unexpected scalar/array relocation',name,relocs)
    elf.check(references)
    for name in forbidden:
        assert not [s for s in elf.symbols if s['name']==name], ('enum has storage/reference',name)
    return elf


def selected_compilers():
    hosts=native_compilers(HOST,os.environ.get('CLANG_CC'))
    extra=os.environ.get('GCC13_CC')
    if extra:
        assert shutil.which(extra), ('explicit additional native compiler unavailable',extra)
        if all(os.path.realpath(shutil.which(cc))!=os.path.realpath(shutil.which(extra)) for cc in hosts):hosts.append(extra)
    return hosts


# N3096 removes the C11 for-init declaration restriction. Both legacy GCC
# diagnostics below are capability gaps, not agreements. Exact frozen original,
# target and compiler versions are mandatory; new failures cannot match by keyword.
FOR_GAP_DIAGNOSTICS = ((
    'error', "declaration of non-variable 'A' in 'for' loop initial declaration"),)
FOR_GAP_VERSIONS = ('11.5.0', '13.3.0')


def expected_warnings(name, clang):
    if name in ('definition parameter enumeration remains visible','prototype enumerator does not leak ordinary name'):
        return (('warning', "declaration of 'enum P' will not be visible outside of this function [-Wvisibility]" if clang else
                 "'enum P' declared inside parameter list will not be visible outside of this definition or declaration"),)
    if not clang:return ()
    return {
        'skipped arithmetic and opaque sizeof': (
            ('warning', "use of logical '||' with constant operand [-Wconstant-logical-operand]"),
            ('note', "use '|' for a bitwise operation"),
            ('warning', 'left operand of comma operator has no effect [-Wunused-value]')),
        'unevaluated enum object updates and missing function': (
            ('warning', 'expression with side effects has no effect in an unevaluated context [-Wunevaluated-expression]'),),
        'enum constants initialize data and null pointer': (
            ('warning', "expression which evaluates to zero treated as a null pointer constant of type 'int *' [-Wnon-literal-null-conversion]"),),
    }.get(name,())


def native_object(cc, source, output, case=None):
    if case is not None:
        assert case in guarded_fixtures() and source.read_text() in [u+'\n' for u in case.units], 'native original identity/version guard'
    output.unlink(missing_ok=True)
    args=[cc,'-std=c2x','-pedantic-errors','-fsigned-char','-fno-common','-c',source,'-o',output]
    result=invoke(args)
    records=native_diagnostics(result.stderr,source,source.read_text(),clang_style(cc))
    if result.returncode:
        assert case and case.name=='for scope restores enumerator' and not clang_style(cc), (case.name if case else '',cc,result.stderr)
        assert fixture_digest(fixtures())==FIXTURE_SHA256 and source.read_text()==case.units[0]+'\n', 'native gap source guard'
        version=invoke([cc,'-dumpfullversion','-dumpversion']);target=invoke([cc,'-dumpmachine'])
        assert version.returncode==target.returncode==0 and not version.stderr and not target.stderr
        assert version.stdout.strip() in FOR_GAP_VERSIONS and target.stdout.strip() in ('x86_64-amazon-linux','x86_64-linux-gnu'), (version,target)
        assert records==FOR_GAP_DIAGNOSTICS and not result.stdout and not output.exists(), (cc,records,result.stderr)
        print('ENUM NATIVE GAP (NOT agreement): '+json.dumps(dict(original=case.name,compiler=cc,version=version.stdout.strip())))
        return False
    assert not result.stdout and records==expected_warnings(case.name if case else '',clang_style(cc)), (case.name if case else '',cc,records,result.stderr)
    assert output.is_file() and output.stat().st_size>0, 'native producer missing fresh ELF'
    return True


def kcc_object(source, output, directory, index):
    assert QBE and shutil.which(QBE), 'QBE is REQUIRED for enum acceptance/ABI evidence'
    il=directory/f'k{index}.ssa'; asm=directory/f'k{index}.s'
    il.unlink(missing_ok=True)
    result=invoke([KCC,source])
    assert result.returncode==0 and not result.stderr, (source.read_text()[:700],result.stderr)
    assert result.stdout, ('missing IL for original with main/objects',source)
    il.write_text(result.stdout)
    producer([QBE,'-t','amd64_sysv','-o',asm,il],asm)
    producer([HOST,'-c',asm,'-o',output],output)
    return result.stdout


def reject_kcc(directory, text, message):
    source=directory/'reject.c';source.write_text(text+'\n')
    result=invoke([KCC,source])
    assert result.returncode==1 and not result.stdout and ': error:' in result.stderr, (text,result)
    assert message.lower() in result.stderr.lower(), (text,message,result.stderr)
    return result


def controls(directory):
    harness_self_test(directory)
    compiler_selection_self_test(directory)
    cases=guarded_fixtures();changed=copy.deepcopy(cases);changed[0].units=(changed[0].units[0]+' ',)
    assert fixture_digest(changed)!=FIXTURE_SHA256
    # Corrupt fresh real ELF in memory: all controls must provoke assertions.
    cc=selected_compilers()[0];source=directory/'control.c';obj=directory/'control.o'
    source.write_text('enum { A=42 }; int value=A; int main(void) { return value; }\n')
    native_object(cc,source,obj)
    expected={'value':integer(42)}
    object_evidence(obj,expected,{})
    def must_fail(operation):
        try:operation()
        except AssertionError:return
        raise AssertionError('enum object oracle accepted corrupt evidence')
    must_fail(lambda:object_evidence(obj,{'value':integer(41)},{}))
    must_fail(lambda:object_evidence(obj,{'value':(4,4096,integer(42)[2],True)},{}))
    must_fail(lambda:object_evidence(obj,expected,{},('value',)))
    must_fail(lambda:object_evidence(obj,{'value':integer(42,False)},{}))
    source.write_text('int values[3]={40,41,42}; int *slot=values+2;\n');native_object(cc,source,obj)
    must_fail(lambda:object_evidence(obj,{}, {'slot':OffsetReference('object','values',byte_addend=4)}))
    must_fail(lambda:object_evidence(obj,{}, {'slot':OffsetReference('object','slot',byte_addend=8)}))
    elf=OffsetRelocations(obj); assert elf.symbol('values')['kind']==1
    # A forged gap must not excuse changed originals, unknown versions, missing
    # diagnostics, extraneous stderr, or native acceptance of an invalid source.
    for_case=next(c for c in cases if c.name=='for scope restores enumerator')
    source.write_text(for_case.units[0]+'\n')
    changed=copy.deepcopy(for_case);changed.units=(for_case.units[0]+' ',)
    must_fail(lambda:native_object(cc,source,obj,changed))
    original=for_case.units[0]
    text=(f"{source}:1:42: error: declaration of non-variable 'A' in 'for' loop initial declaration\n"
          f"    1 | {original}\n      |                                          ^~~\n")
    def fake_native(args):
        if '-dumpfullversion' in args:
            return subprocess.CompletedProcess(args,0,'11.5.0\n','')
        if '-dumpmachine' in args:
            return subprocess.CompletedProcess(args,0,'x86_64-amazon-linux\n','')
        return subprocess.CompletedProcess(args,1,'',text)
    module=__name__
    with patch(module+'.invoke',side_effect=fake_native), patch(module+'.clang_style',return_value=False):
        assert native_object('guarded-gcc',source,obj,for_case) is False
        for malformed in ('',text+'unreviewed tool failure\n',text.replace('error:','warning:')):
            def bad_native(args,diagnostic=malformed):
                if '-dumpfullversion' in args or '-dumpmachine' in args:return fake_native(args)
                return subprocess.CompletedProcess(args,1,'',diagnostic)
            with patch(module+'.invoke',side_effect=bad_native):
                must_fail(lambda:native_object('guarded-gcc',source,obj,for_case))
    # Exact-reason constraint control: wrong reason/extra output/status cannot
    # earn native agreement merely because a compiler returned an error.
    constraint_name='unknown enum reference'
    constraint_text=next(text for name,text,_ in CONSTRAINTS if name==constraint_name)
    source.write_text(constraint_text+'\n')
    reason=NATIVE_CONSTRAINT_ERRORS['gcc11'][constraint_name]['records']
    full=''.join(f'{source}:1:1: {kind}: {message}\n' for kind,message in reason)
    good=subprocess.CompletedProcess([],1,'',full)
    with patch(module+'.native_constraint_identity',return_value='gcc11'), patch(module+'.clang_style',return_value=False):
        with patch(module+'.invoke',return_value=good):
            assert native_constraint('guarded-gcc',source,constraint_name)
        for mutation in ('status','stdout','reason','extra','newline','source'):
            bad=copy.copy(good)
            if mutation=='status':bad.returncode=2
            elif mutation=='stdout':bad.stdout='unexpected output'
            elif mutation=='reason':bad.stderr=full.replace(reason[0][1],'unsupported compiler feature')
            elif mutation=='extra':bad.stderr+=f'{source}:1:1: note: unrelated note\n'
            elif mutation=='newline':bad.stderr=full.rstrip('\n')
            else:source.write_text(constraint_text+' \n')
            with patch(module+'.invoke',return_value=bad):
                must_fail(lambda:native_constraint('guarded-gcc',source,constraint_name))
            source.write_text(constraint_text+'\n')
    # Unknown versions/targets must fail closed before any constraint credit.
    def unreviewed(args):
        if '-dumpmachine' in args:return subprocess.CompletedProcess(args,0,'x86_64-linux-gnu\n','')
        return subprocess.CompletedProcess(args,0,'99.0.0\n','')
    with patch(module+'.invoke',side_effect=unreviewed), patch(module+'.clang_style',return_value=False):
        must_fail(lambda:native_constraint_identity('unreviewed-gcc'))
    # The freeze gate itself is adversarially checked without making commits,
    # editing a real checkout, or running a forged compiler as acceptance.
    checkout=directory/'binding-checkout'
    (checkout/'src').mkdir(parents=True);(checkout/'build').mkdir()
    source_file=checkout/'src'/'unit.c';source_file.write_text('int x;\n')
    binary=checkout/'build'/'kcc';binary.write_bytes(b'not executed')
    os.utime(source_file,ns=(10_000_000,10_000_000));os.utime(binary,ns=(20_000_000,20_000_000))
    frozen='1'*40
    def fake_git(args):
        if 'rev-parse' in args:return subprocess.CompletedProcess(args,0,frozen+'\n','')
        assert 'status' in args
        return subprocess.CompletedProcess(args,0,'','')
    with patch(module+'.KCC',binary), patch.dict(os.environ,{'KCC_SOURCE':str(checkout)}), patch(module+'.invoke',side_effect=fake_git):
        digest,before=source_binding(frozen);assert digest()==before
        must_fail(lambda:source_binding('2'*40))
        os.utime(binary,ns=(1,1));must_fail(lambda:source_binding(frozen))
        os.utime(binary,ns=(20_000_000,20_000_000))
        source_file.write_text('int changed;\n');assert digest()!=before
        os.utime(source_file,ns=(10_000_000,10_000_000))
        digest,before=source_binding(frozen)
        binary.write_bytes(b'swapped compiler');assert digest()!=before


def resource_cases():
    # Use only five external declarations; no unrelated external/local limit masks
    # the enumerator 4096/TU and 1024/definition boundaries.
    def definition(group,count):return 'enum E%d {'%group+','.join('V%d_%d=%d'%(group,i,i) for i in range(count))+'};'
    yield ('members at bound',definition(0,1024),True,'')
    yield ('members beyond bound',definition(0,1025),False,'enumerator')
    yield ('TU enumerators at bound',''.join(definition(i,1024) for i in range(4)),True,'')
    yield ('TU enumerators beyond bound',''.join(definition(i,1024) for i in range(4))+definition(4,1),False,'enumerator')
    # Nested enum definitions via pointer sizeof permit complete outer expression
    # types without referring to incomplete enum tags; each level adds a type query.
    # Existing type-query depth can bind before enum nesting; assert bounded error
    # rather than wrongly attributing it to the enum-only budget.
    text='42'
    for i in range(66):text='sizeof(enum N%d { C%d=%s } *)'%(i,i,text)
    yield ('nested definitions bounded','enum Root { R='+text+' };',False,'limit')


def source_binding(frozen_hash):
    """Fail closed on wrong checkout, dirty compiler, stale/swapped binary."""
    assert frozen_hash and re.fullmatch(r'[0-9a-f]{40}',frozen_hash), 'exact --frozen-hash required'
    checkout=Path(os.environ.get('KCC_SOURCE',KCC.resolve().parent.parent)).resolve()
    assert KCC.is_file() and KCC.resolve().is_relative_to(checkout/'build'), 'KCC must be built inside frozen checkout/build'
    head=invoke(['git','-C',checkout,'rev-parse','HEAD'])
    assert head.returncode==0 and not head.stderr and head.stdout.strip()==frozen_hash, ('wrong frozen HEAD',head)
    dirty=invoke(['git','-C',checkout,'status','--porcelain','--','src'])
    assert dirty.returncode==0 and not dirty.stderr and not dirty.stdout, ('dirty production compiler sources',dirty)
    sources=sorted((checkout/'src').glob('*.[ch]'))
    assert sources and KCC.stat().st_mtime_ns>=max(p.stat().st_mtime_ns for p in sources), 'stale KCC binary predates compiler sources'
    def digest():
        h=hashlib.sha256()
        for p in sources:
            h.update(p.name.encode()+b'\0'+p.read_bytes()+b'\0')
        return (h.hexdigest(),hashlib.sha256(KCC.read_bytes()).hexdigest())
    return digest, digest()


# Independently observed immutable full native constraint reasons, never learned
# at test runtime. Original bytes and exact version/target identities are guarded.
CONSTRAINT_SOURCE_SHA256 = {'standalone completed enum reference': '2c04548fe98c81e68d8ebfb2847d5ef599616fcd737f3b725df9eba9f2245ecd',
 'unknown enum reference': 'd5d5fb8d490fe803834265b241a76e1cfa84514fdf0162988bddf05e6600d202',
 'unknown standalone enum': '869e5531502ef3df4c153dfc2fae6784582869d69732ad81127911e443f91f9f',
 'own list incomplete enum even through pointer': '2b84d15793fe1b438914c4e969cded60793ffb42dc3e8924ae481c896cb85974',
 'own list incomplete enum sizeof': '3c2df767da807594b89c5526d97d0e312f408b00e0af82ac84b86821a533ac75',
 'duplicate enumerator': 'ceabd36d7edcfdaa44c8e44388b09120d0e511eb5b163d299c0dc0bebfbbea3a',
 'enumerator conflicts ordinary object': '4a84ecd452ac040a6750f8f5a8f29e5df01fa39d559eba13b0394a6460be896b',
 'enumerator conflicts typedef': '6487819bd6b29056f131b0cc5ee9754ec0da7bdecc2dd7418ed7ad42884b63dd',
 'later object conflicts enumerator': '756342e033f0dc24edf5d0b53c1fa1bb5703ddba70c87a5a681ede6a942b6a09',
 'later typedef conflicts enumerator': '27bd516778326e2e6bd2cde035042dac35f34ac5b93513337c71f96d1f973f5d',
 'function conflicts enumerator': '931f8b772f371e6d2012120b464105d4afed6628e62fc8e578c5aea9a6de437e',
 'wrong kind record tag': '4c147a2fef883bd70536fc909746a0a30c8f983b1b9decb595e8a878b5e02067',
 'wrong kind enum tag': 'a8a2243bd7ceb3f5ace69eb1267c92f569c2716111bd5dffdadf3b9b50fa4256',
 'forward enumerator value': 'd999170904d7795dccef0447b596469544705850e6a6802525f18c6fdb17fdf1',
 'self enumerator value': '07ad8ca92b6546da1270c5265a41c3a7d0760076d250c11155415b543204c836',
 'non ICE const object': 'a187f3bc4dbfb8c9d059b85f5c1d8f69d0ad53cdb02deb629bf104d02b8508c9',
 'non ICE ordinary call': '6119c76d24fb34a91eb63e6d53054378bf11611472979f0c94012e6c5927c2b0',
 'skipped ordinary call not ICE': 'f6e9039c25b687e2219091794e4f99bce5db9249ece5ff3e42f0d87d9e98d4da',
 'skipped ordinary name not ICE': '92e56d693b4b60f65726f03994eeee2973e2a42f82f27ab9e83407a1d223a5ce',
 'evaluated comma not ICE': 'acee37a93544d05c8f46b99955bb30e8c361f87e5e6a60014c3bbdbae44fb585',
 'write enumerator': 'dc89ffd55705c4a4ef0ecdba80facf9424a4e0a0a23fcd81df5f6c4df6f7270e',
 'take enumerator address': 'e59d212e368b65913c5b1a38a7831d97648fa0bff0252586554748807f3e0218',
 'increment enumerator': '6b39848f8512097e8dd651104d7459bf84071953b62a02ab03919c8180e23835',
 'switch duplicate after conversion': 'ace1806706e0d802c3728c298c16290a9defcde388f2c7e89d78a1ae567b2ac7',
 'prototype scope not exported': '386bee734f436ec1285d5069660d9ddc22df6b66cfca916ecd5d274c093d139a',
 'inner enumerator not exported': '31172cb6a0b797b7da11a0ca12cb70bff599ea876e9d427167d28709890b0c05',
 'empty enum list': '5e9a9b63db58b26b664701144fc83a647fa3228e49949d3b45db96e39fab7721',
 'missing enum name': 'dd486dd7bdece806da18d8214ef221a223fae30810fb96371a072c30977194e8',
 'missing enum value': '07e579032d5e27d97dc2b83db1ddf62a80ae8d9c61932b6969f87e1558482bb6',
 'missing enum delimiter': '004846c03f63b53dda9e2e72df8f9690478422bf77a9de142d46de6efb4479fc'}

NATIVE_CONSTRAINT_ERRORS = {'gcc11': {'standalone completed enum reference': {'records': [['error',
                                                                'ISO C forbids forward references '
                                                                "to 'enum' types [-Wpedantic]"],
                                                               ['error',
                                                                "variable 'x' has initializer but "
                                                                'incomplete type'],
                                                               ['error',
                                                                "storage size of 'x' isn't "
                                                                'known']]},
           'unknown enum reference': {'records': [['error',
                                                   "ISO C forbids forward references to 'enum' "
                                                   'types [-Wpedantic]']]},
           'unknown standalone enum': {'records': [['error',
                                                    "ISO C forbids forward references to 'enum' "
                                                    'types [-Wpedantic]']]},
           'own list incomplete enum even through pointer': {'records': [['error',
                                                                          'ISO C forbids forward '
                                                                          "references to 'enum' "
                                                                          'types [-Wpedantic]']]},
           'own list incomplete enum sizeof': {'records': [['error',
                                                            'ISO C forbids forward references to '
                                                            "'enum' types [-Wpedantic]"],
                                                           ['error',
                                                            "invalid application of 'sizeof' to "
                                                            "incomplete type 'enum E'"]]},
           'duplicate enumerator': {'records': [['error', "redeclaration of enumerator 'A'"],
                                                ['note',
                                                 "previous definition of 'A' with type 'int'"]]},
           'enumerator conflicts ordinary object': {'records': [['error',
                                                                 "'A' redeclared as different kind "
                                                                 'of symbol'],
                                                                ['note',
                                                                 "previous declaration of 'A' with "
                                                                 "type 'int'"]]},
           'enumerator conflicts typedef': {'records': [['error',
                                                         "'A' redeclared as different kind of "
                                                         'symbol'],
                                                        ['note',
                                                         "previous declaration of 'A' with type "
                                                         "'A' {aka 'int'}"]]},
           'later object conflicts enumerator': {'records': [['error',
                                                              "'A' redeclared as different kind of "
                                                              'symbol'],
                                                             ['note',
                                                              "previous definition of 'A' with "
                                                              "type 'enum <anonymous>'"]]},
           'later typedef conflicts enumerator': {'records': [['error',
                                                               "'A' redeclared as different kind "
                                                               'of symbol'],
                                                              ['note',
                                                               "previous definition of 'A' with "
                                                               "type 'enum <anonymous>'"]]},
           'function conflicts enumerator': {'records': [['error',
                                                          "'A' redeclared as different kind of "
                                                          'symbol'],
                                                         ['note',
                                                          "previous definition of 'A' with type "
                                                          "'enum <anonymous>'"]]},
           'wrong kind record tag': {'records': [['error', "'E' defined as wrong kind of tag"],
                                                 ['error',
                                                  "ISO C forbids forward references to 'enum' "
                                                  'types [-Wpedantic]']]},
           'wrong kind enum tag': {'records': [['error', "'E' defined as wrong kind of tag"]]},
           'forward enumerator value': {'records': [['error',
                                                     "'B' undeclared here (not in a function)"]]},
           'self enumerator value': {'records': [['error',
                                                  "'A' undeclared here (not in a function)"]]},
           'non ICE const object': {'records': [['error',
                                                 "enumerator value for 'A' is not an integer "
                                                 'constant']]},
           'non ICE ordinary call': {'records': [['error',
                                                  "enumerator value for 'A' is not an integer "
                                                  'constant']]},
           'skipped ordinary call not ICE': {'records': [['error',
                                                          "enumerator value for 'A' is not an "
                                                          'integer constant expression '
                                                          '[-Wpedantic]']]},
           'skipped ordinary name not ICE': {'records': [['error',
                                                          "enumerator value for 'A' is not an "
                                                          'integer constant expression '
                                                          '[-Wpedantic]']]},
           'evaluated comma not ICE': {'records': [['error',
                                                    "enumerator value for 'A' is not an integer "
                                                    'constant']]},
           'write enumerator': {'records': [['error',
                                             'lvalue required as left operand of assignment']]},
           'take enumerator address': {'records': [['error',
                                                    "lvalue required as unary '&' operand"]]},
           'increment enumerator': {'records': [['error', 'lvalue required as increment operand']]},
           'switch duplicate after conversion': {'records': [['error', 'duplicate case value'],
                                                             ['note', 'previously used here']]},
           'prototype scope not exported': {'records': [['warning',
                                                         "'enum E' declared inside parameter list "
                                                         'will not be visible outside of this '
                                                         'definition or declaration'],
                                                        ['error',
                                                         "'HIDDEN' undeclared here (not in a "
                                                         'function)']]},
           'inner enumerator not exported': {'records': [['error',
                                                          "'HIDDEN' undeclared (first use in this "
                                                          'function)'],
                                                         ['note',
                                                          'each undeclared identifier is reported '
                                                          'only once for each function it appears '
                                                          'in']]},
           'empty enum list': {'records': [['error', 'empty enum is invalid']]},
           'missing enum name': {'records': [['error', "expected identifier before '=' token"]]},
           'missing enum value': {'records': [['error', "expected expression before '}' token"]]},
           'missing enum delimiter': {'records': [['error', "expected ',' or '}' before 'B'"]]}},
 'gcc13': {'standalone completed enum reference': {'records': [['error',
                                                                "empty declaration of 'enum' type "
                                                                'does not redeclare tag '
                                                                '[-Wpedantic]']]},
           'unknown enum reference': {'records': [['error',
                                                   "ISO C forbids forward references to 'enum' "
                                                   'types [-Wpedantic]']]},
           'unknown standalone enum': {'records': [['error',
                                                    "ISO C forbids forward references to 'enum' "
                                                    'types [-Wpedantic]']]},
           'own list incomplete enum even through pointer': {'records': [['error',
                                                                          'ISO C forbids forward '
                                                                          "references to 'enum' "
                                                                          'types [-Wpedantic]']]},
           'own list incomplete enum sizeof': {'records': [['error',
                                                            'ISO C forbids forward references to '
                                                            "'enum' types [-Wpedantic]"],
                                                           ['error',
                                                            "invalid application of 'sizeof' to "
                                                            "incomplete type 'enum E'"]]},
           'duplicate enumerator': {'records': [['error', "redeclaration of enumerator 'A'"],
                                                ['note',
                                                 "previous definition of 'A' with type 'int'"]]},
           'enumerator conflicts ordinary object': {'records': [['error',
                                                                 "'A' redeclared as different kind "
                                                                 'of symbol'],
                                                                ['note',
                                                                 "previous declaration of 'A' with "
                                                                 "type 'int'"]]},
           'enumerator conflicts typedef': {'records': [['error',
                                                         "'A' redeclared as different kind of "
                                                         'symbol'],
                                                        ['note',
                                                         "previous declaration of 'A' with type "
                                                         "'A' {aka 'int'}"]]},
           'later object conflicts enumerator': {'records': [['error',
                                                              "'A' redeclared as different kind of "
                                                              'symbol'],
                                                             ['note',
                                                              "previous definition of 'A' with "
                                                              "type 'enum <anonymous>'"]]},
           'later typedef conflicts enumerator': {'records': [['error',
                                                               "'A' redeclared as different kind "
                                                               'of symbol'],
                                                              ['note',
                                                               "previous definition of 'A' with "
                                                               "type 'enum <anonymous>'"]]},
           'function conflicts enumerator': {'records': [['error',
                                                          "'A' redeclared as different kind of "
                                                          'symbol'],
                                                         ['note',
                                                          "previous definition of 'A' with type "
                                                          "'enum <anonymous>'"]]},
           'wrong kind record tag': {'records': [['error', "'E' defined as wrong kind of tag"],
                                                 ['error',
                                                  "ISO C forbids forward references to 'enum' "
                                                  'types [-Wpedantic]']]},
           'wrong kind enum tag': {'records': [['error', "'E' defined as wrong kind of tag"]]},
           'forward enumerator value': {'records': [['error',
                                                     "'B' undeclared here (not in a function)"]]},
           'self enumerator value': {'records': [['error',
                                                  "'A' undeclared here (not in a function)"]]},
           'non ICE const object': {'records': [['error',
                                                 "enumerator value for 'A' is not an integer "
                                                 'constant']]},
           'non ICE ordinary call': {'records': [['error',
                                                  "enumerator value for 'A' is not an integer "
                                                  'constant']]},
           'skipped ordinary call not ICE': {'records': [['error',
                                                          "enumerator value for 'A' is not an "
                                                          'integer constant expression '
                                                          '[-Wpedantic]']]},
           'skipped ordinary name not ICE': {'records': [['error',
                                                          "enumerator value for 'A' is not an "
                                                          'integer constant expression '
                                                          '[-Wpedantic]']]},
           'evaluated comma not ICE': {'records': [['error',
                                                    "enumerator value for 'A' is not an integer "
                                                    'constant']]},
           'write enumerator': {'records': [['error',
                                             'lvalue required as left operand of assignment']]},
           'take enumerator address': {'records': [['error',
                                                    "lvalue required as unary '&' operand"]]},
           'increment enumerator': {'records': [['error', 'lvalue required as increment operand']]},
           'switch duplicate after conversion': {'records': [['error', 'duplicate case value'],
                                                             ['note', 'previously used here']]},
           'prototype scope not exported': {'records': [['warning',
                                                         "'enum E' declared inside parameter list "
                                                         'will not be visible outside of this '
                                                         'definition or declaration'],
                                                        ['error',
                                                         "'HIDDEN' undeclared here (not in a "
                                                         'function)']]},
           'inner enumerator not exported': {'records': [['error',
                                                          "'HIDDEN' undeclared (first use in this "
                                                          'function)'],
                                                         ['note',
                                                          'each undeclared identifier is reported '
                                                          'only once for each function it appears '
                                                          'in']]},
           'empty enum list': {'records': [['error', 'empty enum is invalid']]},
           'missing enum name': {'records': [['error', "expected identifier before '=' token"]]},
           'missing enum value': {'records': [['error', "expected expression before '}' token"]]},
           'missing enum delimiter': {'records': [['error', "expected ',' or '}' before 'B'"]]}},
 'clang18': {'standalone completed enum reference': {'records': [['error',
                                                                  'ISO C forbids forward '
                                                                  "references to 'enum' types "
                                                                  '[-Werror,-Wpedantic]'],
                                                                 ['error',
                                                                  'variable has incomplete type '
                                                                  "'enum E'"],
                                                                 ['note',
                                                                  "forward declaration of 'enum "
                                                                  "E'"]]},
             'unknown enum reference': {'records': [['error',
                                                     "ISO C forbids forward references to 'enum' "
                                                     'types [-Werror,-Wpedantic]']]},
             'unknown standalone enum': {'records': [['error',
                                                      "ISO C forbids forward references to 'enum' "
                                                      'types [-Werror,-Wpedantic]']]},
             'own list incomplete enum even through pointer': {'accepted_disagreement': True},
             'own list incomplete enum sizeof': {'records': [['error',
                                                              "invalid application of 'sizeof' to "
                                                              "an incomplete type 'enum E'"],
                                                             ['note',
                                                              "definition of 'enum E' is not "
                                                              "complete until the closing '}'"]]},
             'duplicate enumerator': {'records': [['error', "redefinition of enumerator 'A'"],
                                                  ['note', 'previous definition is here']]},
             'enumerator conflicts ordinary object': {'records': [['error', "redefinition of 'A'"],
                                                                  ['note',
                                                                   'previous definition is here']]},
             'enumerator conflicts typedef': {'records': [['error', "redefinition of 'A'"],
                                                          ['note', 'previous definition is here']]},
             'later object conflicts enumerator': {'records': [['error',
                                                                "redefinition of 'A' as different "
                                                                'kind of symbol'],
                                                               ['note',
                                                                'previous definition is here']]},
             'later typedef conflicts enumerator': {'records': [['error',
                                                                 "redefinition of 'A' as different "
                                                                 'kind of symbol'],
                                                                ['note',
                                                                 'previous definition is here']]},
             'function conflicts enumerator': {'records': [['error',
                                                            "redefinition of 'A' as different kind "
                                                            'of symbol'],
                                                           ['note',
                                                            'previous definition is here']]},
             'wrong kind record tag': {'records': [['error',
                                                    "use of 'E' with tag type that does not match "
                                                    'previous declaration'],
                                                   ['note', 'previous use is here']]},
             'wrong kind enum tag': {'records': [['error',
                                                  "use of 'E' with tag type that does not match "
                                                  'previous declaration'],
                                                 ['note', 'previous use is here']]},
             'forward enumerator value': {'records': [['error',
                                                       "use of undeclared identifier 'B'"]]},
             'self enumerator value': {'records': [['error', "use of undeclared identifier 'A'"]]},
             'non ICE const object': {'records': [['error',
                                                   'expression is not an integer constant '
                                                   'expression; folding it to a constant is a GNU '
                                                   'extension [-Werror,-Wgnu-folding-constant]']]},
             'non ICE ordinary call': {'records': [['error',
                                                    'expression is not an integer constant '
                                                    'expression']]},
             'skipped ordinary call not ICE': {'records': [['error',
                                                            'expression is not an integer constant '
                                                            'expression; folding it to a constant '
                                                            'is a GNU extension '
                                                            '[-Werror,-Wgnu-folding-constant]']]},
             'skipped ordinary name not ICE': {'records': [['error',
                                                            'expression is not an integer constant '
                                                            'expression; folding it to a constant '
                                                            'is a GNU extension '
                                                            '[-Werror,-Wgnu-folding-constant]']]},
             'evaluated comma not ICE': {'records': [['warning',
                                                      'left operand of comma operator has no '
                                                      'effect [-Wunused-value]'],
                                                     ['error',
                                                      'expression is not an integer constant '
                                                      'expression; folding it to a constant is a '
                                                      'GNU extension '
                                                      '[-Werror,-Wgnu-folding-constant]']]},
             'write enumerator': {'records': [['error', 'expression is not assignable']]},
             'take enumerator address': {'records': [['error',
                                                      'cannot take the address of an rvalue of '
                                                      "type 'int'"]]},
             'increment enumerator': {'records': [['error', 'expression is not assignable']]},
             'switch duplicate after conversion': {'records': [['error',
                                                                "duplicate case value: 'A' and "
                                                                "'4294967295' both equal "
                                                                "'4294967295'"],
                                                               ['note',
                                                                'previous case defined here']]},
             'prototype scope not exported': {'records': [['warning',
                                                           "declaration of 'enum E' will not be "
                                                           'visible outside of this function '
                                                           '[-Wvisibility]'],
                                                          ['error',
                                                           'use of undeclared identifier '
                                                           "'HIDDEN'"]]},
             'inner enumerator not exported': {'records': [['error',
                                                            'use of undeclared identifier '
                                                            "'HIDDEN'"]]},
             'empty enum list': {'records': [['error', 'use of empty enum']]},
             'missing enum name': {'records': [['error', 'expected identifier']]},
             'missing enum value': {'records': [['error', 'expected expression']]},
             'missing enum delimiter': {'full_stream': "{source}:1:11: error: missing ',' between "
                                                       'enumerators\n'
                                                       '    1 | enum { A=1 B=2 };\n'
                                                       '      |           ^\n'
                                                       '      |           , \n'
                                                       '1 error generated.\n'}}}

def native_constraint_identity(cc):
    target=invoke([cc,'-dumpmachine'])
    assert target.returncode==0 and not target.stderr and target.stdout.endswith('\n'), ('native target',cc,target)
    if clang_style(cc):
        version=invoke([cc,'-dumpversion']); banner=invoke([cc,'--version'])
        assert version.returncode==banner.returncode==0 and not version.stderr and not banner.stderr
        identity=(version.stdout.strip(),target.stdout.strip(),banner.stdout.splitlines()[0])
        assert identity in (
            ('18.1.8','x86_64-amazon-linux-gnu','clang version 18.1.8 (AWS 18.1.8-6.amzn2023.0.3)'),
            ('18.1.3','x86_64-pc-linux-gnu','Ubuntu clang version 18.1.3 (1ubuntu1)'),
        ), ('unreviewed native constraint identity',cc,identity)
        return 'clang18'
    version=invoke([cc,'-dumpfullversion','-dumpversion'])
    assert version.returncode==0 and not version.stderr and version.stdout.endswith('\n')
    identity=(version.stdout.strip(),target.stdout.strip())
    allowed={('11.5.0','x86_64-amazon-linux'):'gcc11',('13.3.0','x86_64-linux-gnu'):'gcc13'}
    assert identity in allowed, ('unreviewed native constraint identity',cc,identity)
    return allowed[identity]


def native_constraint(cc, source, name):
    """Exact original, version, status and complete reason stream; no any-error credit."""
    assert name in CONSTRAINT_SOURCE_SHA256
    assert hashlib.sha256(source.read_bytes()).hexdigest()==CONSTRAINT_SOURCE_SHA256[name], ('changed constraint original',name)
    family=native_constraint_identity(cc)
    expected=NATIVE_CONSTRAINT_ERRORS[family][name]
    result=invoke([cc,'-std=c2x','-pedantic-errors','-fsyntax-only',source])
    assert not result.stdout, (name,cc,'unexpected native stdout',result)
    if expected.get('accepted_disagreement'):
        assert name=='own list incomplete enum even through pointer' and family=='clang18'
        assert result.returncode==0 and not result.stderr, (name,cc,'changed known acceptance disagreement',result)
        print('ENUM NATIVE CONSTRAINT DISAGREEMENT (NOT agreement): '+json.dumps(dict(original=name,compiler=cc)))
        return False
    assert result.returncode==1, (name,cc,'wrong native constraint exit',result)
    if 'full_stream' in expected:
        assert result.stderr==expected['full_stream'].replace('{source}',str(source)), (name,cc,result.stderr)
    else:
        records=native_diagnostics(result.stderr,source,source.read_text(),clang_style(cc))
        assert records==tuple(tuple(r) for r in expected['records']), (name,cc,records,expected)
    if name=='standalone completed enum reference' and family!='gcc13':
        # GCC11/Clang invent a shadow incomplete tag instead of diagnosing the
        # actual C23 empty declaration. Rejection is observed, but its reason
        # disagrees: never count this as correct-reason constraint agreement.
        print('ENUM NATIVE CONSTRAINT REASON DISAGREEMENT (NOT agreement): '+json.dumps(dict(original=name,compiler=cc)))
        return False
    return True


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--native-only',action='store_true')
    parser.add_argument('--harness-self-test',action='store_true')
    parser.add_argument('--frozen-hash')
    args=parser.parse_args()
    binding=None
    if not args.native_only and not args.harness_self_test:
        binding=source_binding(args.frozen_hash)
    cases=guarded_fixtures();compilers=selected_compilers()
    counts=dict(originals=len(cases),native_program_runs=0,kcc_program_runs=0,mixed_abi_runs=0,native_constraint_rejections=0,native_constraint_disagreements=0,kcc_rejections=0,resource_checks=0,native_gaps=0,unresolved_native_originals=[])
    with tempfile.TemporaryDirectory(prefix='kcc independent enum ') as name:
        directory=Path(name)
        if args.harness_self_test:
            controls(directory);print('enum harness self-tests PASS (not KCC acceptance)');return
        if not args.native_only:
            assert KCC.is_file() and QBE and shutil.which(QBE), ('required KCC/QBE unavailable',KCC,QBE)
        for number,case in enumerate(cases):
            work=directory/str(number);work.mkdir()
            sources=[];generated=[]
            for i,text in enumerate(case.units):
                source=work/f'original{i}.c';source.write_text(text+'\n');sources.append(source)
                if not args.native_only:
                    obj=work/f'k{i}.o';il=kcc_object(source,obj,work,i)
                    object_evidence(obj,case.objects[i],case.references[i],case.forbidden,il)
                    generated.append(obj)
            if generated:
                run_program(HOST,generated,work/'all-kcc');counts['kcc_program_runs']+=1
            native_runs_before=counts['native_program_runs']
            for lane,cc in enumerate(compilers):
                native=[]
                for i,source in enumerate(sources):
                    obj=work/f'h{lane}-{i}.o'
                    if not native_object(cc,source,obj,case):
                        counts['native_gaps']+=1;break
                    object_evidence(obj,case.objects[i],case.references[i],case.forbidden)
                    native.append(obj)
                if len(native)!=len(sources):continue
                run_program(cc,native,work/f'all-native{lane}');counts['native_program_runs']+=1
                if generated and len(native)>1:
                    for i in range(len(native)):
                        mixed=native.copy();mixed[i]=generated[i]
                        run_program(cc,mixed,work/f'mixed{lane}-{i}');counts['mixed_abi_runs']+=1
            if counts['native_program_runs']==native_runs_before:counts['unresolved_native_originals'].append(case.name)
        for name,text,message in CONSTRAINTS:
            if not args.native_only:
                reject_kcc(directory,text,message);counts['kcc_rejections']+=1
            source=directory/'constraint.c';source.write_text(text+'\n')
            for cc in compilers:
                agreement=native_constraint(cc,source,name)
                counts['native_constraint_rejections' if agreement else 'native_constraint_disagreements']+=1
        if not args.native_only:
            for text,message in INVALID_ARITHMETIC+DEFERRED:
                reject_kcc(directory,text,message);counts['kcc_rejections']+=1
            for text in NOMINAL:
                reject_kcc(directory,text,'incompatible');counts['kcc_rejections']+=1
            for name,text,success,message in resource_cases():
                if success:
                    source=directory/'resource.c';source.write_text(text+'\n');result=invoke([KCC,source])
                    assert result.returncode==0 and not result.stderr and not result.stdout, (name,result.stderr,result.stdout[:200])
                else:reject_kcc(directory,text,message)
                counts['resource_checks']+=1
        if binding:
            digest,initial=binding
            assert digest()==initial, 'compiler sources/binary changed during production test'
            print('Frozen enum production hash: '+args.frozen_hash)
        print(('NATIVE-ONLY enum evidence (NOT KCC PASS): ' if args.native_only else 'M18 enum evidence: ')+json.dumps(counts,sort_keys=True))


if __name__=='__main__':main()

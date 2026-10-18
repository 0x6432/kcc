"""Independent M15 block storage/linkage release gates (test-only).

KCC=... QBE=... CLANG_CC=... python3 tests/test_block_storage.py
--native-only executes the SAME curated, defined original translation units;
never rewrites a source for a compiler and never claims KCC coverage.
Constraints, valid-but-deferred subset forms and UB refusals are separate,
compile-only inventories. Native acceptance is NOT evidence for UB or a subset
refusal. All producers require fresh nonempty artifacts and exact diagnostics.
The AST companion is built separately with compiler sources excluding main.c.
"""
import argparse
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import shutil
import tempfile

from test_integer_initializers import (
    KCC, HOST, QBE, invoke, producer, clang_style, elf_objects, run_program,
    features_for, harness_self_test, reject, native_diagnostics,
)
from test_null_initializers import native_compilers, compiler_selection_self_test
from test_direct_address_initializers import Reference, ElfRelocations


# Exact unchanged originals only. GCC13 supports typeof but still diagnoses
# register-array decay inside this unevaluated query (GCC11 takes the separate
# keyword-gap path). Neither rejection is a native runtime agreement.
REGISTER_ARRAY_DIVERGENCES = {
    'int main(void) { register int a[2]; return sizeof(a[0])==4?42:1; }': {
        'gcc': (('error', "ISO C forbids subscripting 'register' array [-Wpedantic]"),),
        'clang': (('error', 'address of register variable requested'),),
    },
    'int main(void) { register int a[2]; typeof(a+0) p=0; return p==0?42:1; }': {
        'gcc': (('error', "address of register variable 'a' requested"),),
        'clang': (('error', 'address of register variable requested'),),
    },
}


@dataclass(frozen=True)
class Storage:
    stem: str
    width: int = 4
    bits: int = 0
    alignment: int = 4
    reference: object = None
    zero: bool = False
    public: bool = True


@dataclass
class Case:
    name: str
    owner: str
    companion: str = ''
    locals: tuple = ()
    globals: dict = field(default_factory=dict)
    features: tuple = ()
    # Second unchanged KCC-owned TU: tests genuinely independent local linkage.
    peer: str = ''
    peer_locals: tuple = ()
    native_gaps: dict = field(default_factory=dict)


def fixtures():
    cases = []
    def add(name, owner, companion='', locals=(), globals=None, features=(), peer='', peer_locals=()):
        cases.append(Case(name, owner, companion, tuple(locals), globals or {}, features, peer, tuple(peer_locals)))
    driver = 'int inspect(void); int main(void) { return inspect(); }'
    add('extern first introduced in block',
        'int inspect(void) { extern int target; return target; }',
        'int target=42; '+driver)
    add('extern mutable object address identity',
        'int *slot(void) { extern int target; return &target; } '
        'int inspect(void) { extern int target; target+=2; return target; }',
        'int target=40; int *slot(void); int inspect(void); int main(void) { '
        'return slot()==&target && inspect()==42 && target==42?42:1; }')
    add('block extern no tentative ownership',
        'int inspect(void) { extern int absent; return sizeof absent==4?42:1; }', driver)
    add('parameter then nested extern hides parameter',
        'int inspect(int target) { if(target!=2) return 1; '
        '{ extern int target; if(target!=42) return 2; } return target==2?42:3; }',
        'int target=42; int inspect(int); int main(void) { return inspect(2); }')
    add('automatic then nested extern restores automatic',
        'int inspect(void) { int target=2; { extern int target; if(target!=42) return 1; '
        '{ int target=3; if(target!=3) return 2; } if(target!=42) return 3; } return target==2?42:4; }',
        'int target=42; '+driver)
    add('extern same-scope repeated and declaration list',
        'int inspect(void) { extern int target,other,*pointer; extern int target; '
        'return pointer==&target && target+other==42?42:1; }',
        'int target=40,other=2; int *pointer=&target; '+driver)
    add('sibling externs share entity',
        'int inspect(void) { int *p; { extern int target; p=&target; *p=40; } '
        '{ extern int target; return p==&target?target+2:1; } }',
        'int target; '+driver)
    add('block-only then file declaration same entity',
        'int *slot(void) { extern int target; return &target; } int target=42; '
        'int inspect(void) { return slot()==&target?target:1; }', driver,
        globals={'target': Storage('target', bits=42)})
    add('visible file static inherited by block extern',
        'static int target=40; int inspect(void) { extern int target; target+=2; return target; }',
        driver, globals={'target': Storage('target', bits=40, public=False)})
    add('extern function explicit and implicit storage declarations',
        'int inspect(void) { extern int target(int); int other(int); return other(target(38)); }',
        'int target(int x) { return x+2; } int other(int x) { return x+2; } '+driver)
    add('function block scope hides automatic then restores it',
        'int inspect(void) { int target=2; { int target(int); if(target(40)!=42) return 1; } '
        'return target==2?42:2; }', 'int target(int x) { return x+2; } '+driver)
    add('visible internal function inherited',
        'static int target(int x) { return x+2; } '
        'int inspect(void) { extern int target(int); return target(40); }', driver)
    add('block function then later definition',
        'int inspect(void) { int target(int); return target(40); } int target(int x) { return x+2; }', driver)
    add('block function pointer object distinction',
        'int inspect(void) { extern int target(int),(*callback)(int); '
        'return callback==target?callback(40):1; }',
        'int target(int x) { return x+2; } int (*callback)(int)=target; '+driver)
    add('block function alias and queried declaration',
        'typedef int F(int); int inspect(void) { extern F target; typeof(target) other; '
        'F *callback=target; return other(callback(38)); }',
        'int target(int x) { return x+2; } int other(int x) { return x+2; } '+driver,
        features=('typeof',))
    add('array composite grows within block',
        'int inspect(void) { extern int target[]; extern int target[3]; extern int target[]; '
        'return sizeof target==12?target[2]:1; }', 'int target[3]={0,0,42}; '+driver)
    add('array visible composite inherited into block',
        'extern int target[3]; int inspect(void) { extern int target[]; return sizeof target==12?target[2]:1; }',
        'int target[3]={0,0,42}; '+driver)
    add('pointer-to-array composite within block',
        'int inspect(void) { extern int (*row)[]; extern int (*row)[3]; extern int (*row)[]; '
        'return sizeof *row==12?(*row)[2]:1; }', 'int target[3]={0,0,42}; int (*row)[3]=&target; '+driver)
    add('function parameter composite within block',
        'int inspect(void) { extern int target(int (*)[]); extern int target(int (*)[3]); '
        'int a[3]; a[2]=42; return target(&a); }',
        'int target(int (*p)[3]) { return (*p)[2]; } '+driver)
    add('loop local shadow restores block binding',
        'int inspect(void) { extern int target; for(int target=0;target<2;target++) {} return target; }',
        'int target=42; '+driver)
    add('static uninitialized persistence',
        'int tick(void) { static int cell; return ++cell; }',
        'int tick(void); int main(void) { return tick()==1 && tick()==2 && tick()==3?42:1; }',
        [Storage('cell', zero=True)])
    add('static initializer exactly once not per call',
        'int tick(void) { static int cell=40; return ++cell; }',
        'int tick(void); int main(void) { return tick()==41 && tick()==42?42:1; }', [Storage('cell', bits=40)])
    add('recursive shared static and automatic separation',
        'int recurse(int depth) { static int cell; int saved=++cell; '
        'if(depth) { if(recurse(depth-1)!=3) return 1; } '
        'return cell==3 && saved==3-depth?3:1; } '
        'int inspect(void) { return recurse(2)==3?42:1; }', driver, [Storage('cell', zero=True)])
    add('same spelling different functions and nested siblings',
        'int *first(void) { static int cell=1; return &cell; } '
        'int *second(void) { static int cell=2; return &cell; } '
        'int inspect(void) { int *a; int *b; { static int cell=3; a=&cell; } '
        '{ static int cell=4; b=&cell; } return first()!=second() && first()!=a && '
        'first()!=b && second()!=a && second()!=b && a!=b && '
        '*first()==1 && *second()==2 && *a==3 && *b==4?42:1; }', driver,
        [Storage('cell', bits=n) for n in (1,2,3,4)])
    add('static auto shadow and source list order',
        'int inspect(void) { static int cell=40; { int cell=2; if(cell!=2) return 1; } '
        '{ static int cell=2; if(cell!=2) return 2; } static int other=sizeof other; '
        'return cell+other==44?42:3; }', driver,
        [Storage('cell', bits=40), Storage('cell', bits=2), Storage('other', bits=4)])
    add('static loop lifetime',
        'int inspect(void) { int total=0; for(int i=0;i<3;i++) { static int cell=12; total+=++cell; } '
        'return total; }', driver, [Storage('cell', bits=12)])
    add('static lifetime escape across returns',
        'int *slot(void) { static int cell=40; return &cell; }',
        'int *slot(void); int main(void) { int *p=slot(); if(p!=slot() || *p!=40) return 1; '
        '*p+=2; return *slot(); }', [Storage('cell', bits=40)])
    add('two KCC translation units same local spelling',
        'int *first(void) { static int cell=40; return &cell; }',
        'int *first(void); int *second(void); int main(void) { '
        'int *a=first(); int *b=second(); if(a==b || *a!=40 || *b!=2) return 1; '
        '*a=41; *b=1; return *first()+*second(); }', [Storage('cell', bits=40)],
        peer='int *second(void) { static int cell=2; return &cell; }', peer_locals=[Storage('cell', bits=2)])
    for typ, width, bits, expression in [
        ('_Bool',1,1,'1'), ('char',1,42,'42'), ('signed char',1,-7,'-7'),
        ('unsigned char',1,255,'255'), ('short',2,-1234,'-1234'),
        ('unsigned short',2,65535,'65535'), ('int',4,-1234567,'-1234567'),
        ('unsigned',4,4294967295,'4294967295U'), ('long',8,4294967296,'4294967296L'),
        ('unsigned long',8,18446744073709551615,'18446744073709551615UL'),
        ('long long',8,4611686018427387904,'4611686018427387904LL'),
        ('unsigned long long',8,18446744073709551615,'18446744073709551615ULL'),
    ]:
        add('static initialized '+typ,
            f'{typ} *slot(void) {{ static {typ} cell={expression}; return &cell; }}',
            f'{typ} *slot(void); int main(void) {{ {typ} *p=slot(); '
            f'if(p!=slot() || *p!=({typ}){expression}) return 1; *p=0; return *slot()==0?42:2; }}',
            [Storage('cell',width,bits,width)])
    add('static constant expression arithmetic',
        'int inspect(void) { static int cell=(6*7)+(0 && 1); return cell; }', driver,
        [Storage('cell',bits=42)])
    add('static const scalar address escape',
        'const int *slot(void) { static const int cell=42; return &cell; }',
        'const int *slot(void); int main(void) { return slot()==slot()?*slot():1; }', [Storage('cell',bits=42)])
    add('static self sizeof uses own object type',
        'int inspect(void) { static long cell=sizeof cell; return cell==8?42:1; }',driver,
        [Storage('cell',8,8,8)])
    add('static pointer implicit zero and explicit null ICE',
        'int inspect(void) { static int *first; static int *second=2-2; '
        'static int (*callback)(int)=(void *)0; return !first && !second && !callback?42:1; }', driver,
        [Storage('first',8,alignment=8,zero=True),Storage('second',8,alignment=8),Storage('callback',8,alignment=8)])
    add('static nullptr object and callback',
        'int inspect(void) { static int *first=nullptr; static int (*callback)(int)=nullptr; '
        'return !first && !callback?42:1; }', driver,
        [Storage('first',8,alignment=8),Storage('callback',8,alignment=8)], features=('nullptr',))
    add('static pointer to native external object',
        'int *slot(void) { extern int target; static int *cell=&target; return cell; }',
        'int target=42; int *slot(void); int main(void) { return slot()==&target?*slot():1; }',
        [Storage('cell',8,alignment=8,reference=Reference('object','target'))])
    add('static pointer to previous static local and self',
        'int inspect(void) { static int target=42; static int *cell=&target; '
        'static void *self=&self; return cell==&target && self==&self?*cell:1; }', driver,
        [Storage('target',bits=42),Storage('cell',8,alignment=8,reference=Reference('object','@target')),
         Storage('self',8,alignment=8,reference=Reference('object','@self'))])
    add('static string direct literal',
        'const char *slot(void) { static const char *cell="a\\0bc"; return cell; }',
        'const char *slot(void); int main(void) { const char *p=slot(); '
        'return p==slot() && p[0]==97 && p[1]==0 && p[2]==98 && p[3]==99 && p[4]==0?42:1; }',
        [Storage('cell',8,alignment=8,reference=Reference('string',contents=b'a\0bc\0'))])
    add('static function address from block declaration',
        'int inspect(void) { extern int target(int); static int (*cell)(int)=&target; '
        'return cell==target?cell(40):1; }', 'int target(int x) { return x+2; } '+driver,
        [Storage('cell',8,alignment=8,reference=Reference('function','target'))])
    add('static array zero initialization and persistence',
        'int *slot(void) { static int cells[3]; return cells; }',
        'int *slot(void); int main(void) { int *p=slot(); if(p[0] || p[1] || p[2]) return 1; '
        'p[2]=42; return p==slot()?slot()[2]:2; }', [Storage('cells',12,alignment=4,zero=True)])
    add('static multidimensional array address and decay',
        'int inspect(void) { static int cells[2][3]; static int (*row)[3]=cells; '
        'static int (*whole)[2][3]=&cells; if(cells[0][0] || cells[1][2]) return 1; '
        'row[1][2]=42; return whole==&cells?(*whole)[1][2]:2; }',driver,
        [Storage('cells',24,alignment=4,zero=True),
         Storage('row',8,alignment=8,reference=Reference('object','@cells')),
         Storage('whole',8,alignment=8,reference=Reference('object','@cells'))])
    add('static pointer array zero elements',
        'int inspect(void) { static int *cells[3]; static int (*callbacks[2])(int); '
        'return !cells[0] && !cells[1] && !cells[2] && !callbacks[0] && !callbacks[1]?42:1; }', driver,
        [Storage('cells',24,alignment=8,zero=True),Storage('callbacks',16,alignment=8,zero=True)])
    add('static alias array and pointer',
        'typedef int A[3]; int inspect(void) { static A cells; static A *whole=&cells; '
        '(*whole)[2]=42; return cells[0]==0 && cells[1]==0?cells[2]:1; }', driver,
        [Storage('cells',12,alignment=4,zero=True),
         Storage('whole',8,alignment=8,reference=Reference('object','@cells'))])
    add('static nullptr_t storage',
        'typeof(nullptr) *slot(void) { static typeof(nullptr) cell=nullptr; return &cell; } '
        'int main(void) { typeof(nullptr) *p=slot(); '
        'return p==slot() && *p==nullptr?42:1; }', '',
        [Storage('cell',8,alignment=8)], features=('typeof','nullptr'))
    add('register void', 'int target(register void) { return 42; } int main(void) { return target(); }', features=())
    cases[-1].native_gaps = {'gcc': (('error', "'void' as only parameter may not be qualified"),)}
    add('register array unevaluated', 'int main(void) { register int a[2]; return sizeof(a[0])==4?42:1; }', features=())
    cases[-1].native_gaps = REGISTER_ARRAY_DIVERGENCES[cases[-1].owner]
    add('register array typeof', 'int main(void) { register int a[2]; typeof(a+0) p=0; return p==0?42:1; }', features=('typeof',))
    cases[-1].native_gaps = REGISTER_ARRAY_DIVERGENCES[cases[-1].owner]
    return cases


def local_mapping(path, expected, il_names=None):
    """Bijective native source-stem matching; never assumes GCC suffix numbers.

    Same-spelling distinct declarations carry different initialized values.
    KCC uses the exact ordered emission names validated by check_il instead.
    """
    widths = dict(zip(il_names, [s.width for s in expected])) if il_names is not None else None
    records = elf_objects(path, widths)
    mapping, used = [], set()
    for index, spec in enumerate(expected):
        wanted = (spec.bits % (1 << (8*spec.width))).to_bytes(spec.width, 'little')
        names = [il_names[index]] if il_names is not None else [
            name for name in records if re.search(r'(^|\.)'+re.escape(spec.stem)+r'(\.|$)',name)]
        matches = [name for name in names if name not in used and len(records.get(name, [])) == 1
                   and records[name][0][0] == 0 and records[name][0][1] == spec.width
                   and records[name][0][4] == wanted]
        assert len(matches) == 1, (path, spec, names, records)
        mapping.append(matches[0]); used.add(matches[0])
    return mapping


def check_storage(path, specs, names, global_specs=None, qbe=False):
    expected = dict(zip(names, specs))
    expected.update(global_specs or {})
    records = elf_objects(path, {n:s.width for n,s in expected.items()} if qbe else None)
    nm = invoke(['nm', '-a', '-S', path])
    assert nm.returncode == 0 and not nm.stderr, nm
    refs = {}
    elf = ElfRelocations(path)
    for name, spec in expected.items():
        entries = records.get(name, [])
        assert len(entries) == 1, (name, entries)
        binding, size, align, offset, contents = entries[0]
        public = name in (global_specs or {}) and spec.public
        wanted = (spec.bits % (1 << (spec.width*8))).to_bytes(spec.width, 'little')
        assert (binding, size, contents) == (int(public), spec.width, wanted), (name,entries,spec)
        assert align >= spec.alignment and offset % spec.alignment == 0, (name,entries,spec)
        lines = [line.split() for line in nm.stdout.splitlines() if line.split()[-1] == name]
        assert len(lines) == 1 and lines[0][-2] in ('BDR' if public else 'bdr'), (name,nm.stdout)
        if not qbe:
            assert len(lines[0]) == 4 and int(lines[0][1],16) == spec.width, (name,lines)
        symbol = elf.symbol(name)
        if spec.reference:
            reference = spec.reference
            if reference.name.startswith('@'):
                candidates = [n for n,s in zip(names,specs) if s.stem == reference.name[1:]]
                assert len(candidates) == 1
                reference = Reference(reference.kind,candidates[0])
            refs[name] = reference
        else:
            assert not [r for r in elf.relocations if r['section'] == symbol['section']
                        and symbol['value'] <= r['offset'] < symbol['value']+spec.width], (name,elf.relocations)
    elf.check(refs)
    # No implicit tentative/external storage and no accidental extra local data.
    actual = {n for n in records if not n.startswith('.Lkcc.string.')}
    assert actual == set(expected), (path,actual,set(expected))
    return records


def check_il(text, specs, globals=None):
    """Exact scalar/zero-array data declarations, unique private synthetic names.

    Emission order follows source declaration order. No function-entry stores can
    masquerade as persistent storage: runtime/AST checks independently gate it.
    """
    string_pattern = r'^data \$\.Lkcc\.string\.(\d+) = align 1 \{\n((?:\tb \d+,?\n)+)\}$'
    literals = [bytes(int(n) for n in re.findall(r'\tb (\d+)',body))
                for _,body in re.findall(string_pattern,text,re.M)]
    wanted_literals = [s.reference.contents for s in specs if s.reference and s.reference.kind == 'string']
    assert sorted(literals) == sorted(wanted_literals), (literals,wanted_literals,text)
    data_text = re.sub(string_pattern,'',text,flags=re.M)
    declarations = re.findall(r'^(export )?data \$(\S+) = align (\d+) \{ ([^\n]+) \}$',data_text,re.M)
    assert len(re.findall(r'^(?:export )?data ',data_text,re.M)) == len(declarations), text
    private = [(export,name,align,value) for export,name,align,value in declarations if name.startswith('.Lkcc.static.')]
    assert len(private) == len(specs), (private,specs,text)
    names = [row[1] for row in private]
    assert len(set(names)) == len(names)
    numbers = [int(name.removeprefix('.Lkcc.static.')) for name in names]
    assert numbers == list(range(len(numbers))), (numbers,text)
    lookup = {s.stem:n for s,n in zip(specs,names)}
    for (export,name,align,value),spec in zip(private,specs):
        assert not export and int(align) == spec.alignment, (name,align,spec)
        if spec.zero:
            wanted = f'z {spec.width}'
        elif spec.reference:
            reference = spec.reference
            if reference.kind == 'string':
                assert re.fullmatch(r'l \$\.Lkcc\.string\.\d+',value), (name,value)
                continue
            target = lookup[reference.name[1:]] if reference.name.startswith('@') else reference.name
            wanted = 'l $'+target
        else:
            wanted = {1:'b',2:'h',4:'w',8:'l'}[spec.width]+' '+str(spec.bits % (1 << (8*spec.width)))
        assert value == wanted, (name,value,wanted,text)
    remaining = [(e,n,int(a),v) for e,n,a,v in declarations if n not in names]
    expected_global = []
    for n,s in (globals or {}).items():
        export = 'export ' if s.public else ''
        expected_global.append((export,n,s.alignment,{1:'b',2:'h',4:'w',8:'l'}[s.width]+' '+str(s.bits)))
    assert remaining == expected_global, (remaining,expected_global,text)
    return names


# Constraint violations: exact native error/note signatures are compiler-family
# specific, original-specific and full-stream validated (not returncode != 0).
# (source, exact KCC message, GCC diagnostics, Clang diagnostics, optional features)
CONSTRAINTS = [
    ('int f(void) { extern int cell=1; return cell; }', 'block-scope extern declaration cannot have an initializer', (('error', "'cell' has both 'extern' and initializer"),), (('error', 'declaration of block scope identifier with linkage cannot have an initializer'),)),
    ('int f(void) { static int target(int); return 0; }', 'block-scope static function declaration is not permitted', (('error', "invalid storage class for function 'target'"),), (('error', "function declared in block scope cannot have 'static' storage class"),)),
    ('int f(void) { static int cell; static int cell; return cell; }', 'redeclaration of local in this scope', (('error', "redeclaration of 'cell' with no linkage"), ('note', "previous declaration of 'cell' with type 'int'")), (('error', "redefinition of 'cell'"), ('note', 'previous definition is here'))),
    ('int f(void) { int cell; extern int cell; return 0; }', 'redeclaration of local in this scope', (('error', "extern declaration of 'cell' follows declaration with no linkage"), ('note', "previous declaration of 'cell' with type 'int'")), (('error', "extern declaration of 'cell' follows non-extern declaration"), ('note', 'previous definition is here'))),
    ('int f(void) { extern int cell; extern long cell; return 0; }', 'incompatible external object declaration', (('error', "conflicting types for 'cell'; have 'long int'"), ('note', "previous declaration of 'cell' with type 'int'")), (('error', "redeclaration of 'cell' with a different type: 'long' vs 'int'"), ('note', 'previous declaration is here'))),
    ('int f(void) { int target(int); int target(long); return 0; }', 'incompatible function declaration', (('error', "conflicting types for 'target'; have 'int(long int)'"), ('note', "previous declaration of 'target' with type 'int(int)'")), (('error', "conflicting types for 'target'"), ('note', 'previous declaration is here'))),
    ('int f(void) { int target(int); return target(1); } int g(void) { return target(1); }', 'call to undeclared function', (('error', "implicit declaration of function 'target' [-Wimplicit-function-declaration]"), ('note', "previous declaration of 'target' with type 'int(int)'")), (('error', "use of undeclared identifier 'target'"),)),
    ('int f(void) { extern int cell; return cell; } int g(void) { return cell; }', 'use of undeclared identifier', (('error', "'cell' undeclared (first use in this function)"), ('note', 'each undeclared identifier is reported only once for each function it appears in')), (('error', "use of undeclared identifier 'cell'"),)),
    ('int f(void) { { extern int cell; } { return cell; } }', 'use of undeclared identifier', (('error', "'cell' undeclared (first use in this function)"), ('note', 'each undeclared identifier is reported only once for each function it appears in')), (('error', "use of undeclared identifier 'cell'"),)),
    ('int f(void) { int copy=cell; extern int cell; return copy; }', 'use of undeclared identifier', (('error', "'cell' undeclared (first use in this function)"), ('note', 'each undeclared identifier is reported only once for each function it appears in')), (('error', "use of undeclared identifier 'cell'"),)),
    ('int target(void); int f(void) { static int cell=target(); return cell; }', 'file-scope initializer must be an integer constant expression', (('error', 'initializer element is not constant'),), (('error', 'initializer element is not a compile-time constant'),)),
    ('int f(int argument) { static int *cell=&argument; return *cell; }', 'file-scope pointer initializer requires a supported null or direct address constant expression', (('error', 'initializer element is not constant'),), (('error', 'initializer element is not a compile-time constant'),)),
    ('int f(void) { static int cell[]; return 0; }', 'static local object type must be complete', (('error', "array size missing in 'cell'"),), (('error', 'definition of variable with array type needs an explicit size or an initializer'),)),
    ('int f(int n) { static int cell[n]; return 0; }', 'array bound must be an integer constant expression; variable-length arrays are not supported yet', (('error', "storage size of 'cell' isn't constant"),), (('error', "variable length array declaration cannot have 'static' storage duration"),)),
    ('int f(void) { typedef int cell; extern int cell; return 0; }', 'ordinary declaration conflicts with typedef name', (('error', "'cell' redeclared as different kind of symbol"), ('note', "previous declaration of 'cell' with type 'cell' {aka 'int'}")), (('error', "redefinition of 'cell' as different kind of symbol"), ('note', 'previous definition is here'))),
    ('extern int cell[]; int f(void) { extern int cell[3]; return sizeof cell; } int g(void) { return sizeof cell; }', 'sizeof requires a complete object type', (('error', "invalid application of 'sizeof' to incomplete type 'int[]'"),), (('error', "invalid application of 'sizeof' to an incomplete type 'int[]'"),)),
    ('int f(void) { { extern int cell[3]; } { extern int cell[]; return sizeof cell; } }', 'sizeof requires a complete object type', (('error', "invalid application of 'sizeof' to incomplete type 'int[]'"),), (('error', "invalid application of 'sizeof' to an incomplete type 'int[]'"),)),
    ('extern int cell[]; int f(void) { { extern int cell[3]; } return sizeof cell; }', 'sizeof requires a complete object type', (('error', "invalid application of 'sizeof' to incomplete type 'int[]'"),), (('error', "invalid application of 'sizeof' to an incomplete type 'int[]'"),)),
    ('int f(void) { static int cell=cell; return cell; }', 'file-scope initializer must be an integer constant expression', (('error', 'initializer element is not constant'),), (('error', 'initializer element is not a compile-time constant'),)),
    ('int f(void) { for(static int cell=0;cell<1;cell++) {} return 0; }', 'for declaration requires an automatic or register object', (('error', "declaration of static variable 'cell' in 'for' loop initial declaration"),), (('error', "declaration of non-local variable in 'for' loop"),)),
    ('int f(void) { for(extern int cell;cell<1;cell++) {} return 0; }', 'for declaration requires an automatic or register object', (('error', "declaration of 'extern' variable 'cell' in 'for' loop initial declaration"),), (('error', "declaration of non-local variable in 'for' loop"),)),
    ('int f(void) { register int a[2]; return sizeof(&a); }', 'cannot take the address of a register object', (('error', "address of register variable 'a' requested"),), (('error', 'address of register variable requested'),)),
    ('typedef int F(void); int f(void) { F auto target; return 0; }',
     'auto storage requires an object type',
     (('error', "invalid storage class for function 'target' [-Wpedantic]"),
      ('error', "nested function 'target' declared but never defined")),
     (('error', "cannot combine with previous 'type-name' declaration specifier"),)),
    ('int target(void); int f(void) { auto typeof(target) other; return 0; }',
     'auto storage requires an object type', (),
     (('error', "cannot combine with previous 'auto' declaration specifier"),
      ('error', "declaration of variable 'other' with deduced type 'auto' requires an initializer")), ('typeof',)),

]

# Valid C but deliberately outside the supported static initializer subset.
SUBSET = [
    ('int f(void) { static int cells[2]={1,2}; return cells[0]; }', 'expected integer literal'),
    ('int f(void) { static int cell={42}; return cell; }', 'expected integer literal'),
]

# UB is NOT a mandatory native diagnostic. These originals only compile with
# KCC. They are never native or KCC executables and never oracle agreements.
UB_REFUSALS = [
    ('int f(void) { extern int cell; return 0; } int g(void) { extern long cell; return 0; }', 'incompatible external object declaration'),
    ('static int target; int f(void) { int target; { extern int target; return target; } }', 'block extern declaration conflicts with hidden internal linkage'),
    ('int f(void) { register int cells[2]; int *p=cells; return 0; }', 'register array-to-pointer conversion is not supported'),
]


# Evaluated-invalid constant arithmetic is a constant-expression constraint;
# native compilers vary between error and warning acceptance. KCC compile-only
# refusal, NEVER execution or native agreement (separate from valid subset/UB).
CONSTEXPR_REFUSALS = [
    ('int f(void) { static int cell=1/0; return cell; }', 'division by zero in integer constant expression'),
    ('int f(void) { static int cell=2147483647+1; return cell; }', 'signed overflow in integer constant expression'),
]


def native_refusal(text, result, source, output, expected, clang):
    return (result.returncode == 1 and not result.stdout and not output.exists()
            and native_diagnostics(result.stderr,source,text,clang) == tuple(expected))


def register_array_refusal(text, result, source, output, clang):
    """Allow only a fixed original + family + complete diagnostic transcript."""
    family = 'clang' if clang else 'gcc'
    expected = REGISTER_ARRAY_DIVERGENCES.get(text, {}).get(family)
    return (expected is not None and
            native_refusal(text, result, source, output, expected, clang))


def register_array_controls(directory):
    """Replay GCC13 CI evidence and poison every verdict path; execute no C."""
    import subprocess
    source, output = directory/'register-original.c', directory/'register-original.o'
    for text, families in REGISTER_ARRAY_DIVERGENCES.items():
        source.write_text(text+'\n')
        for family, expected in families.items():
            clang = family == 'clang'
            message = expected[0][1]
            # Match the actual GCC13 In-function/source/caret rendering, not a
            # keyword-unsupported error or a flag-only diagnostic exception.
            context = '' if clang else f"{source}: In function ‘main’:\n"
            rendered = (context+f'{source}:1:1: error: {message}\n'
                        f'    1 | {text}\n      | ^~~\n')
            if clang:
                rendered += '1 error generated.\n'
            good = subprocess.CompletedProcess([],1,'',rendered)
            output.unlink(missing_ok=True)
            assert register_array_refusal(text,good,source,output,clang)
            assert not register_array_refusal(text+' ',good,source,output,clang)
            assert not register_array_refusal('int unrelated;',good,source,output,clang)
            poisoned = [rendered+'unrecognized tool output\n',
                        rendered+'internal compiler error: broken\n',
                        rendered.replace('error:', 'fatal error:', 1),
                        rendered.replace(message, 'unrelated register failure'),
                        rendered.replace(text, text.replace('a[2]', 'a[3]')),
                        rendered+'1 error generated.\n']
            poisoned += [rendered+f'{source}:1:1: {kind}: extra\n'
                         for kind in ('warning','error','note')]
            for stderr in poisoned:
                assert not register_array_refusal(text,subprocess.CompletedProcess([],1,'',stderr),source,output,clang)
            for status in (0,2,127,-6,-9,-11):
                assert not register_array_refusal(text,subprocess.CompletedProcess([],status,'',rendered),source,output,clang)
            assert not register_array_refusal(text,subprocess.CompletedProcess([],1,'unexpected stdout',rendered),source,output,clang)
            output.write_bytes(b'stale')
            assert not register_array_refusal(text,good,source,output,clang)
    output.unlink(missing_ok=True)
    print('Register-array controls: exact GCC13/Clang originals, full-stream evidence and poison/stale rejection')


def controls(directory):
    """Storage-specific adversarial tests, in addition to imported harness gates."""
    source, output = directory/'storage-control.c',directory/'storage-control.o'
    source.write_text('int *slot(void) { static int cell=40; return &cell; }\n')
    producer([HOST,'-std=c2x','-pedantic-errors','-fno-common','-O0','-c',source,'-o',output],output)
    specs = [Storage('cell',bits=40)]
    names = local_mapping(output,specs)
    check_storage(output,specs,names)
    for changed in ([Storage('cell',bits=41)], [Storage('cell',8,40,8)], [Storage('cell',bits=40,alignment=64)]):
        try:
            check_storage(output,changed,names)
        except AssertionError:
            pass
        else:
            raise AssertionError('storage oracle accepted wrong bytes/size/alignment')
    for original in ('int cell=40;',
                     'int *slot(void) { static int cell=40; return &cell; } int extra=41;'):
        source.write_text(original+'\n')
        producer([HOST,'-std=c2x','-pedantic-errors','-fno-common','-O0','-c',source,'-o',output],output)
        try:
            check_storage(output,specs,['cell'] if original == 'int cell=40;' else local_mapping(output,specs))
        except AssertionError:
            pass
        else:
            raise AssertionError('ELF oracle accepted exported local or extra storage')
    il = 'data $.Lkcc.static.0 = align 4 { w 40 }\n'
    assert check_il(il,specs) == ['.Lkcc.static.0']
    for bad in (il.replace('data','export data'), il+il, il.replace('40','41'),
                il.replace('align 4','align 1'),il.replace('w 40','z 4'),
                il.replace('.Lkcc.static.0','cell'),il+'export data $absent = align 4 { z 4 }\n'):
        try:
            check_il(bad,specs)
        except (AssertionError,ValueError):
            pass
        else:
            raise AssertionError('IL oracle accepted public/duplicate/wrong initializer/storage/name')
    text = 'int f(void) { extern int cell=1; return cell; }'
    source.write_text(text+'\n')
    message = 'storage-specific error'
    expected = (('error',message),)
    for clang in (False,True):
        good = f'{source}:1:25: error: {message}\n'+('1 error generated.\n' if clang else '')
        import subprocess
        result = subprocess.CompletedProcess([],1,'',good)
        output.unlink(missing_ok=True)
        assert native_refusal(text,result,source,output,expected,clang)
        for status,stdout,stderr in [(0,'',good),(-11,'',good),(2,'',good),(1,'noise',good),
                                     (1,'',good+'extra\n'),(1,'',good.replace(message,'different')),
                                     (1,'',good.replace('error:','fatal error:'))]:
            assert not native_refusal(text,subprocess.CompletedProcess([],status,stdout,stderr),source,output,expected,clang)
        output.write_bytes(b'stale')
        assert not native_refusal(text,result,source,output,expected,clang)
    print('Block storage controls: bytes/size/alignment, unique private IL, exact diagnostics, stale outputs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-only',action='store_true')
    parser.add_argument('--harness-self-test',action='store_true')
    options = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='kcc block storage ') as tmp:
        d = Path(tmp)
        harness_self_test(d)
        compiler_selection_self_test(d)
        controls(d)
        register_array_controls(d)
        if options.harness_self_test:
            return
        compilers = native_compilers(HOST,os.environ.get('CLANG_CC') or shutil.which('clang'))
        source, other_source, peer_source = (d/n for n in ('owner.c','companion.c','peer.c'))
        native, other, peer_obj, exe = (d/n for n in ('native.o','other.o','peer.o','program'))
        il, assembly, obj = (d/n for n in ('owner.ssa','owner.s','owner.o'))
        supported = {cc:features_for(cc,source,native) for cc in compilers}
        counts = {cc:[0,0,0,0] for cc in compilers}
        kcc_cases = qbe_cases = refused = 0
        cases = fixtures()
        assert len({c.name for c in cases}) == len(cases)
        for case in cases:
            source.write_text(case.owner+'\n'); other_source.write_text(case.companion+'\n')
            peer_source.write_text(case.peer+'\n')
            for cc in compilers:
                if not set(case.features) <= supported[cc]:
                    counts[cc][1] += 1
                    continue
                gap = case.native_gaps.get('clang' if clang_style(cc) else 'gcc')
                if gap:
                    native.unlink(missing_ok=True)
                    result = invoke([cc,'-std=c2x','-pedantic-errors','-fno-common','-O0','-c',source,'-o',native])
                    if case.owner in REGISTER_ARRAY_DIVERGENCES:
                        assert register_array_refusal(case.owner,result,source,native,clang_style(cc)), (case.name,cc,result)
                    else:
                        assert native_refusal(case.owner,result,source,native,gap,clang_style(cc)), (case.name,cc,result)
                    counts[cc][3] += 1
                    continue
                expected_warnings = ()
                if clang_style(cc) and case.name == 'static pointer implicit zero and explicit null ICE':
                    expected_warnings = (('warning', "expression which evaluates to zero treated as a null pointer constant of type 'int *' [-Wnon-literal-null-conversion]"),)
                producer([cc,'-std=c2x','-pedantic-errors','-fno-common','-O0','-c',source,'-o',native],native,expected_warnings)
                names = local_mapping(native,case.locals)
                check_storage(native,case.locals,names,case.globals)
                objects = [native]
                if case.peer:
                    producer([cc,'-std=c2x','-pedantic-errors','-fno-common','-O0','-c',peer_source,'-o',peer_obj],peer_obj)
                    check_storage(peer_obj,case.peer_locals,local_mapping(peer_obj,case.peer_locals))
                    objects.append(peer_obj)
                if case.companion:
                    producer([cc,'-std=c2x','-pedantic-errors','-fno-common','-O0','-c',other_source,'-o',other],other)
                    objects.append(other)
                run_program(cc,objects,exe)
                counts[cc][0] += 1
            if options.native_only:
                continue
            kcc_objects = []
            for text,specs,globals,label in [(case.owner,case.locals,case.globals,'owner')]+(
                    [(case.peer,case.peer_locals,{},'peer')] if case.peer else []):
                input_path = source if label == 'owner' else peer_source
                result = invoke([KCC,input_path])
                assert result.returncode == 0 and not result.stderr and result.stdout, (case.name,result)
                names = check_il(result.stdout,specs,globals)
                if QBE:
                    il.write_text(result.stdout)
                    producer([QBE,'-t','amd64_sysv','-o',assembly,il],assembly)
                    assert not re.search(r'^\s*\.(?:comm|lcomm)\b',assembly.read_text(),re.M)
                    target = obj if label == 'owner' else peer_obj
                    # Preserve .L labels for exact ELF slot/base inspection.
                    producer([HOST,'-Wa,-L','-c',assembly,'-o',target],target)
                    check_storage(target,specs,names,globals,qbe=True)
                    kcc_objects.append(target)
            kcc_cases += 1
            if QBE:
                if case.companion:
                    producer([HOST,'-std=c2x','-pedantic-errors','-fno-common','-O0','-c',other_source,'-o',other],other)
                    kcc_objects.append(other)
                run_program(HOST,kcc_objects,exe)
                qbe_cases += 1
        for record in CONSTRAINTS:
            text,message,gcc,clang = record[:4]
            requirements = record[4] if len(record) == 5 else ()
            source.write_text(text+'\n')
            for cc in compilers:
                if not set(requirements) <= supported[cc]:
                    counts[cc][1] += 1
                    continue
                native.unlink(missing_ok=True)
                result = invoke([cc,'-std=c2x','-pedantic-errors','-fno-common','-O0','-c',source,'-o',native])
                assert native_refusal(text,result,source,native,clang if clang_style(cc) else gcc,clang_style(cc)), (text,cc,result.stderr)
                counts[cc][2] += 1
            if not options.native_only:
                assert message is not None, text
                reject(source,'error: '+message+'\n'); refused += 1
        if not options.native_only:
            for text,message in SUBSET+UB_REFUSALS+CONSTEXPR_REFUSALS:
                source.write_text(text+'\n')
                assert message is not None, text
                reject(source,'error: '+message+'\n'); refused += 1
        print(f'Block storage: {len(cases)} unchanged defined originals; KCC {kcc_cases}; '
              f'QBE/ELF/runtime {qbe_cases}; compile-only refusals {refused} '
              f'({len(CONSTRAINTS)} native constraints/{len(CONSTEXPR_REFUSALS)} constant-expression constraints/'
              f'{len(SUBSET)} subset/{len(UB_REFUSALS)} UB)')
        for cc,(agreements,gaps,constraints,divergences) in counts.items():
            print(f'{cc}: {agreements} unchanged ELF/runtime agreements; {gaps} keyword gaps (NOT agreements); '
                  f'{constraints} exact diagnostic constraints; {divergences} exact known native divergences (NOT agreements)')
        if options.native_only:
            print('NATIVE-ONLY: no claim of KCC coverage')
        elif not QBE:
            print('QBE unset: no claim of KCC ELF/runtime coverage')


if __name__ == '__main__':
    main()

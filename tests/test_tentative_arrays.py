# M17: exact newly legal originals moved to test_initialization_promotions.py.
"""Sole-owner tentative arrays and end-of-TU outer completion.

Run: [KCC=...] [HOST_CC=...] [QBE=...] python3 tests/test_tentative_arrays.py
Only defined curated originals execute. Invalid, subset and generated resource
sources compile only; native constraints compile real objects. Native diagnostic
classification follows the independent source/standard and object-layout audit.

The unchanged owner TU alone defines storage, whether compiled by kcc or native.
Companions only extern-declare its objects, with -fno-common and symbol checks.
Unknown-final arrays have ONE outer element: runtime indices stay in that object
(index 0 for a primitive; row 0 for rows). Larger indices require a visible later
known completion. No null callback call, null dereference, cross-row arithmetic,
uninitialized automatic read, invalid-source execution, or fuzz execution.

Audited native split: exact benign final-one and legacy-logical diagnostics can
count as agreements ONLY after every owned nm-S size/count/kind guard and a later
valid native runtime pass. Exact Clang later-completion underallocations are
implementation bugs, counted separately and NEVER linked/executed. Every source
and full diagnostic sequence is frozen; independently probed compiler family/target,
flags, status 0, empty stdout, existing object and exact owned layout are required.
Exact vendor version and executable alias are LOGGED, not acceptance keys.
Unknown diagnostics/layouts fail closed. Actual Ubuntu CI validation is separate
and remains pending; local focused results are recorded in their host logs.
The old extern-array suite retains its separate audited typeof_unqual-array gap;
this draft does not duplicate that original or add a new waiver.
"""
# Saved AWS observations predict the following ONLY for those recorded outcomes.
# Actual Ubuntu CI validation is PENDING; no Ubuntu compiler was probed here.
# Portable classification uses invariants, not the vendor/version strings below.
# EXPECTED after implementation; compile-only audit is NOT runtime validation:
# gcc14-gcc: 74 agreements = 42 clean + 32 final-one warnings; 0 storage bugs.
# clang-18: 70 agreements = 39 clean + 31 final-one warnings; 4 storage bugs.
# gcc: 70 agreements = 40 clean + 30 final-one warnings; 4 keyword-gated pairs.
# clang-15: 68 agreements = 37 clean + 30 final-one + 1 logical warning;
#           2 storage bugs and 4 keyword-gated pairs.
# Independent future kcc/QBE: 74 pairs modern / 73 legacy (one companion gap).
# Constraints: 29 modern / 26 legacy. Unknown native messages are not waived.
# Exact newly supported originals moved to test_storage_promotions.py.
import os
import re
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root/'build'/'kcc'))
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
integers = ['_Bool', 'char', 'signed char', 'unsigned char', 'short', 'unsigned short',
            'int', 'unsigned', 'long', 'unsigned long', 'long long', 'unsigned long long']
values = ['1', '-7', '-7', '255', '-1234', '65535', '-1234567', '4294967295U',
          '4294967296L', '18446744073709551615UL', '4611686018427387904LL',
          '18446744073709551615ULL']
primitive_sizes = [1, 1, 1, 1, 2, 2, 4, 4, 8, 8, 8, 8]
pairs = []


def pair(name, text, companion, owned, features=(), companion_features=()):
    # owned maps name to (exact zero-storage bytes, target alignment).
    pairs.append((name, text, companion, owned, features, companion_features))


# 48 primitive arrangements: 12 leaves x fixed/unknown-final x both directions.
# Source unknown bounds stay unknown during expression analysis; only final
# storage layout uses count 1. Companion fixed [1] is in a DIFFERENT TU and
# cannot complete the owner's source type. Never use sizeof(owner unknown).
for suffix, count, label in [('[3]', 3, 'fixed'), ('[]', 1, 'unknown final one')]:
    index = count-1
    for typ, value, size in zip(integers, values, primitive_sizes):
        layout = {'items': (count*size, size)}
        zero_checks = ' || '.join(f'items[{i}]!=0' for i in range(count))
        pair(typ+' '+label+' owner driver',
             f'{typ} items{suffix}; extern {typ} items{suffix}; {typ} items{suffix}; '
             f'extern int verify({typ} *,{typ}); int main(void) {{ '
             f'if({zero_checks}) return 1; {typ} (*whole){suffix}=&items; '
             f'if((*whole)+{index}!=&items[{index}]) return 2; '
             f'items[{index}]=({typ}){value}; int result=verify(&items[{index}],items[{index}]); '
             f'return result==42 && items[{index}]==0?42:3; }}',
             f'extern {typ} items[{count}]; int verify({typ} *p,{typ} value) {{ '
             f'if(p!=&items[{index}] || value!=({typ}){value} || *p!=value) return 1; '
             '*p=0; return 42; }', layout)
        pair(typ+' '+label+' companion driver',
             f'extern {typ} items{suffix}; {typ} items{suffix}; {typ} items{suffix}; '
             f'{typ} get(void) {{ return items[{index}]; }} '
             f'void put({typ} x) {{ items[{index}]=x; }} '
             f'{typ} *elements(void) {{ return items; }} '
             f'{typ} (*whole(void)){suffix} {{ return &items; }}',
             f'extern {typ} items[{count}]; {typ} get(void); void put({typ}); '
             f'{typ} *elements(void); {typ} (*whole(void)){suffix}; int main(void) {{ '
             f'if({zero_checks} || get()!=0 || elements()!=items || whole()!=&items) return 1; '
             f'put(({typ}){value}); if(get()!=({typ}){value} || items[{index}]!=({typ}){value}) return 2; '
             f'elements()[{index}]=0; return get()==0?42:3; }}', layout)

pair('earlier decay then visible known outer completion',
     'int items[]; int *earlier(void) { return items; } extern int items[3]; '
     'int main(void) { if(sizeof items!=12 || items[0] || items[1] || items[2]) return 1; '
     'items[2]=42; return earlier()==items?earlier()[2]:2; }',
     'extern int items[3];', {'items': (12, 4)})
pair('extern-first known tentative anchor survives later unknown',
     'extern int items[]; int items[3]; int items[]; int main(void) { '
     'if(sizeof items!=12 || items[2]) return 1; items[2]=42; return items[2]; }',
     'extern int items[3];', {'items': (12, 4)})
pair('unknown outer row finalizes to exactly one complete row',
     'int rows[][3]; int main(void) { if(rows[0][0] || rows[0][1] || rows[0][2]) return 1; '
     'int (*p)[3]=rows; if(sizeof rows[0]!=12 || p+1-p!=1) return 2; '
     'rows[0][2]=42; return p[0][2]; }',
     'extern int rows[1][3];', {'rows': (12, 4)})
pair('unknown rows gain two rows before runtime second-row access',
     'int rows[][3]; int (*earlier(void))[3] { return rows; } '
     'extern int rows[2][3]; int main(void) { if(sizeof rows!=24 || rows[1][2]) return 1; '
     'rows[1][2]=42; return earlier()[1][2]; }',
     'extern int rows[2][3];', {'rows': (24, 4)})
pair('fixed rows use row and whole-array strides without crossing subarrays',
     'int rows[2][3]; int main(void) { int (*p)[3]=rows; int (*whole)[2][3]=&rows; '
     'if(sizeof rows!=24 || sizeof rows[0]!=12 || p+1!=&rows[1] || whole+1-whole!=1) return 1; '
     'if(rows[0][2] || rows[1][2]) return 2; rows[1][2]=42; return (*whole)[1][2]; }',
     'extern int rows[2][3];', {'rows': (24, 4)})
pair('pointer array slots zero then point only to live locals',
     'int *items[2]; int main(void) { if(items[0] || items[1]) return 1; '
     'int a=40,b=2; items[0]=&a; items[1]=&b; int **slot=&items[0]; '
     '*slot=items[1]; int result=*items[0]+40; items[0]=0; items[1]=0; return result; }',
     'extern int *items[2];', {'items': (16, 8)})
pair('unknown pointer array companion writes only sole element',
     'int *items[]; int **elements(void) { return items; } int get(void) { return *items[0]; }',
     'extern int *items[1]; int **elements(void); int get(void); int main(void) { '
     'if(items[0] || elements()!=items) return 1; int value=42; elements()[0]=&value; '
     'int result=get(); items[0]=0; return result; }', {'items': (8, 8)})
pair('fixed callback array private target assigned through element address',
     'int (*items[2])(int); static int plus(int x) { return x+2; } '
     'void arm(void) { int (**slot)(int)=&items[1]; *slot=plus; }',
     'extern int (*items[2])(int); void arm(void); int main(void) { '
     'if(items[0] || items[1]) return 1; arm(); if(!items[1]) return 2; return items[1](40); }',
     {'items': (16, 8)})
pair('unknown callback array null checked before sole-slot assignment',
     'int (*items[])(int); extern int plus(int); int main(void) { if(items[0]) return 1; '
     'items[0]=plus; int result=items[0](40); items[0]=0; return result; }',
     'extern int (*items[1])(int); int plus(int x) { return x+2; }', {'items': (8, 8)})
pair('unknown void callback array assigned before call',
     'void (*items[])(int *); extern void set(int *); int main(void) { if(items[0]) return 1; '
     'int value=0; items[0]=set; items[0](&value); items[0]=0; return value; }',
     'extern void (*items[1])(int *); void set(int *p) { *p=42; }', {'items': (8, 8)})
pair('pointer-returning callback array zero then live local pointee',
     'int *(*items[1])(int *); extern int *identity(int *); int main(void) { '
     'if(items[0]) return 1; int value=40; items[0]=identity; int *p=items[0](&value); '
     'if(p!=&value) return 2; *p+=2; items[0]=0; return value; }',
     'extern int *(*items[1])(int *); int *identity(int *p) { return p; }', {'items': (8, 8)})
pair('const fixed array elements are zero and whole address agrees',
     'const int items[3]; const int (*whole(void))[3] { return &items; }',
     'extern const int items[3]; const int (*whole(void))[3]; int main(void) { '
     'return items[0]==0 && items[1]==0 && items[2]==0 && whole()==&items?42:1; }',
     {'items': (12, 4)})
pair('const unknown array has exactly one zero element',
     'const int items[]; extern int inspect(void); int main(void) { return items[0]==0?inspect():1; }',
     'extern const int items[1]; int inspect(void) { return items[0]==0?42:1; }', {'items': (4, 4)})
pair('const pointer elements remain zero nonmodifiable objects',
     'int *const items[2]; extern int inspect(void); int main(void) { '
     'return !items[0] && !items[1]?inspect():1; }',
     'extern int *const items[2]; int inspect(void) { return !items[0] && !items[1]?42:1; }',
     {'items': (16, 8)})
pair('mixed scalar array callback and function declaration list',
     'int scalar,items[3],f(int),(*callbacks[1])(int); int main(void) { '
     'if(scalar || items[2] || callbacks[0]) return 1; scalar=40; callbacks[0]=f; '
     'items[2]=callbacks[0](scalar); callbacks[0]=0; return items[2]; }',
     'extern int scalar; extern int items[3]; extern int (*callbacks[1])(int); '
     'int f(int x) { return x+2; }', {'scalar': (4, 4), 'items': (12, 4), 'callbacks': (8, 8)})
pair('fixed row typedef roots retain shape and zero fill',
     'typedef int Row[3]; Row rows[2]; int main(void) { '
     'if(sizeof rows!=24 || rows[1][2]) return 1; rows[1][2]=42; return rows[1][2]; }',
     'extern int rows[2][3];', {'rows': (24, 4)})
pair('unknown typedef root owns one final element',
     'typedef int Unknown[]; Unknown items; int main(void) { '
     'if(items[0]) return 1; items[0]=42; return items[0]; }',
     'extern int items[1];', {'items': (4, 4)})
pair('earlier unknown array query preserves pointer identity after completion',
     'int items[]; typedef typeof(items) Saved; Saved *earlier(void) { return &items; } '
     'extern int items[3]; int main(void) { if(sizeof items!=12 || items[2]) return 1; '
     'items[2]=42; return earlier()==&items?(*earlier())[2]:2; }',
     'extern int items[3];', {'items': (12, 4)}, ('typeof',))
pair('captured unknown alias independently finalizes separate object to one',
     'int items[]; typedef typeof(items) Saved; Saved other; extern int items[3]; '
     'int main(void) { if(items[2] || other[0]) return 1; '
     'items[2]=40; other[0]=2; return items[2]+other[0]; }',
     'extern int items[3]; extern int other[1];', {'items': (12, 4), 'other': (4, 4)}, ('typeof',))
pair('own redeclaration bound observes prior known outer bound',
     'int items[3]; int items[sizeof items/sizeof items[0]]; int main(void) { '
     'if(items[2]) return 1; items[2]=42; return items[2]; }',
     'extern int items[3];', {'items': (12, 4)})
pair('same-list later bound sees completed preceding declarator',
     'int items[3],other[sizeof items/sizeof items[0]]; int main(void) { '
     'if(sizeof other!=12 || items[2] || other[2]) return 1; other[2]=42; return other[2]; }',
     'extern int items[3]; extern int other[3];', {'items': (12, 4), 'other': (12, 4)})
pair('own local bound sees outer array before local publication',
     'int items[3]; int main(void) { long items[sizeof items]; '
     'if(sizeof items!=96) return 1; items[11]=42; return items[11]; }',
     'extern int items[3];', {'items': (12, 4)})
pair('unknown nullptr array has one zero/null element',
     'typeof(nullptr) items[]; extern int inspect(void); int main(void) { '
     'if(items[0]!=nullptr) return 1; int *p=items[0]; items[0]=nullptr; return !p?inspect():2; }',
     'extern typeof(nullptr) items[1]; int inspect(void) { return items[0]==nullptr?42:1; }',
     {'items': (8, 8)}, ('typeof', 'nullptr'), ('typeof', 'nullptr'))
pair('private function type query creates zero array without private reference',
     'static int private_fn(int); typeof(&private_fn) items[2]; extern int inspect(void); '
     'int main(void) { return !items[0] && !items[1]?inspect():1; }',
     'extern int (*items[2])(int); int inspect(void) { return !items[0] && !items[1]?42:1; }',
     {'items': (16, 8)}, ('typeof',))
pair('scalar and pointer zero-storage behavior retained alongside array',
     'long scalar; int items[3]; int *pointer; int main(void) { '
     'if(scalar || items[2] || pointer) return 1; scalar=40; items[2]=2; pointer=&items[2]; '
     'int result=scalar+*pointer; pointer=0; return result; }',
     'extern long scalar; extern int items[3]; extern int *pointer;',
     {'scalar': (8, 8), 'items': (12, 4), 'pointer': (8, 8)})
pair('pure extern unknown stays declaration-only beside owned scalar',
     'int scalar; extern int absent[]; extern int inspect(void); '
     'int main(void) { if(scalar) return 1; scalar=42; return inspect(); }',
     'extern int scalar; extern int absent[]; int inspect(void) { return scalar; }', {'scalar': (4, 4)})

# Every original below is compile-only, even those
# whose unknown array would eventually have count 1 in a valid translation.
# End-of-TU layout completion must not retroactively legalize earlier sizeof,
# arithmetic on a pointer-to-incomplete-array, or captured unknown aliases.
constraints = [
    ('int items[]; int f(void) { return sizeof items; }', 'complete object type'),
    ('int items[]; int f(void) { return sizeof items; } int items[3];', 'complete object type'),
    ('int items[]; int f(void) { return &items+1==&items; }', 'complete object referent'),
    ('extern int items[]; int f(void) { return sizeof items; }', 'complete object type'),
    ('int items[2]; int items[3];', 'incompatible external object'),
    ('int items[][2]; extern int items[][3];', 'incompatible external object'),
    ('int items[2]; const int items[2];', 'incompatible external object'),
    ('int *items[2]; const int *items[2];', 'incompatible external object'),
    ('int items[2]; int *items;', 'incompatible external object'),
    ('int items[2]; int items(void);', 'function name conflicts'),
    ('int items(void); int items[2];', 'conflicts with prior ordinary'),
    ('typedef int items; int items[2];', 'conflicts with prior ordinary'),
    ('int items[2]; typedef int items;', 'conflicts with prior ordinary'),
    ('int items[2][];', 'array element type must be complete'),
    ('int items[][];', 'array element type must be complete'),
    ('void items[2];', 'array element type must be complete'),
    ('int items[2](void);', 'array element type must be complete'),
    ('int items[0];', 'array bound'),
    ('int items[-1];', 'array bound'),
    ('int n; int items[n];', 'integer constant expression'),
    ('int items[2],other[2]; int f(void) { items=other; return 0; }', 'modifiable lvalue'),
    ('int items[2][3]; int f(void) { items[0]=items[1]; return 0; }', 'modifiable lvalue'),
    ('const int items[2]; int f(void) { items[0]=1; return 0; }', 'modifiable lvalue'),
    ('int *const items[2]; int f(void) { items[0]=0; return 0; }', 'modifiable lvalue'),
    ('int items[2][3]; int f(void) { int **p=items; return 0; }', 'pointer conversion'),
    ('int items[2]; int f(void) { return items(); }', 'called expression'),
]
c23_constraints = [
    ('int items[]; typedef typeof(items) Saved; extern int items[3]; '
     'Saved old; int f(void) { return sizeof old; }', 'complete object type'),
    ('int items[]; typeof(items) *earlier(void) { return &items; } extern int items[3]; '
     'int f(void) { return sizeof *earlier(); }', 'complete object type'),
    ('int items[]; typedef typeof(items) Saved; Saved old; '
     'int f(void) { return sizeof old; }', 'complete object type'),
]
subset_errors = [
    ('int main[1];', 'tentative main object is not supported on the Linux target'),
]
unavailable_initializers = [
    'int items[3]; int f(void) { auto items='+initializer+'; return 0; }'
    for initializer in ['items', 'sizeof items', '(typeof(items[0]))0', 'sizeof(typeof(items))', '&items', '0?items:items']
]


def diagnostic_records(text):
    return re.findall(r'(fatal error|error|warning|note): ([^\n]+)',
                      text.replace('‘', "'").replace('’', "'"))


def legacy_feature_gap(feature, text, result):
    """Exact independent keyword probes, not a catch-all native failure waiver."""
    probes = {'typeof': 'typeof(int) value;', 'typeof_unqual': 'typeof_unqual(int) value;',
              'nullptr': 'int *p=nullptr;'}
    expected = {
        'typeof': [
            [('error', "return type defaults to 'int' [-Wimplicit-int]"),
             ('error', "expected declaration specifiers before 'value'"),
             ('error', "expected '{' at end of input")],
            [('error', 'expected function body after function declarator')],
        ],
        'nullptr': [
            [('error', "'nullptr' undeclared here (not in a function)")],
            [('error', "use of undeclared identifier 'nullptr'")],
        ],
    }
    expected['typeof_unqual'] = expected['typeof']
    return (text == probes[feature] and result.returncode == 1 and
            diagnostic_records(result.stderr) in expected[feature])


# Portable invariant policy, grounded in N3096 6.9.2p2 and the saved audit.
# Full original source/metadata and diagnostic records remain frozen literals.
# Probe family/target independently; log exact version, never key by vendor or
# executable alias. Actual Ubuntu CI evidence remains PENDING, not a claimed pass.
# Corrected layouts cannot match old bugs; the same exact valid original and
# records can instead take the explicitly approved correct-layout warning path.
NATIVE_OBJECT_FLAGS = ('-std=c2x', '-pedantic-errors', '-fno-common', '-c')
NATIVE_TARGET = 'amd64_sysv_lp64_le_signed_char'
AUDITED_NATIVE_SOURCES = {'_Bool unknown final one companion driver': 'extern _Bool items[]; _Bool items[]; _Bool items[]; _Bool get(void) { '
                                             'return items[0]; } void put(_Bool x) { items[0]=x; } _Bool '
                                             '*elements(void) { return items; } _Bool (*whole(void))[] { return '
                                             '&items; }',
 '_Bool unknown final one owner driver': '_Bool items[]; extern _Bool items[]; _Bool items[]; extern int verify(_Bool '
                                         '*,_Bool); int main(void) { if(items[0]!=0) return 1; _Bool '
                                         '(*whole)[]=&items; if((*whole)+0!=&items[0]) return 2; items[0]=(_Bool)1; '
                                         'int result=verify(&items[0],items[0]); return result==42 && '
                                         'items[0]==0?42:3; }',
 'captured unknown alias independently finalizes separate object to one': 'int items[]; typedef typeof(items) Saved; '
                                                                          'Saved other; extern int items[3]; int '
                                                                          'main(void) { if(items[2] || other[0]) '
                                                                          'return 1; items[2]=40; other[0]=2; return '
                                                                          'items[2]+other[0]; }',
 'char unknown final one companion driver': 'extern char items[]; char items[]; char items[]; char get(void) { return '
                                            'items[0]; } void put(char x) { items[0]=x; } char *elements(void) { '
                                            'return items; } char (*whole(void))[] { return &items; }',
 'char unknown final one owner driver': 'char items[]; extern char items[]; char items[]; extern int verify(char '
                                        '*,char); int main(void) { if(items[0]!=0) return 1; char (*whole)[]=&items; '
                                        'if((*whole)+0!=&items[0]) return 2; items[0]=(char)-7; int '
                                        'result=verify(&items[0],items[0]); return result==42 && items[0]==0?42:3; }',
 'const unknown array has exactly one zero element': 'const int items[]; extern int inspect(void); int main(void) { '
                                                     'return items[0]==0?inspect():1; }',
 'earlier decay then visible known outer completion': 'int items[]; int *earlier(void) { return items; } extern int '
                                                      'items[3]; int main(void) { if(sizeof items!=12 || items[0] || '
                                                      'items[1] || items[2]) return 1; items[2]=42; return '
                                                      'earlier()==items?earlier()[2]:2; }',
 'earlier unknown array query preserves pointer identity after completion': 'int items[]; typedef typeof(items) Saved; '
                                                                            'Saved *earlier(void) { return &items; } '
                                                                            'extern int items[3]; int main(void) { '
                                                                            'if(sizeof items!=12 || items[2]) return '
                                                                            '1; items[2]=42; return '
                                                                            'earlier()==&items?(*earlier())[2]:2; }',
 'fixed rows use row and whole-array strides without crossing subarrays': 'int rows[2][3]; int main(void) { int '
                                                                          '(*p)[3]=rows; int (*whole)[2][3]=&rows; '
                                                                          'if(sizeof rows!=24 || sizeof rows[0]!=12 || '
                                                                          'p+1!=&rows[1] || whole+1-whole!=1) return '
                                                                          '1; if(rows[0][2] || rows[1][2]) return 2; '
                                                                          'rows[1][2]=42; return (*whole)[1][2]; }',
 'int unknown final one companion driver': 'extern int items[]; int items[]; int items[]; int get(void) { return '
                                           'items[0]; } void put(int x) { items[0]=x; } int *elements(void) { return '
                                           'items; } int (*whole(void))[] { return &items; }',
 'int unknown final one owner driver': 'int items[]; extern int items[]; int items[]; extern int verify(int *,int); '
                                       'int main(void) { if(items[0]!=0) return 1; int (*whole)[]=&items; '
                                       'if((*whole)+0!=&items[0]) return 2; items[0]=(int)-1234567; int '
                                       'result=verify(&items[0],items[0]); return result==42 && items[0]==0?42:3; }',
 'long long unknown final one companion driver': 'extern long long items[]; long long items[]; long long items[]; long '
                                                 'long get(void) { return items[0]; } void put(long long x) { '
                                                 'items[0]=x; } long long *elements(void) { return items; } long long '
                                                 '(*whole(void))[] { return &items; }',
 'long long unknown final one owner driver': 'long long items[]; extern long long items[]; long long items[]; extern '
                                             'int verify(long long *,long long); int main(void) { if(items[0]!=0) '
                                             'return 1; long long (*whole)[]=&items; if((*whole)+0!=&items[0]) return '
                                             '2; items[0]=(long long)4611686018427387904LL; int '
                                             'result=verify(&items[0],items[0]); return result==42 && '
                                             'items[0]==0?42:3; }',
 'long unknown final one companion driver': 'extern long items[]; long items[]; long items[]; long get(void) { return '
                                            'items[0]; } void put(long x) { items[0]=x; } long *elements(void) { '
                                            'return items; } long (*whole(void))[] { return &items; }',
 'long unknown final one owner driver': 'long items[]; extern long items[]; long items[]; extern int verify(long '
                                        '*,long); int main(void) { if(items[0]!=0) return 1; long (*whole)[]=&items; '
                                        'if((*whole)+0!=&items[0]) return 2; items[0]=(long)4294967296L; int '
                                        'result=verify(&items[0],items[0]); return result==42 && items[0]==0?42:3; }',
 'short unknown final one companion driver': 'extern short items[]; short items[]; short items[]; short get(void) { '
                                             'return items[0]; } void put(short x) { items[0]=x; } short '
                                             '*elements(void) { return items; } short (*whole(void))[] { return '
                                             '&items; }',
 'short unknown final one owner driver': 'short items[]; extern short items[]; short items[]; extern int verify(short '
                                         '*,short); int main(void) { if(items[0]!=0) return 1; short '
                                         '(*whole)[]=&items; if((*whole)+0!=&items[0]) return 2; '
                                         'items[0]=(short)-1234; int result=verify(&items[0],items[0]); return '
                                         'result==42 && items[0]==0?42:3; }',
 'signed char unknown final one companion driver': 'extern signed char items[]; signed char items[]; signed char '
                                                   'items[]; signed char get(void) { return items[0]; } void '
                                                   'put(signed char x) { items[0]=x; } signed char *elements(void) { '
                                                   'return items; } signed char (*whole(void))[] { return &items; }',
 'signed char unknown final one owner driver': 'signed char items[]; extern signed char items[]; signed char items[]; '
                                               'extern int verify(signed char *,signed char); int main(void) { '
                                               'if(items[0]!=0) return 1; signed char (*whole)[]=&items; '
                                               'if((*whole)+0!=&items[0]) return 2; items[0]=(signed char)-7; int '
                                               'result=verify(&items[0],items[0]); return result==42 && '
                                               'items[0]==0?42:3; }',
 'unknown callback array null checked before sole-slot assignment': 'int (*items[])(int); extern int plus(int); int '
                                                                    'main(void) { if(items[0]) return 1; '
                                                                    'items[0]=plus; int result=items[0](40); '
                                                                    'items[0]=0; return result; }',
 'unknown nullptr array has one zero/null element': 'typeof(nullptr) items[]; extern int inspect(void); int main(void) '
                                                    '{ if(items[0]!=nullptr) return 1; int *p=items[0]; '
                                                    'items[0]=nullptr; return !p?inspect():2; }',
 'unknown outer row finalizes to exactly one complete row': 'int rows[][3]; int main(void) { if(rows[0][0] || '
                                                            'rows[0][1] || rows[0][2]) return 1; int (*p)[3]=rows; '
                                                            'if(sizeof rows[0]!=12 || p+1-p!=1) return 2; '
                                                            'rows[0][2]=42; return p[0][2]; }',
 'unknown pointer array companion writes only sole element': 'int *items[]; int **elements(void) { return items; } int '
                                                             'get(void) { return *items[0]; }',
 'unknown rows gain two rows before runtime second-row access': 'int rows[][3]; int (*earlier(void))[3] { return rows; '
                                                                '} extern int rows[2][3]; int main(void) { if(sizeof '
                                                                'rows!=24 || rows[1][2]) return 1; rows[1][2]=42; '
                                                                'return earlier()[1][2]; }',
 'unknown typedef root owns one final element': 'typedef int Unknown[]; Unknown items; int main(void) { if(items[0]) '
                                                'return 1; items[0]=42; return items[0]; }',
 'unknown void callback array assigned before call': 'void (*items[])(int *); extern void set(int *); int main(void) { '
                                                     'if(items[0]) return 1; int value=0; items[0]=set; '
                                                     'items[0](&value); items[0]=0; return value; }',
 'unsigned char unknown final one companion driver': 'extern unsigned char items[]; unsigned char items[]; unsigned '
                                                     'char items[]; unsigned char get(void) { return items[0]; } void '
                                                     'put(unsigned char x) { items[0]=x; } unsigned char '
                                                     '*elements(void) { return items; } unsigned char (*whole(void))[] '
                                                     '{ return &items; }',
 'unsigned char unknown final one owner driver': 'unsigned char items[]; extern unsigned char items[]; unsigned char '
                                                 'items[]; extern int verify(unsigned char *,unsigned char); int '
                                                 'main(void) { if(items[0]!=0) return 1; unsigned char '
                                                 '(*whole)[]=&items; if((*whole)+0!=&items[0]) return 2; '
                                                 'items[0]=(unsigned char)255; int result=verify(&items[0],items[0]); '
                                                 'return result==42 && items[0]==0?42:3; }',
 'unsigned long long unknown final one companion driver': 'extern unsigned long long items[]; unsigned long long '
                                                          'items[]; unsigned long long items[]; unsigned long long '
                                                          'get(void) { return items[0]; } void put(unsigned long long '
                                                          'x) { items[0]=x; } unsigned long long *elements(void) { '
                                                          'return items; } unsigned long long (*whole(void))[] { '
                                                          'return &items; }',
 'unsigned long long unknown final one owner driver': 'unsigned long long items[]; extern unsigned long long items[]; '
                                                      'unsigned long long items[]; extern int verify(unsigned long '
                                                      'long *,unsigned long long); int main(void) { if(items[0]!=0) '
                                                      'return 1; unsigned long long (*whole)[]=&items; '
                                                      'if((*whole)+0!=&items[0]) return 2; items[0]=(unsigned long '
                                                      'long)18446744073709551615ULL; int '
                                                      'result=verify(&items[0],items[0]); return result==42 && '
                                                      'items[0]==0?42:3; }',
 'unsigned long unknown final one companion driver': 'extern unsigned long items[]; unsigned long items[]; unsigned '
                                                     'long items[]; unsigned long get(void) { return items[0]; } void '
                                                     'put(unsigned long x) { items[0]=x; } unsigned long '
                                                     '*elements(void) { return items; } unsigned long (*whole(void))[] '
                                                     '{ return &items; }',
 'unsigned long unknown final one owner driver': 'unsigned long items[]; extern unsigned long items[]; unsigned long '
                                                 'items[]; extern int verify(unsigned long *,unsigned long); int '
                                                 'main(void) { if(items[0]!=0) return 1; unsigned long '
                                                 '(*whole)[]=&items; if((*whole)+0!=&items[0]) return 2; '
                                                 'items[0]=(unsigned long)18446744073709551615UL; int '
                                                 'result=verify(&items[0],items[0]); return result==42 && '
                                                 'items[0]==0?42:3; }',
 'unsigned short unknown final one companion driver': 'extern unsigned short items[]; unsigned short items[]; unsigned '
                                                      'short items[]; unsigned short get(void) { return items[0]; } '
                                                      'void put(unsigned short x) { items[0]=x; } unsigned short '
                                                      '*elements(void) { return items; } unsigned short '
                                                      '(*whole(void))[] { return &items; }',
 'unsigned short unknown final one owner driver': 'unsigned short items[]; extern unsigned short items[]; unsigned '
                                                  'short items[]; extern int verify(unsigned short *,unsigned short); '
                                                  'int main(void) { if(items[0]!=0) return 1; unsigned short '
                                                  '(*whole)[]=&items; if((*whole)+0!=&items[0]) return 2; '
                                                  'items[0]=(unsigned short)65535; int '
                                                  'result=verify(&items[0],items[0]); return result==42 && '
                                                  'items[0]==0?42:3; }',
 'unsigned unknown final one companion driver': 'extern unsigned items[]; unsigned items[]; unsigned items[]; unsigned '
                                                'get(void) { return items[0]; } void put(unsigned x) { items[0]=x; } '
                                                'unsigned *elements(void) { return items; } unsigned (*whole(void))[] '
                                                '{ return &items; }',
 'unsigned unknown final one owner driver': 'unsigned items[]; extern unsigned items[]; unsigned items[]; extern int '
                                            'verify(unsigned *,unsigned); int main(void) { if(items[0]!=0) return 1; '
                                            'unsigned (*whole)[]=&items; if((*whole)+0!=&items[0]) return 2; '
                                            'items[0]=(unsigned)4294967295U; int result=verify(&items[0],items[0]); '
                                            'return result==42 && items[0]==0?42:3; }'}

AUDITED_NATIVE_METADATA = {'_Bool unknown final one companion driver': {'items': (1, 1)},
 '_Bool unknown final one owner driver': {'items': (1, 1)},
 'captured unknown alias independently finalizes separate object to one': {'items': (12, 4), 'other': (4, 4)},
 'char unknown final one companion driver': {'items': (1, 1)},
 'char unknown final one owner driver': {'items': (1, 1)},
 'const unknown array has exactly one zero element': {'items': (4, 4)},
 'earlier decay then visible known outer completion': {'items': (12, 4)},
 'earlier unknown array query preserves pointer identity after completion': {'items': (12, 4)},
 'fixed rows use row and whole-array strides without crossing subarrays': {'rows': (24, 4)},
 'int unknown final one companion driver': {'items': (4, 4)},
 'int unknown final one owner driver': {'items': (4, 4)},
 'long long unknown final one companion driver': {'items': (8, 8)},
 'long long unknown final one owner driver': {'items': (8, 8)},
 'long unknown final one companion driver': {'items': (8, 8)},
 'long unknown final one owner driver': {'items': (8, 8)},
 'short unknown final one companion driver': {'items': (2, 2)},
 'short unknown final one owner driver': {'items': (2, 2)},
 'signed char unknown final one companion driver': {'items': (1, 1)},
 'signed char unknown final one owner driver': {'items': (1, 1)},
 'unknown callback array null checked before sole-slot assignment': {'items': (8, 8)},
 'unknown nullptr array has one zero/null element': {'items': (8, 8)},
 'unknown outer row finalizes to exactly one complete row': {'rows': (12, 4)},
 'unknown pointer array companion writes only sole element': {'items': (8, 8)},
 'unknown rows gain two rows before runtime second-row access': {'rows': (24, 4)},
 'unknown typedef root owns one final element': {'items': (4, 4)},
 'unknown void callback array assigned before call': {'items': (8, 8)},
 'unsigned char unknown final one companion driver': {'items': (1, 1)},
 'unsigned char unknown final one owner driver': {'items': (1, 1)},
 'unsigned long long unknown final one companion driver': {'items': (8, 8)},
 'unsigned long long unknown final one owner driver': {'items': (8, 8)},
 'unsigned long unknown final one companion driver': {'items': (8, 8)},
 'unsigned long unknown final one owner driver': {'items': (8, 8)},
 'unsigned short unknown final one companion driver': {'items': (2, 2)},
 'unsigned short unknown final one owner driver': {'items': (2, 2)},
 'unsigned unknown final one companion driver': {'items': (4, 4)},
 'unsigned unknown final one owner driver': {'items': (4, 4)}}

AUDITED_DIAGNOSTIC_RECORDS = {'records_1': (('warning', "array 'items' assumed to have one element"),),
 'records_2': (('warning', "array 'rows' assumed to have one element"),),
 'records_3': (('warning', "array 'other' assumed to have one element"),),
 'records_4': (('warning', 'tentative array definition assumed to have one element'),),
 'records_5': (('warning', 'tentative array definition assumed to have one element'),
               ('warning', 'tentative array definition assumed to have one element')),
 'records_6': (('warning', "use of logical '||' with constant operand [-Wconstant-logical-operand]"),
               ('note', "use '|' for a bitwise operation"))}

AUDITED_NATIVE_CASES = {'clang': {'_Bool unknown final one companion driver': ('final_one_warning', 'records_4', None),
           '_Bool unknown final one owner driver': ('final_one_warning', 'records_4', None),
           'captured unknown alias independently finalizes separate object to one': ('completed_bound_warning',
                                                                                     'records_5',
                                                                                     (('B', 'items', 4),
                                                                                      ('B', 'other', 4))),
           'char unknown final one companion driver': ('final_one_warning', 'records_4', None),
           'char unknown final one owner driver': ('final_one_warning', 'records_4', None),
           'const unknown array has exactly one zero element': ('final_one_warning', 'records_4', None),
           'earlier decay then visible known outer completion': ('completed_bound_warning',
                                                                 'records_4',
                                                                 (('B', 'items', 4),)),
           'earlier unknown array query preserves pointer identity after completion': ('completed_bound_warning',
                                                                                       'records_4',
                                                                                       (('B', 'items', 4),)),
           'fixed rows use row and whole-array strides without crossing subarrays': ('legacy_logical_warning',
                                                                                     'records_6',
                                                                                     None),
           'int unknown final one companion driver': ('final_one_warning', 'records_4', None),
           'int unknown final one owner driver': ('final_one_warning', 'records_4', None),
           'long long unknown final one companion driver': ('final_one_warning', 'records_4', None),
           'long long unknown final one owner driver': ('final_one_warning', 'records_4', None),
           'long unknown final one companion driver': ('final_one_warning', 'records_4', None),
           'long unknown final one owner driver': ('final_one_warning', 'records_4', None),
           'short unknown final one companion driver': ('final_one_warning', 'records_4', None),
           'short unknown final one owner driver': ('final_one_warning', 'records_4', None),
           'signed char unknown final one companion driver': ('final_one_warning', 'records_4', None),
           'signed char unknown final one owner driver': ('final_one_warning', 'records_4', None),
           'unknown callback array null checked before sole-slot assignment': ('final_one_warning', 'records_4', None),
           'unknown nullptr array has one zero/null element': ('final_one_warning', 'records_4', None),
           'unknown outer row finalizes to exactly one complete row': ('final_one_warning', 'records_4', None),
           'unknown pointer array companion writes only sole element': ('final_one_warning', 'records_4', None),
           'unknown rows gain two rows before runtime second-row access': ('completed_bound_warning',
                                                                           'records_4',
                                                                           (('B', 'rows', 12),)),
           'unknown typedef root owns one final element': ('final_one_warning', 'records_4', None),
           'unknown void callback array assigned before call': ('final_one_warning', 'records_4', None),
           'unsigned char unknown final one companion driver': ('final_one_warning', 'records_4', None),
           'unsigned char unknown final one owner driver': ('final_one_warning', 'records_4', None),
           'unsigned long long unknown final one companion driver': ('final_one_warning', 'records_4', None),
           'unsigned long long unknown final one owner driver': ('final_one_warning', 'records_4', None),
           'unsigned long unknown final one companion driver': ('final_one_warning', 'records_4', None),
           'unsigned long unknown final one owner driver': ('final_one_warning', 'records_4', None),
           'unsigned short unknown final one companion driver': ('final_one_warning', 'records_4', None),
           'unsigned short unknown final one owner driver': ('final_one_warning', 'records_4', None),
           'unsigned unknown final one companion driver': ('final_one_warning', 'records_4', None),
           'unsigned unknown final one owner driver': ('final_one_warning', 'records_4', None)},
 'gcc': {'_Bool unknown final one companion driver': ('final_one_warning', 'records_1', None),
         '_Bool unknown final one owner driver': ('final_one_warning', 'records_1', None),
         'captured unknown alias independently finalizes separate object to one': ('final_one_warning',
                                                                                   'records_3',
                                                                                   None),
         'char unknown final one companion driver': ('final_one_warning', 'records_1', None),
         'char unknown final one owner driver': ('final_one_warning', 'records_1', None),
         'const unknown array has exactly one zero element': ('final_one_warning', 'records_1', None),
         'int unknown final one companion driver': ('final_one_warning', 'records_1', None),
         'int unknown final one owner driver': ('final_one_warning', 'records_1', None),
         'long long unknown final one companion driver': ('final_one_warning', 'records_1', None),
         'long long unknown final one owner driver': ('final_one_warning', 'records_1', None),
         'long unknown final one companion driver': ('final_one_warning', 'records_1', None),
         'long unknown final one owner driver': ('final_one_warning', 'records_1', None),
         'short unknown final one companion driver': ('final_one_warning', 'records_1', None),
         'short unknown final one owner driver': ('final_one_warning', 'records_1', None),
         'signed char unknown final one companion driver': ('final_one_warning', 'records_1', None),
         'signed char unknown final one owner driver': ('final_one_warning', 'records_1', None),
         'unknown callback array null checked before sole-slot assignment': ('final_one_warning', 'records_1', None),
         'unknown nullptr array has one zero/null element': ('final_one_warning', 'records_1', None),
         'unknown outer row finalizes to exactly one complete row': ('final_one_warning', 'records_2', None),
         'unknown pointer array companion writes only sole element': ('final_one_warning', 'records_1', None),
         'unknown typedef root owns one final element': ('final_one_warning', 'records_1', None),
         'unknown void callback array assigned before call': ('final_one_warning', 'records_1', None),
         'unsigned char unknown final one companion driver': ('final_one_warning', 'records_1', None),
         'unsigned char unknown final one owner driver': ('final_one_warning', 'records_1', None),
         'unsigned long long unknown final one companion driver': ('final_one_warning', 'records_1', None),
         'unsigned long long unknown final one owner driver': ('final_one_warning', 'records_1', None),
         'unsigned long unknown final one companion driver': ('final_one_warning', 'records_1', None),
         'unsigned long unknown final one owner driver': ('final_one_warning', 'records_1', None),
         'unsigned short unknown final one companion driver': ('final_one_warning', 'records_1', None),
         'unsigned short unknown final one owner driver': ('final_one_warning', 'records_1', None),
         'unsigned unknown final one companion driver': ('final_one_warning', 'records_1', None),
         'unsigned unknown final one owner driver': ('final_one_warning', 'records_1', None)}}

def native_identity_from_macros(result):
    """Preprocessing-only family/target evidence, not executable-name inference."""
    if result.returncode != 0 or result.stderr != '':
        return None
    macros = {}
    for line in result.stdout.splitlines():
        match = re.fullmatch(r'#define ([A-Za-z_][A-Za-z_0-9]*) (.+)', line)
        if match:
            name, value = match.groups()
            if name in macros:
                return None
            macros[name] = value
    # Reject other known GNU-emulating frontends; no generic GNU-macro waiver.
    if any(name in macros for name in ['__INTEL_COMPILER', '__INTEL_LLVM_COMPILER',
                                       '__NVCOMPILER', '__TINYC__', '__PCC__']):
        return None
    def positive(name):
        return macros.get(name, '').isdigit() and int(macros[name]) > 0
    if macros.get('__clang__') == '1' and positive('__clang_major__') and positive('__GNUC__'):
        family = 'clang'
    elif '__clang__' not in macros and positive('__GNUC__'):
        family = 'gcc'
    else:
        return None
    expected = {'__linux__': '1', '__ELF__': '1', '__x86_64__': '1', '__LP64__': '1',
                '__CHAR_BIT__': '8', '__SIZEOF_SHORT__': '2', '__SIZEOF_INT__': '4',
                '__SIZEOF_LONG__': '8', '__SIZEOF_LONG_LONG__': '8', '__SIZEOF_POINTER__': '8',
                '__ORDER_LITTLE_ENDIAN__': '1234'}
    if any(macros.get(name) != value for name, value in expected.items()):
        return None
    if '__CHAR_UNSIGNED__' in macros or macros.get('__BYTE_ORDER__') not in ['__ORDER_LITTLE_ENDIAN__', '1234']:
        return None
    return family, NATIVE_TARGET


def parse_nm_records(text):
    records = []
    try:
        for line in text.splitlines():
            parts = line.split()
            if not parts:
                continue
            if len(parts) == 4:
                records.append((parts[-2], parts[-1], int(parts[-3], 16)))
            elif len(parts) in [2, 3]:
                # QBE data symbols may lack ELF .size metadata. None is NOT
                # acceptable for native owners; their strict size guard stays.
                records.append((parts[-2], parts[-1], None))
            else:
                return None
    except ValueError:
        return None
    return records


# R is permitted only for these independently frozen, exact-source const-owned
# fixtures and their exact ownership metadata. Do not infer const by symbol name,
# pointer pointee qualification, diagnostic category or a substring of the source.
CONST_OWNED_ORIGINALS = {'const int items[3]; const int (*whole(void))[3] { return &items; }': {'items': (12, 4)},
 'const int items[]; extern int inspect(void); int main(void) { return items[0]==0?inspect():1; }': {'items': (4,
                                                                                                               4)},
 'int *const items[2]; extern int inspect(void); int main(void) { return !items[0] && !items[1]?inspect():1; }': {'items': (16,
                                                                                                                            8)}}


def owned_symbols_are_known(owned, records):
    return records is not None and bool(owned) and not any(
        kind in ['B', 'D', 'R', 'C'] and name not in owned for kind, name, size in records)


def owned_layout_matches(text, owned, records):
    """One pure guard for clean owners, warning owners and kcc objects alike."""
    if not owned_symbols_are_known(owned, records):
        return False
    const_metadata = CONST_OWNED_ORIGINALS.get(text)
    if const_metadata is not None and owned != const_metadata:
        return False
    readonly = set(const_metadata) if const_metadata is not None else set()
    for name, (size, alignment) in owned.items():
        found = [(kind, actual_size) for kind, symbol, actual_size in records if symbol == name]
        allowed = ['B', 'D', 'R'] if name in readonly else ['B', 'D']
        if len(found) != 1 or found[0][0] not in allowed or found[0][1] != size:
            return False
    return True


def check_qbe_owned_storage(assembly_text, owned):
    # QBE 1.2 omits ELF data .size, so nm -S cannot establish byte extent.
    # Verify the ACTUAL emitted zero allocation/alignment before supplying its
    # size to the shared guard. Native objects NEVER use this alternate path.
    for name, (size, alignment) in owned.items():
        expected = (f'.bss\n.balign {alignment}\n.globl {name}\n{name}:\n'
                    f'\t.fill {size},1,0\n/* end data */')
        assert assembly_text.count(expected) == 1, (name, expected, assembly_text)


def check_qbe_bss_evidence(assembly_text, nm_text, section_text, owned):
    check_qbe_owned_storage(assembly_text, owned)
    assert len(re.findall(r'^\.bss$', assembly_text, re.M)) == len(owned), assembly_text
    assert len(re.findall(r'^\s*\.fill\b', assembly_text, re.M)) == len(owned), assembly_text
    order = sorted(owned, key=lambda name: assembly_text.index(f'\n{name}:\n'))
    addresses = {}
    records = parse_nm_records(nm_text)
    assert records is not None and owned_symbols_are_known(owned, records), nm_text
    for line in nm_text.splitlines():
        parts = line.split()
        if parts and parts[-1] in owned:
            name = parts[-1]
            assert len(parts) in [3, 4] and parts[-2] == 'B' and name not in addresses, nm_text
            addresses[name] = int(parts[0], 16)
            if len(parts) == 4:
                assert int(parts[-3], 16) == owned[name][0], nm_text
    cursor = 0
    for name in order:
        size, alignment = owned[name]
        cursor = (cursor+alignment-1)//alignment*alignment
        assert addresses.get(name) == cursor, (name, cursor, nm_text)
        cursor += size
    section_rows = [re.fullmatch(
        r'\s*\[\s*\d+\]\s+\.bss\s+NOBITS\s+[0-9a-fA-F]+\s+[0-9a-fA-F]+\s+'
        r'([0-9a-fA-F]+)\s+\S+\s+(\S+)\s+\d+\s+\d+\s+(\d+)\s*', line)
        for line in section_text.splitlines()]
    section_rows = [row for row in section_rows if row is not None]
    assert len(section_rows) == 1, section_text
    section_size, flags, section_alignment = section_rows[0].groups()
    assert int(section_size, 16) == cursor and 'W' in flags and 'A' in flags, section_text
    assert int(section_alignment) >= max(alignment for size, alignment in owned.values()), section_text
    # Only after exact directives + B symbols/offsets + ELF NOBITS extent agree
    # may missing QBE .size values be filled for the common ownership predicate.
    return [(kind, name, owned[name][0]) if name in owned and size is None
            else (kind, name, size) for kind, name, size in records]


def check_qbe_bss_controls():
    owned = {'first': (3, 1), 'second': (16, 8), 'third': (12, 4)}
    assembly_text = ''.join(f'.bss\n.balign {alignment}\n.globl {name}\n{name}:\n'
                            f'\t.fill {size},1,0\n/* end data */\n\n'
                            for name, (size, alignment) in owned.items())
    nm_text = '00000000 B first\n00000008 B second\n00000018 B third\n'
    section_text = '  [ 3] .bss NOBITS 00000000 000040 000024 00 WA 0 0 8\n'
    records = check_qbe_bss_evidence(assembly_text, nm_text, section_text, owned)
    assert owned_layout_matches('synthetic mutable layout controls', owned, records)
    variants = [(assembly_text.replace('.fill 16,1,0', '.fill 8,1,0'), nm_text, section_text),
                (assembly_text.replace('.balign 8', '.balign 4'), nm_text, section_text),
                (assembly_text, nm_text.replace('00000008', '00000003'), section_text),
                (assembly_text, nm_text.replace('B second', 'R second'), section_text),
                (assembly_text, nm_text+'00000000 B first\n', section_text),
                (assembly_text, nm_text+'00000000 B unknown\n', section_text),
                (assembly_text, nm_text.replace('00000008 B second', '00000008 00000008 B second'), section_text),
                (assembly_text, nm_text, section_text.replace('000024', '000023')),
                (assembly_text, nm_text, section_text.replace('WA 0 0 8', 'WA 0 0 1')),
                (assembly_text, nm_text, '')]
    for changed_assembly, changed_nm, changed_sections in variants:
        try:
            check_qbe_bss_evidence(changed_assembly, changed_nm, changed_sections, owned)
        except AssertionError:
            pass
        else:
            raise AssertionError('QBE BSS evidence negative control accepted')


def check_owned_layout_controls():
    # Clean-path regression: the diagnostic classifier is not involved here.
    mutable_source = 'int mutable[1];'
    mutable_owned = {'mutable': (4, 4)}
    for kind in ['B', 'D']:
        assert owned_layout_matches(mutable_source, mutable_owned, [(kind, 'mutable', 4)])
    for kind in ['R', 'C', 'U']:
        assert not owned_layout_matches(mutable_source, mutable_owned, [(kind, 'mutable', 4)])
    for text, owned in CONST_OWNED_ORIGINALS.items():
        name = next(iter(owned))
        size, alignment = owned[name]
        for kind in ['B', 'D', 'R']:
            assert owned_layout_matches(text, owned, [(kind, name, size)])
        for records in [[('R', name, size), ('R', name, size)], [('R', name, size+1)],
                        [('R', 'misplaced_const', size)], [('R', name, size), ('B', 'unknown', 4)],
                        [('U', name, None)], [('C', name, size)], []]:
            assert not owned_layout_matches(text, owned, records)
        assert not owned_layout_matches(text+' ', owned, [('R', name, size)])
        assert not owned_layout_matches(mutable_source, {name: (size, alignment)}, [('R', name, size)])
        assert not owned_layout_matches(text, {'misplaced_const': (size, alignment)}, [('R', 'misplaced_const', size)])
        assert not owned_layout_matches(text, {**owned, 'mutable': (4, 4)}, [('R', name, size), ('R', 'mutable', 4)])
    assert not owned_layout_matches(mutable_source, mutable_owned, [('B', 'mutable', 8)])
    assert not owned_layout_matches(mutable_source, mutable_owned, [('B', 'mutable', 4), ('D', 'mutable', 4)])
    assert not owned_layout_matches(mutable_source, mutable_owned, [('B', 'mutable', 4), ('R', 'unknown', 4)])
    assert not owned_layout_matches(mutable_source, {}, [])
    assert not owned_layout_matches(mutable_source, mutable_owned, None)
    assert not owned_layout_matches(mutable_source, mutable_owned, [('B', 'mutable', None)])


def classify_native_diagnostic(family, target, flags, text, result,
                               owned, object_exists, object_bytes, nm_result):
    if family not in AUDITED_NATIVE_CASES or target != NATIVE_TARGET or tuple(flags) != NATIVE_OBJECT_FLAGS:
        return None
    name = next((name for name, original in AUDITED_NATIVE_SOURCES.items() if text == original), None)
    case = AUDITED_NATIVE_CASES[family].get(name)
    if case is None or owned != AUDITED_NATIVE_METADATA[name]:
        return None
    benign_category, record_id, known_undersized_layout = case
    if (result.returncode != 0 or result.stdout != '' or not object_exists or object_bytes <= 0 or
            tuple(diagnostic_records(result.stderr)) != AUDITED_DIAGNOSTIC_RECORDS[record_id] or
            nm_result.returncode != 0 or nm_result.stderr != ''):
        return None
    records = parse_nm_records(nm_result.stdout)
    if records is None:
        return None
    observed = tuple(sorted(record for record in records if record[1] in owned))
    if not owned_symbols_are_known(owned, records):
        return None
    if owned_layout_matches(text, owned, records):
        return benign_category  # Including a future correctly completed Clang array.
    if known_undersized_layout is not None and observed == known_undersized_layout:
        return 'layout_gap'  # Exact known defect; NEVER a native agreement or execution.
    return None


def check_native_diagnostic_controls(family, target, flags, text, result,
                                     owned, object_exists, object_bytes, nm_result):
    args = [family, target, flags, text, result, owned, object_exists, object_bytes, nm_result]
    assert classify_native_diagnostic(*args) is not None

    def reject(index, replacement):
        changed = args.copy()
        changed[index] = replacement
        assert classify_native_diagnostic(*changed) is None, (index, replacement)

    reject(0, 'unknown-family')
    reject(1, 'unknown-target')
    for changed_flags in [(), flags[:-1], (*flags, '-O2'), (*flags[:-1], '-fsyntax-only')]:
        reject(2, changed_flags)
    for changed_source in ['int unrelated;', text+' ', text+'\n']:
        reject(3, changed_source)
    for status in [1, 2, 127, -6, -9, -11]:
        reject(4, subprocess.CompletedProcess([], status, '', result.stderr))
    reject(4, subprocess.CompletedProcess([], 0, 'unexpected stdout', result.stderr))
    for extra in ['error: extra', 'warning: extra', 'note: extra', 'fatal error: extra']:
        reject(4, subprocess.CompletedProcess([], 0, '', result.stderr+'\n'+extra))
    records = diagnostic_records(result.stderr)
    for omitted in range(len(records)):
        missing = '\n'.join(f'{kind}: {message}' for i, (kind, message) in enumerate(records) if i != omitted)
        reject(4, subprocess.CompletedProcess([], 0, '', missing))
    reversed_records = list(reversed(records))
    if reversed_records != records:
        reordered = '\n'.join(f'{kind}: {message}' for kind, message in reversed_records)
        reject(4, subprocess.CompletedProcess([], 0, '', reordered))
    reject(4, subprocess.CompletedProcess([], 0, '', result.stderr+result.stderr))
    reject(6, False)
    reject(7, 0)
    reject(8, subprocess.CompletedProcess([], 1, nm_result.stdout, ''))
    reject(8, subprocess.CompletedProcess([], 0, nm_result.stdout, 'unexpected nm diagnostic'))
    reject(8, subprocess.CompletedProcess([], 0, '', ''))
    reject(8, subprocess.CompletedProcess([], 0, nm_result.stdout+'00000000 00000004 B unknown_owner\n', ''))
    owned_records = [record for record in parse_nm_records(nm_result.stdout) if record[1] in owned]
    kind, name, size = owned_records[0]
    assert size is not None
    line = f'00000000 {size:08x} {kind} {name}\n'
    reject(8, subprocess.CompletedProcess([], 0, nm_result.stdout+line, ''))
    for changed_kind, changed_name, changed_size in [('C', name, size), ('U', name, size),
                                                   (kind, name, size+1), (kind, 'wrong_symbol', size)]:
        changed = [(changed_kind, changed_name, changed_size), *owned_records[1:]]
        output = ''.join(f'00000000 {count:08x} {tag} {symbol}\n' for tag, symbol, count in changed)
        reject(8, subprocess.CompletedProcess([], 0, output, ''))
    # A corrected layout is NOT the old bug. Same exact valid source/full records
    # plus every correct owned layout qualifies only for the benign alternative.
    expected_size, alignment = owned[name]
    if size != expected_size:
        corrected = [(kind, name, expected_size), *owned_records[1:]]
        output = ''.join(f'00000000 {count:08x} {tag} {symbol}\n' for tag, symbol, count in corrected)
        corrected_args = args.copy()
        corrected_args[8] = subprocess.CompletedProcess([], 0, output, '')
        assert classify_native_diagnostic(*corrected_args) == 'completed_bound_warning'
    if len(owned_records) > 1:
        missing = ''.join(f'00000000 {count:08x} {tag} {symbol}\n' for tag, symbol, count in owned_records[1:])
        reject(8, subprocess.CompletedProcess([], 0, missing, ''))
    wrong_metadata = owned.copy()
    wrong_metadata[name] = (expected_size+1, alignment)
    reject(5, wrong_metadata)
    wrong_metadata[name] = (expected_size, alignment+1)
    reject(5, wrong_metadata)


check_owned_layout_controls()
check_qbe_bss_controls()


with tempfile.TemporaryDirectory(prefix='kcc tentative arrays ') as directory:
    directory = Path(directory)
    source, companion, il, assembly, native_obj, companion_obj, kcc_obj, executable = [directory/n for n in
        ('owner.c', 'companion.c', 'p.ssa', 'p.s', 'native-owner.o', 'companion.o', 'kcc-owner.o', 'program')]

    def invoke(args):
        return subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=15)

    def compile_source(text, success=True, message=None):
        source.write_text(text+'\n')
        result = invoke([compiler, source])
        if success:
            assert result.returncode == 0 and not result.stderr, (text[:1800], result.stderr)
            if qbe:
                il.write_text(result.stdout)
                assembly.unlink(missing_ok=True)
                translated = invoke([qbe, '-t', 'amd64_sysv', '-o', assembly, il])
                assert translated.returncode == 0 and assembly.is_file(), translated.stderr
                assert not re.search(r'^\s*\.(?:comm|lcomm)\b', assembly.read_text(), re.M), assembly.read_text()
        else:
            assert result.returncode == 1 and not result.stdout and 'error:' in result.stderr, (text[:1800], result.stderr)
            assert str(source)+':' in result.stderr, result.stderr
            if message is not None:
                assert message in result.stderr, (text[:1800], message, result.stderr)
        return result.stdout

    def check_layout(emitted, owned):
        for name, (size, alignment) in owned.items():
            assert len(re.findall(r'\bdata \$'+re.escape(name)+r'\b', emitted)) == 1, (name, emitted)
            expected = f'export data ${name} = align {alignment} {{ z {size} }}'
            assert expected in emitted.splitlines(), (name, expected, emitted)

    def native_compile(path, output, owned=None):
        output.unlink(missing_ok=True)  # Success/existence must refer to THIS invocation.
        result = invoke([host, *NATIVE_OBJECT_FLAGS, path, '-o', output])
        assert result.returncode == 0 and result.stdout == '' and output.is_file() and output.stat().st_size > 0, (path.read_text(), result.stderr)
        category = None
        if owned is not None:
            nm_result = invoke(['nm', '-S', output])
            classifier_args = (native_family, native_target, NATIVE_OBJECT_FLAGS,
                               path.read_text().removesuffix('\n'), result, owned,
                               output.is_file(), output.stat().st_size, nm_result)
            category = classify_native_diagnostic(*classifier_args)
            if category is not None:
                check_native_diagnostic_controls(*classifier_args)
            if category == 'layout_gap':
                return category  # No link/run and no agreement for this native object.
        if category is None:
            assert not diagnostic_records(result.stderr), ('unaudited native diagnostic', path.read_text(), result.stderr)
            category = 'clean'
        if owned is not None:
            owned_once(output, owned)  # Mandatory even for audited benign warnings.
        return category

    def symbols(path):
        result = invoke(['nm', '-S', path])
        assert result.returncode == 0, result.stderr
        records = parse_nm_records(result.stdout)
        assert records is not None, result.stdout
        return records

    def owned_once(path, owned, qbe_assembly=None):
        if qbe_assembly is None:
            records = symbols(path)  # Native nm-S sizes remain mandatory.
        else:
            nm_result = invoke(['nm', '-S', path])
            sections = invoke(['readelf', '-SW', path])
            assert nm_result.returncode == 0 and not nm_result.stderr, nm_result.stderr
            assert sections.returncode == 0 and not sections.stderr, sections.stderr
            records = check_qbe_bss_evidence(qbe_assembly.read_text(), nm_result.stdout, sections.stdout, owned)
        text = source.read_text().removesuffix('\n')
        assert owned_layout_matches(text, owned, records), (text, owned, records)
        return records

    def companion_declares_only(path, owned):
        records = symbols(path)
        for kind, name, size in records:
            if name in owned:
                assert kind == 'U', (name, records)

    def link_run(objects):
        result = invoke([host, *objects, '-o', executable])
        assert result.returncode == 0, result.stderr
        result = subprocess.run([str(executable)], timeout=5)
        assert result.returncode == 42, (source.read_text(), companion.read_text(), result.returncode)

    version_probe = invoke([host, '--version'])
    assert version_probe.returncode == 0 and version_probe.stdout.splitlines(), version_probe.stderr
    native_version = version_probe.stdout.splitlines()[0]
    macro_probe = subprocess.run([host, '-std=c2x', '-pedantic-errors', '-fno-common',
                                  '-dM', '-E', '-x', 'c', '-'], input='',
                                 capture_output=True, text=True, timeout=15)
    identity = native_identity_from_macros(macro_probe)
    assert identity is not None, ('unsupported/unverified native family or target', native_version, macro_probe.stderr)
    native_family, native_target = identity
    print(f'Native identity: {host}; {native_version}; family={native_family}; target={native_target}; flags={NATIVE_OBJECT_FLAGS}')

    supported = set()
    for feature, text in [('typeof', 'typeof(int) value;'),
                          ('typeof_unqual', 'typeof_unqual(int) value;'),
                          ('nullptr', 'int *p=nullptr;')]:
        companion.write_text(text+'\n')
        probe = invoke([host, '-std=c2x', '-pedantic-errors', '-fsyntax-only', companion])
        if probe.returncode == 0:
            supported.add(feature)
        else:
            assert legacy_feature_gap(feature, text, probe), probe.stderr
            assert not legacy_feature_gap(feature, 'int unrelated;', probe)
            for status in [0, 2, 127, -6, -9, -11]:
                assert not legacy_feature_gap(feature, text, subprocess.CompletedProcess([], status, '', probe.stderr))
            for extra in ['error: extra', 'warning: extra', 'note: extra', 'fatal error: extra']:
                assert not legacy_feature_gap(feature, text, subprocess.CompletedProcess([], 1, '', probe.stderr+'\n'+extra))

    native_pairs = runtime_pairs = keyword_skips = companion_skips = 0
    native_storage_gaps = native_clean_pairs = native_final_one_pairs = native_legacy_logical_pairs = native_completed_bound_pairs = 0
    for name, text, companion_text, owned, features, companion_features in pairs:
        emitted = compile_source(text)
        check_layout(emitted, owned)
        companion.write_text(companion_text+'\n')
        if not set(companion_features) <= supported:
            companion_skips += 1
        else:
            native_compile(companion, companion_obj)
            companion_declares_only(companion_obj, owned)
            if qbe:
                kcc_obj.unlink(missing_ok=True)
                result = invoke([host, '-c', assembly, '-o', kcc_obj])
                assert result.returncode == 0, result.stderr
                owned_once(kcc_obj, owned, qbe_assembly=assembly)
                link_run([kcc_obj, companion_obj])
                runtime_pairs += 1
        if not set(features+companion_features) <= supported:
            keyword_skips += 1
            continue
        # Correct kcc/QBE ownership/runtime above is independent of native bugs.
        category = native_compile(source, native_obj, owned)
        if category == 'layout_gap':
            native_storage_gaps += 1
            continue  # NEVER execute or count an underallocated native original.
        owned_once(native_obj, owned)
        link_run([native_obj, companion_obj])
        native_pairs += 1
        native_clean_pairs += category == 'clean'
        native_final_one_pairs += category == 'final_one_warning'
        native_legacy_logical_pairs += category == 'legacy_logical_warning'
        native_completed_bound_pairs += category == 'completed_bound_warning'

    native_constraints = 0
    for cases, features in [(constraints, ()), (c23_constraints, ('typeof',))]:
        for text, message in cases:
            compile_source(text, False, message)
            if not set(features) <= supported:
                continue
            native_obj.unlink(missing_ok=True)
            result = invoke([host, '-std=c2x', '-pedantic-errors', '-fno-common', '-c', source, '-o', native_obj])
            assert result.returncode == 1, (text, result.stderr)
            native_constraints += 1
    for text, message in subset_errors:
        compile_source(text, False, message)
    for text in unavailable_initializers:
        compile_source(text, False, 'inferred name is unavailable in its initializer')

    # Resource-generated sources compile only; no definition from these probes
    # is linked or executed. Keep limits shared with scalars/extern objects.
    for amount in [512, 513]:
        emitted = compile_source('int items[];'*amount, amount == 512,
                                 None if amount == 512 else 'declaration limit (512)')
        if amount == 512:
            check_layout(emitted, {'items': (4, 4)})
        compile_source('int '+','.join(['items[]']*amount)+';', amount == 512,
                       None if amount == 512 else 'declaration limit (512)')
    for amount in [256, 257]:
        compile_source('int '+','.join(f'a{i}[]' for i in range(amount))+';', amount == 256,
                       None if amount == 256 else 'external object limit (256)')
    shared = 'int '+','.join([f's{i}' for i in range(128)]+[f'a{i}[]' for i in range(128)])+';'
    emitted = compile_source(shared)
    assert len(re.findall(r'\bdata \$', emitted)) == 256, emitted
    compile_source(shared+'int extra;', False, 'external object limit (256)')
    mixed = shared+'int '+','.join(f'f{i}(void)' for i in range(256))+';'
    compile_source(mixed)
    compile_source(mixed+'extern int a0[];', False, 'declaration limit (512)')
    for text, success in [
        ('char a[1048576];', True), ('char a[1048577];', False),
        ('int a[262144];', True), ('int a[262145];', False),
        ('char a[1024][1024];', True), ('char a[1024][1025];', False),
        ('char a[][1048576];', True),
        ('char a[][1048576]; extern char a[2][1048576];', False),
        ('char a[1048576],b[1048576];', True),
        ('extern char a[]; char a[1048576];', True),
    ]:
        compile_source(text, success, None if success else 'storage limit')
    for dimensions in [64, 65]:
        compile_source('int a'+'[1]'*dimensions+';', dimensions == 64,
                       None if dimensions == 64 else 'dimension limit (64)')
        compile_source('int a[]'+'[1]'*(dimensions-1)+';', dimensions == 64,
                       None if dimensions == 64 else 'dimension limit (64)')

    # Regression: scalar data and declaration-only extern arrays retain their
    # old behavior; scalar/array labels never allocate function-local slots.
    for typ, size in zip(integers, primitive_sizes):
        emitted = compile_source(f'{typ} scalar; extern {typ} scalar; {typ} scalar;')
        check_layout(emitted, {'scalar': (size, size)})
    for pure_extern in ['extern int absent[];', 'extern int absent[3];',
                        'typedef int Unknown[]; extern Unknown absent;',
                        'extern int absent[]; extern typeof(absent) other;']:
        assert not compile_source(pure_extern).strip(), pure_extern
    query_only = ('static int private_fn(int); typeof(&private_fn) callbacks[2]; '
                  'extern int absent[]; int query(void) { return sizeof callbacks+sizeof(&absent); }')
    emitted = compile_source(query_only)
    check_layout(emitted, {'callbacks': (16, 8)})
    assert '$private_fn' not in emitted and '$absent' not in emitted and 'alloc' not in emitted, emitted
    comparison = compile_source('int get(void) { int local=42; return local; }')
    with_array = compile_source('int items[3]; int get(void) { int local=42; return local; }')
    assert comparison.count('alloc') == with_array.count('alloc') == 1, (comparison, with_array)
    source.write_text('int items[];\n')
    with open('/dev/full', 'w') as full:
        failed = subprocess.run([str(compiler), str(source)], stdout=full,
                                stderr=subprocess.PIPE, text=True, timeout=15)
    assert failed.returncode == 1 and 'cannot write QBE output' in failed.stderr, failed.stderr
    if qbe:
        compile_source(query_only)
        kcc_obj.unlink(missing_ok=True)
        result = invoke([host, '-c', assembly, '-o', kcc_obj])
        assert result.returncode == 0, result.stderr
        records = owned_once(kcc_obj, {'callbacks': (16, 8)}, qbe_assembly=assembly)
        assert not any(name in ['private_fn', 'absent'] for kind, name, size in records), records
        emitted = compile_source('int items[]; extern int absent[]; '
                                 'int get(void) { return items[0]+absent[0]; }')
        check_layout(emitted, {'items': (4, 4)})
        assert 'data $absent' not in emitted, emitted
        kcc_obj.unlink(missing_ok=True)
        result = invoke([host, '-c', assembly, '-o', kcc_obj])
        assert result.returncode == 0, result.stderr
        records = owned_once(kcc_obj, {'items': (4, 4)}, qbe_assembly=assembly)
        assert [kind for kind, name, size in records if name == 'items'][0] in ['B', 'D'], records
        assert ('U', 'absent', None) in records, records

print(f'Tentative arrays passed: {len(pairs)} sole-owner zero-storage pairs '
      f'(48 primitive fixed/unknown both-direction arrangements), '
      f'{native_pairs} unchanged native runtime agreements ({native_clean_pairs} diagnostic-free, '
      f'{native_final_one_pairs} exact benign final-one warnings, {native_legacy_logical_pairs} exact logical warnings, '
      f'{native_completed_bound_pairs} exact correct-composite warnings), '
      f'{native_storage_gaps} exact native storage bugs (NEVER executed), {keyword_skips} keyword-gated native pairs, '
      f'{native_constraints} native constraints, {len(constraints)+len(c23_constraints)} kcc constraints, '
      f'{len(subset_errors)} subset refusals, {len(unavailable_initializers)} kcc-only unavailable-name barriers; '
      f'512 declarations/256 shared objects/256 functions/1 MiB per array/64 dimensions; '
      f'{host}; keywords available: {sorted(supported)}'
      + (f'; QBE {runtime_pairs} paired runtimes, {companion_skips} companion keyword gaps, exact layout/nm-S/sole-owner checks passed' if qbe else ''))

"""M15 file-scope INTEGER initialized definitions: independent storage/ICE oracle.

[KCC=...] [HOST_CC=...] [CLANG_CC=...] [QBE=...] python3 tests/test_integer_initializers.py
--native-only validates unchanged originals without claiming KCC passed.
--harness-self-test exercises the ELF reader and fail-closed producer checks.

Only defined curated originals execute. Every native comparison compiles the
EXACT owner and companion separately, with -fno-common; no source adaptation,
keyword substitution, syntax-only tentative-finalization shortcut, or UB
execution. Keyword-unavailable originals are explicitly counted, NOT agreements.
Arithmetic-invalid and conservative subset cases compile only; native undefined
arithmetic or mixed-linkage UB is never counted as native rejection evidence.
"""
import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
KCC = Path(os.environ.get('KCC', ROOT / 'build' / 'kcc'))
HOST = os.environ.get('HOST_CC', 'cc')
QBE = os.environ.get('QBE')
# type, size, unchanged initializer expression, expected target integer
LEAVES = [('_Bool', 1, '9', 1), ('char', 1, '-7', -7),
          ('signed char', 1, '-101', -101), ('unsigned char', 1, '255', 255),
          ('short', 2, '-12345', -12345), ('unsigned short', 2, '65535', 65535),
          ('int', 4, '-2147483647-1', -2147483648),
          ('unsigned', 4, '4294967295U', 4294967295),
          ('long', 8, '-4294967297L', -4294967297),
          ('unsigned long', 8, '18446744073709551615UL', 18446744073709551615),
          ('long long', 8, '-9223372036854775807LL-1LL', -9223372036854775808),
          ('unsigned long long', 8, '18446744073709551615ULL', 18446744073709551615)]


@dataclass
class Fixture:
    name: str
    owner: str
    objects: dict  # name -> (byte width, integer bits/value, global binding)
    companion: str = ''
    features: tuple = ()
    initialized: tuple = None  # None means every owned object is explicit.


def fixtures():
    cases = []
    # Each type has direct/static/extern initialized definitions, and const
    # counterparts. Earlier and later tentatives must NOT acquire second storage.
    for typ, width, expression, value in LEAVES:
        for storage in ['', 'static ', 'extern ']:
            for const in ['', 'const ']:
                t = const + typ
                prior = 'static ' if storage == 'static ' else ''
                owner = (f'{prior}{t} cell; {storage}{t} cell={expression}; '
                         f'extern {t} cell; {prior}{t} cell; '
                         f'{t} *slot(void) {{ return &cell; }} '
                         'int main(void) { '
                         f'if(sizeof cell!={width} || cell!=({t})({expression})) return 1; '
                         f'{t} *p=slot(); if(p!=&cell || *p!=cell) return 2; ')
                if not const:
                    owner += f'*p=({typ})0; if(cell!=0) return 3; '
                owner += 'return 42; }'
                cases.append(Fixture(f'{storage}{t}', owner,
                                     {'cell': (width, value, storage != 'static ')}))
    # Zero initializers need explicit-definition ownership even if an assembler
    # chooses BSS. Narrowing is defined modulo unsigned width / boolean truth.
    for typ, width, _, _ in LEAVES:
        cases.append(Fixture(typ+' explicit zero',
                             f'{typ} cell=0; {typ} cell; int main(void) {{ '
                             'return cell==0 && *(&cell)==0?42:1; }', {'cell': (width, 0, True)}))
    for typ, width, expr, value in [('_Bool', 1, '1ULL<<63', 1),
                                   ('_Bool', 1, '4294967295U+1U', 0),
                                   ('unsigned char', 1, '257', 1),
                                   ('unsigned short', 2, '65537U', 1),
                                   ('unsigned', 4, '18446744073709551615ULL', 4294967295),
                                   ('unsigned long', 8, '-1', 18446744073709551615)]:
        cases.append(Fixture(typ+' conversion '+expr,
                             f'{typ} cell={expr}; int main(void) {{ '
                             f'return cell==({typ})({expr})?42:1; }}', {'cell': (width, value, True)}))
    for expr, value in [('6*7', 42), ('(15&7)^2', 5), ('~0U', 4294967295),
                        ('1?42:1/0', 42), ('0?1ULL<<64:42', 42),
                        ('1 || (1,2)', 1), ('0 && 1/0', 0),
                        ('1?42:2147483647+1', 42), ('sizeof(1/0)+38', 42),
                        ('sizeof cell+38', 42), ('sizeof(int[2][3])+18', 42),
                        ('(unsigned char)256+42', 42), ("'A'-23", 42)]:
        cases.append(Fixture('ICE '+expr,
                             f'unsigned cell={expr}; int main(void) {{ '
                             f'return cell==({expr})?42:1; }}', {'cell': (4, value, True)}))
    cases.extend([
        Fixture('mixed direct declarators',
                'int a=40,b,c=sizeof a+38,f(void),*p,(*fp)(void); '
                'int f(void) { return 42; } int main(void) { '
                'if(a!=40 || b || c!=42 || p || fp) return 1; '
                'p=&a; fp=f; return *p+2==fp()?42:2; }',
                {'a': (4, 40, True), 'b': (4, 0, True), 'c': (4, 42, True),
                 'p': (8, 0, True), 'fp': (8, 0, True)}, initialized=('a', 'c')),
        Fixture('same-list canonical ownership',
                'int cell,cell=42,cell; int main(void) { return cell; }',
                {'cell': (4, 42, True)}),
        Fixture('mixed static declarators',
                'static int a=40,b,c=sizeof a+38; extern int a,b,c; '
                'int main(void) { return a==40 && b==0 && c==42?42:1; }',
                {'a': (4, 40, False), 'b': (4, 0, False), 'c': (4, 42, False)}, initialized=('a', 'c')),
        Fixture('extern declaration and definition list',
                'extern int absent,cell=42; int main(void) { return cell; }',
                {'cell': (4, 42, True)}),
        Fixture('extern inherits private linkage for definition',
                'static int cell; extern int cell=42; static int cell; '
                'int main(void) { return cell; }', {'cell': (4, 42, False)}),
        Fixture('after function explicit definition',
                'extern long cell; int main(void) { return cell==4294967296L?42:1; } '
                'long cell=4294967296L;', {'cell': (8, 4294967296, True)}),
        Fixture('local and parameter shadows restore initialized storage',
                'int cell=42; int pick(int cell) { return cell; } int main(void) { '
                'int *p=&cell; { int cell=2; if(cell!=2) return 1; } '
                'for(int cell=0;cell<2;cell++) {} return p==&cell?pick(cell):2; }',
                {'cell': (4, 42, True)}),
        Fixture('initialized const is not omitted',
                'const long cell=4294967296L; const long *slot(void) { return &cell; }',
                {'cell': (8, 4294967296, True)},
                'extern const long cell; const long *slot(void); int main(void) { '
                'return slot()==&cell && *slot()==4294967296L?42:1; }'),
        Fixture('static symbol isolated from companion same spelling',
                'static int cell=40; int *slot(void) { return &cell; } '
                'int get(void) { return cell; }', {'cell': (4, 40, False)},
                'static int cell=99; int *slot(void); int get(void); int main(void) { '
                'if(get()!=40 || slot()==&cell || cell!=99) return 1; '
                '*slot()=42; return get()==42 && cell==99?42:2; }'),
    ])
    # Every leaf via unresolved typedef/query roots, including qualifier retention.
    for typ, width, expr, value in LEAVES:
        cases.append(Fixture('typedef root '+typ,
                             f'typedef {typ} T; T cell={expr}; extern T cell; '
                             'T *slot(void) { return &cell; } int main(void) { '
                             f'return slot()==&cell && cell==(T)({expr})?42:1; }}',
                             {'cell': (width, value, True)}))
        cases.append(Fixture('typeof root '+typ,
                             f'typeof({typ}) cell={expr}; typeof(cell) other=sizeof cell; '
                             'int main(void) { '
                             f'return cell==({typ})({expr}) && other=={width}?42:1; }}',
                             {'cell': (width, value, True), 'other': (width, width, True)}, features=('typeof',)))
    cases.extend([
        Fixture('const typedef root',
                'typedef const long T; static T cell=42; extern T cell; '
                'const long *slot(void) { return &cell; } '
                'int main(void) { return slot()==&cell && *slot()==42?42:1; }', {'cell': (8, 42, False)}),
        Fixture('typeof_unqual writable root',
                'const long frozen=40; typeof_unqual(frozen) cell=42; '
                'int main(void) { cell+=1; return frozen==40 && cell==43?42:1; }',
                {'frozen': (8, 40, True), 'cell': (8, 42, True)}, features=('typeof_unqual',)),
        Fixture('query-only function not emitted',
                'static long missing(void); int cell=sizeof missing()+34; '
                'int main(void) { return cell; }', {'cell': (4, 42, True)}),
        Fixture('C23 bool spelling', 'bool cell=42; const bool other=false; '
                'int main(void) { return cell && !other?42:1; }',
                {'cell': (1, 1, True), 'other': (1, 0, True)}, features=('bool',)),
    ])
    # Exact migrated static-object positives, kept alongside stronger leaf and
    # canonical-ownership matrices rather than weakening older subset tests.
    for name, text, width, value, features in [
            ('static int zero', 'static int cell=0;', 4, 0, ()),
            ('static int forty-two', 'static int cell=42;', 4, 42, ()),
            ('static const int zero', 'static const int cell=0;', 4, 0, ()),
            ('static typedef zero', 'typedef int T; static T cell=0;', 4, 0, ()),
            ('static typeof zero', 'static typeof(int) cell=0;', 4, 0, ('typeof',)),
            ('typedef self sizeof', 'typedef short T; static T cell=sizeof cell+40;', 2, 42, ()),
            ('typeof self sizeof', 'static typeof(long) cell=sizeof cell+34;', 8, 42, ('typeof',))]:
        cases.append(Fixture(name, text+' const void *slot(void) { return &cell; } '+
                             f'int main(void) {{ return slot()==&cell && cell=={value}?42:1; }}',
                             {'cell': (width, value, False)}, features=features))
    cases.append(Fixture('mixed typedef-root declarators',
                         'typedef int T; T a=40,b,c=sizeof a+38,f(void),*p; '
                         'int f(void) { return 42; } int main(void) { '
                         'return a==40 && !b && c==42 && !p && f()==42?42:1; }',
                         {'a': (4, 40, True), 'b': (4, 0, True),
                          'c': (4, 42, True), 'p': (8, 0, True)}, initialized=('a', 'c')))
    # Eight mixed integer arguments cover register and stack classification;
    # initialized leaf is returned and observed at full width in BOTH directions.
    params = 'char a,short b,int c,long d,unsigned e,long long f,unsigned long long g,int h'
    args = '-7,-1234,-1234567,4294967296L,4294967295U,4611686018427387904LL,18446744073709551615ULL,8'
    check = ('if(a!=-7 || b!=-1234 || c!=-1234567 || d!=4294967296L || '
             'e!=4294967295U || f!=4611686018427387904LL || '
             'g!=18446744073709551615ULL || h!=8) return 0; ')
    for typ, width, expr, value in LEAVES:
        callee = f'{typ} pick({params}) {{ {check} return cell; }}'
        caller = (f'int main(void) {{ if(pick({args})!=({typ})({expr}) || '
                  f'cell!=({typ})({expr})) return 1; cell=0; return cell==0?42:2; }}')
        cases.append(Fixture('owner callee '+typ, f'{typ} cell={expr}; '+callee,
                             {'cell': (width, value, True)},
                             f'extern {typ} cell; {typ} pick({params}); '+caller))
        cases.append(Fixture('owner caller '+typ,
                             f'{typ} cell={expr}; {typ} pick({params}); '+caller,
                             {'cell': (width, value, True)}, f'extern {typ} cell; '+callee))
    return cases


# Native constraint agreements: compile only, no mixed-linkage UB or invalid
# signed arithmetic is allowed in this list.
CONSTRAINTS = [
    ('int cell=1; long cell;', 'incompatible'),
    ('const int cell=1; int cell;', 'incompatible'),
    ('int cell; long cell=1;', 'incompatible'),
    ('int cell(void); int cell=1;', 'conflict'),
    ('typedef int cell; int cell=1;', 'conflict'),
    ('int cell=42; int f(void) { return cell(); }', 'called'),
    ('const int cell=42; int f(void) { cell=2; return cell; }', 'modifiable'),
    ('int cell=missing;', 'undeclared'),
    ('int cell=later; int later=42;', 'undeclared'),
    ('int f(void); int cell=f();', 'constant'),
    ('int other=42; int cell=other;', 'constant'),
    ('int cell=42; _Static_assert(cell==42,"not ICE");', 'constant'),
]
# KCC's conservative ICE checker diagnoses invalid arithmetic before assignment
# conversion, including for _Bool. Native UB acceptance/rejection is NOT scored.
DUPLICATES = [
    ('int cell=1; int cell=2;', 'multiple initialized definitions of object'),
    ('static int cell=1; static int cell=1;', 'multiple initialized definitions of object'),
    ('int cell=1,cell=1;', 'multiple initialized definitions of object'),
    ('extern int cell=1; int cell=1;', 'multiple initialized definitions of object'),
]
ARITHMETIC = [('1/0', 'division by zero'), ('1%0', 'division by zero'),
              ('2147483647+1', 'signed overflow'),
              ('(-2147483647-1)-1', 'signed overflow'),
              ('2147483647*2', 'signed overflow'),
              ('-(-2147483647-1)', 'signed overflow'),
              ('(-9223372036854775807LL-1LL)/-1LL', 'signed overflow'),
              ('(-9223372036854775807LL-1LL)%-1LL', 'signed overflow'),
              ('1ULL<<64', 'invalid shift count'), ('1<<-1', 'invalid shift count'),
              ('-1<<1', 'negative left operand'), ('1<<31', 'signed overflow')]
DEFERRED = [
    'int cell[2]={1,2};',
    'int cell[]={1,2};', 'int cell={42};', 'int cell={};',
    'int other; int *cell=&other;', 'char *cell="x";',
    'int f(int); int (*cell)(int)=f;', 'typeof(nullptr) cell=nullptr;',
    'int cell=(1,42);', 'int other; int cell=1?42:other;',
    'int f(void); int cell=1||f();',
    'static int cell; int cell=42;',
]


def invoke(args):
    return subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=20)


def producer(args, output, expected=()):
    """Fresh output, exact complete diagnostics, and success are all required."""
    output.unlink(missing_ok=True)
    result = invoke(args)
    assert result.returncode == 0 and not result.stdout, (args, result.returncode, result.stdout, result.stderr)
    if expected or result.stderr:
        assert '-c' in args, (args, result.stderr)
        source = Path(args[args.index('-c')+1])
        actual = native_diagnostics(result.stderr, source, source.read_text(), clang_style(args[0]))
        assert actual == tuple(expected), (args, actual, expected, result.stderr)
    assert output.is_file() and output.stat().st_size > 0, ('missing/empty fresh output', args, output)
    return result


def clang_style(cc):
    return 'clang' in Path(os.path.realpath(shutil.which(cc) or cc)).name


def expected_warnings(fixture, clang):
    """Exact compiler AND original-specific signatures; no flag-only waivers."""
    extern_names = {'extern '+const+typ for typ, _, _, _ in LEAVES for const in ['', 'const ']}
    extern_names |= {'extern declaration and definition list', 'extern inherits private linkage for definition'}
    if fixture.name in extern_names:
        return (('warning', "'extern' variable has an initializer [-Wextern-initializer]" if clang
                 else "'cell' initialized and declared 'extern'"),)
    gcc = {
        'unsigned char conversion 257': "unsigned conversion from 'int' to 'unsigned char' changes value from '257' to '1' [-Woverflow]",
        'unsigned short conversion 65537U': "conversion from 'unsigned int' to 'short unsigned int' changes value from '65537' to '1' [-Woverflow]",
        'unsigned conversion 18446744073709551615ULL': "conversion from 'long long unsigned int' to 'unsigned int' changes value from '18446744073709551615' to '4294967295' [-Woverflow]",
    }
    clang_messages = {
        '_Bool conversion 1ULL<<63': "converting the result of '<<' to a boolean always evaluates to true [-Wtautological-constant-compare]",
        'unsigned char conversion 257': "implicit conversion from 'int' to 'unsigned char' changes value from 257 to 1 [-Wconstant-conversion]",
        'unsigned short conversion 65537U': "implicit conversion from 'unsigned int' to 'unsigned short' changes value from 65537 to 1 [-Wconstant-conversion]",
        'unsigned conversion 18446744073709551615ULL': "implicit conversion from 'unsigned long long' to 'unsigned int' changes value from 18446744073709551615 to 4294967295 [-Wconstant-conversion]",
        'ICE 1?42:1/0': 'division by zero is undefined [-Wdivision-by-zero]',
        'ICE 0 && 1/0': 'division by zero is undefined [-Wdivision-by-zero]',
    }
    if clang and fixture.name == 'ICE 0?1ULL<<64:42':
        return (('warning', 'shift count >= width of type [-Wshift-count-overflow]'),
                ('warning', "implicit conversion from 'unsigned long long' to 'unsigned int' changes value from 9223372036854775808 to 0 [-Wconstant-conversion]"))
    if clang and fixture.name == 'ICE 1 || (1,2)':
        pair = (('warning', "use of logical '||' with constant operand [-Wconstant-logical-operand]"),
                ('note', "use '|' for a bitwise operation"))
        return (('warning', 'left operand of comma operator has no effect [-Wunused-value]'),)+pair+pair
    message = (clang_messages if clang else gcc).get(fixture.name)
    return (('warning', message),) if message else ()


def elf_objects(path, widths=None):
    """Read real ELF64 SysV/x86-64 relocatable storage, not textual IL guesses."""
    data = path.read_bytes()
    assert data[:7] == b'\x7fELF\x02\x01\x01', (path, data[:16])
    header = struct.unpack_from('<16sHHIQQQIHHHHHH', data)
    assert header[1:3] == (1, 62), (path, header[1:3])  # ET_REL, EM_X86_64
    offset, entry_size, amount = header[6], header[11], header[12]
    assert entry_size == 64 and amount > 0
    sections = [struct.unpack_from('<IIQQQQIIQQ', data, offset+i*entry_size) for i in range(amount)]
    found = {}
    for section in sections:
        if section[1] != 2:  # SHT_SYMTAB
            continue
        strings_section = sections[section[6]]
        strings = data[strings_section[4]:strings_section[4]+strings_section[5]]
        assert section[9] == 24 and section[5] % 24 == 0
        for pos in range(section[4], section[4]+section[5], 24):
            name, info, _, index, value, size = struct.unpack_from('<IBBHQQ', data, pos)
            if not name or index == 0 or index >= len(sections):
                continue
            label = strings[name:strings.index(b'\0', name)].decode()
            if info & 15 != 1:
                # QBE emits defined STT_NOTYPE/size=0 labels for data. Read
                # expected byte width only after exact typed IL layout checks;
                # never pretend QBE supplied ELF object-size metadata.
                if not widths or label not in widths or info & 15 != 0 or size != 0:
                    continue
                size = widths[label]
            assert index < len(sections)
            target = sections[index]
            assert value+size <= target[5], (path, label, value, size, target)
            contents = bytes(size) if target[1] == 8 else data[target[4]+value:target[4]+value+size]
            found.setdefault(label, []).append((info >> 4, size, target[8], value, contents))
    return found


def storage_evidence(path, expected, qbe_labels=False):
    records = elf_objects(path, {n: v[0] for n, v in expected.items()} if qbe_labels else None)
    nm = invoke(['nm', '-S', path])
    assert nm.returncode == 0 and not nm.stderr, nm.stderr
    nm_records = [line.split() for line in nm.stdout.splitlines()]
    for name, (width, value, public) in expected.items():
        entries = records.get(name, [])
        assert len(entries) == 1, (path, name, records)
        binding, size, alignment, offset, contents = entries[0]
        wanted = (value % (1 << (width*8))).to_bytes(width, 'little')
        assert (binding, size, contents) == (int(public), width, wanted), (path, name, entries, wanted)
        assert alignment >= width and offset % width == 0, (path, name, entries)
        symbols = [p for p in nm_records if p[-1] == name]
        assert len(symbols) == 1 and len(symbols[0]) == (3 if qbe_labels else 4), (name, nm.stdout)
        kind = symbols[0][-2]
        assert kind in ('BDR' if public else 'bdr'), (name, nm.stdout)
        if not qbe_labels:
            assert int(symbols[0][1], 16) == width, (name, nm.stdout)
    assert not re.search(r'\b[Cc]\s+(?:'+ '|'.join(map(re.escape, expected)) +r')$', nm.stdout, re.M)
    assert not any(name in records for name in ['absent', 'missing']), records


def run_program(linker, objects, executable):
    producer([linker, *objects, '-o', executable], executable)
    result = invoke([executable])
    assert result.returncode == 42 and not result.stdout and not result.stderr, (
        objects, result.returncode, result.stdout, result.stderr)


PROBES = {'typeof': 'typeof(int) cell;', 'typeof_unqual': 'typeof_unqual(int) cell;',
          'bool': 'bool cell=true;', 'nullptr': 'int *cell=nullptr;'}



def native_diagnostics(stderr, source, original, clang):
    """Validate EVERY stderr line; unknown tool text is never a diagnostic gap.

    GCC/Clang source/caret/fix-it rendering is accepted only against the exact
    unchanged original. Summary counts must exactly match all diagnostic headers.
    Return None on any unknown line, fatal diagnostic, bad count or context.
    """
    if not stderr:
        return ()
    if not stderr.endswith('\n'):
        return None
    records, summary = [], None
    original_lines = original.splitlines()
    path = re.escape(str(source))
    header = re.compile(path+r':(\d+):(?:(\d+):)? (fatal error|error|warning|note): (.+)$')
    lines = stderr.splitlines()
    last_source_line = None
    for index, raw in enumerate(lines):
        line = raw.replace('‘', "'").replace('’', "'")
        match = header.fullmatch(line)
        if match:
            number, column, kind, message = match.groups()
            if kind == 'fatal error' or not 1 <= int(number) <= len(original_lines)+1:
                return None
            if column is not None and int(column) < 1:
                return None
            records.append((kind, message))
            last_source_line = int(number)
            continue
        snippet = re.fullmatch(r'\s*(\d+) \| ?(.*)', raw)
        if snippet:
            number, code = int(snippet[1]), snippet[2]
            if not records or number != last_source_line or not 1 <= number <= len(original_lines):
                return None
            if code != original_lines[number-1]:
                return None
            continue
        if re.fullmatch(r'\s*\|[ ~^|]*', line):
            if not records or last_source_line is None:
                return None
            continue
        if re.fullmatch(r'\s*\+\+\+ \|\+#include <stdbool.h>', line):
            if not records or records[-1] not in [
                    ('note', "'bool' is defined in header '<stdbool.h>'; did you forget to '#include <stdbool.h>'?"),
                    ('note', "'true' is defined in header '<stdbool.h>'; did you forget to '#include <stdbool.h>'?")]:
                return None
            continue
        context = re.fullmatch(path+r": In function '([A-Za-z_][A-Za-z_0-9]*)':", line)
        if context:
            if not re.search(r'\b'+re.escape(context[1])+r'\s*\(', original):
                return None
            continue
        if line == str(source)+': At top level:':
            continue
        # A summary is permitted ONLY as the exact final Clang summary.
        if clang and index == len(lines)-1:
            warnings = sum(kind == 'warning' for kind, _ in records)
            errors = sum(kind == 'error' for kind, _ in records)
            parts = []
            if warnings:
                parts.append(f'{warnings} warning'+('s' if warnings != 1 else ''))
            if errors:
                parts.append(f'{errors} error'+('s' if errors != 1 else ''))
            if parts and line == ' and '.join(parts)+' generated.':
                summary = True
                continue
        return None
    if not records or (clang and not summary):
        return None
    return tuple(records)


def keyword_gap(feature, original, result, source, clang):
    """Only exact independent legacy-keyword signatures qualify as absence."""
    typeof = [
        [('error', "return type defaults to 'int' [-Wimplicit-int]"),
         ('error', "expected declaration specifiers before 'cell'"),
         ('error', "expected '{' at end of input")],
        [('error', 'expected function body after function declarator')],
    ]
    expected = {
        'typeof': typeof, 'typeof_unqual': typeof,
        'nullptr': [[('error', "'nullptr' undeclared here (not in a function)")],
                    [('error', "use of undeclared identifier 'nullptr'")]],
        'bool': [
            [('error', "unknown type name 'bool'"),
             ('note', "'bool' is defined in header '<stdbool.h>'; did you forget to '#include <stdbool.h>'?"),
             ('error', "'true' undeclared here (not in a function)"),
             ('note', "'true' is defined in header '<stdbool.h>'; did you forget to '#include <stdbool.h>'?")],
            [('error', "unknown type name 'bool'"), ('error', "use of undeclared identifier 'true'")],
        ],
    }
    return (original == PROBES[feature] and result.returncode == 1 and not result.stdout
            and native_diagnostics(result.stderr, source, original, clang) in [tuple(r) for r in expected[feature]])


def expected_constraint(text, clang):
    gcc = [
        (("conflicting types for 'cell'; have 'long int'"), "previous definition of 'cell' with type 'int'"),
        ("conflicting type qualifiers for 'cell'", "previous definition of 'cell' with type 'int'"),
        ("conflicting types for 'cell'; have 'long int'", "previous declaration of 'cell' with type 'int'"),
        ("'cell' redeclared as different kind of symbol", "previous declaration of 'cell' with type 'int(void)'"),
        ("'cell' redeclared as different kind of symbol", "previous declaration of 'cell' with type 'cell' {aka 'int'}"),
        ("called object 'cell' is not a function or function pointer", 'declared here'),
        ("assignment of read-only variable 'cell'",),
        ("'missing' undeclared here (not in a function)",),
        ("'later' undeclared here (not in a function)",),
        ('initializer element is not constant',),
        ('initializer element is not constant',),
        ('expression in static assertion is not constant',),
    ]
    clang_messages = [
        ("redefinition of 'cell' with a different type: 'long' vs 'int'", 'previous definition is here'),
        ("redefinition of 'cell' with a different type: 'int' vs 'const int'", 'previous definition is here'),
        ("redefinition of 'cell' with a different type: 'long' vs 'int'", 'previous definition is here'),
        ("redefinition of 'cell' as different kind of symbol", 'previous definition is here'),
        ("redefinition of 'cell' as different kind of symbol", 'previous definition is here'),
        ("called object type 'int' is not a function or function pointer",),
        ("cannot assign to variable 'cell' with const-qualified type 'const int'", "variable 'cell' declared const here"),
        ("use of undeclared identifier 'missing'",),
        ("use of undeclared identifier 'later'",),
        ('initializer element is not a compile-time constant',),
        ('initializer element is not a compile-time constant',),
        ('static assertion expression is not an integral constant expression',),
    ]
    originals = [original for original, _ in CONSTRAINTS]
    messages = (clang_messages if clang else gcc)[originals.index(text)]
    return tuple(('error' if index == 0 else 'note', msg) for index, msg in enumerate(messages))


def native_rejection(text, result, source, output, clang):
    return (result.returncode == 1 and not result.stdout and not output.exists() and
            native_diagnostics(result.stderr, source, text, clang) == expected_constraint(text, clang))


def features_for(cc, source, output):
    supported = set()
    for feature, text in PROBES.items():
        source.write_text(text+'\n')
        output.unlink(missing_ok=True)
        result = invoke([cc, '-std=c2x', '-pedantic-errors', '-c', source, '-o', output])
        assert not result.stdout
        if result.returncode == 0:
            assert not result.stderr and output.is_file() and output.stat().st_size
            supported.add(feature)
        else:
            # A failed independent keyword probe never excuses fixture failures.
            # Signals, tool failures, unsupported target flags, etc. fail closed.
            assert keyword_gap(feature, text, result, source, clang_style(cc)), (cc, feature, result.stderr)
            assert str(source) in result.stderr, result.stderr
            assert not output.exists(), (cc, feature, 'failed producer left object')
    return supported


def harness_self_test(directory):
    """Adversarial controls for all native verdict paths, not compiler fixtures."""
    source, output = directory/'probe.c', directory/'stale.o'
    original = PROBES['nullptr']
    source.write_text(original+'\n')

    def rendered(kind, message, clang=False):
        text = f'{source}:1:1: {kind}: {message}\n    1 | {original}\n      | ^\n'
        if clang:
            text += f'1 {kind} generated.\n'
        return text

    for clang in [False, True]:
        message = "use of undeclared identifier 'nullptr'" if clang else "'nullptr' undeclared here (not in a function)"
        good = rendered('error', message, clang)
        result = subprocess.CompletedProcess([], 1, '', good)
        assert keyword_gap('nullptr', original, result, source, clang)
        assert not keyword_gap('nullptr', 'int unrelated;', result, source, clang)
        for status in [0, -6, -9, -11, 2, 127]:
            assert not keyword_gap('nullptr', original, subprocess.CompletedProcess([], status, '', good), source, clang)
        corruptions = [good+'UNRECOGNIZED EXTRA STDERR\n', good+'internal compiler error: broken\n',
                       good+'tool: unrelated failure\n', good.replace('error:', 'fatal error:', 1),
                       good+f'{source}:1:1: warning: extra\n', good+f'{source}:1:1: error: extra\n',
                       good+f'{source}:1:1: note: extra\n', good+'1 error generated.\n',
                       good.replace('1 error generated.', '2 errors generated.') if clang else good+'garbage\n']
        for stderr in corruptions:
            assert not keyword_gap('nullptr', original, subprocess.CompletedProcess([], 1, '', stderr), source, clang), stderr
        assert not keyword_gap('nullptr', original, subprocess.CompletedProcess([], 1, 'stdout', good), source, clang)

    original = 'int cell=missing;'
    source.write_text(original+'\n')
    for clang in [False, True]:
        good = rendered('error', expected_constraint(original, clang)[0][1], clang)
        result = subprocess.CompletedProcess([], 1, '', good)
        output.unlink(missing_ok=True)
        assert native_rejection(original, result, source, output, clang)
        for status in [0, -6, -9, -11, 2, 127]:
            assert not native_rejection(original, subprocess.CompletedProcess([], status, '', good), source, output, clang)
        for stderr in [good+'UNRECOGNIZED EXTRA STDERR\n', good+'internal compiler error: broken\n',
                       good+'tool: unrelated failure\n', good.replace('error:', 'fatal error:', 1),
                       rendered('error', 'unrelated tool failure', clang),
                       good+f'{source}:1:1: warning: extra\n', good+f'{source}:1:1: error: extra\n',
                       good+f'{source}:1:1: note: extra\n', good+'1 error generated.\n',
                       good.replace('1 error generated.', '2 errors generated.') if clang else good+'garbage\n']:
            assert not native_rejection(original, subprocess.CompletedProcess([], 1, '', stderr), source, output, clang), stderr
        assert not native_rejection(original, subprocess.CompletedProcess([], 1, 'stdout', good), source, output, clang)
        output.write_bytes(b'stale')
        assert not native_rejection(original, result, source, output, clang)
        output.unlink()

    # Exercise real producer calls: even a success status cannot reuse stale data.
    original = 'extern int cell=42;'
    source.write_text(original+'\n')
    for clang in [False, True]:
        source.write_text(original+'\n')
        fake = directory/('fake-clang' if clang else 'fake-gcc')
        fixture = Fixture('extern int', original, {})
        expected = expected_warnings(fixture, clang)
        good = rendered('warning', expected[0][1], clang)

        def fake_tool(stderr, stdout='', status=0, creates=True):
            fake.write_text('#!/usr/bin/env python3\nimport os, sys, resource\nfrom pathlib import Path\nresource.setrlimit(resource.RLIMIT_CORE, (0,0))\n'+
                            (f"Path(sys.argv[-1]).write_bytes({b'' if creates == 'empty' else b'fresh'!r})\n" if creates else '')+
                            f'sys.stderr.write({stderr!r})\nsys.stdout.write({stdout!r})\nsys.stderr.flush()\nsys.stdout.flush()\n'+
                            (f'os.kill(os.getpid(), {-status})\n' if status < 0 else f'sys.exit({status})\n'))
            fake.chmod(0o700)

        fake_tool(good)
        output.write_bytes(b'stale')
        producer([fake, '-c', source, '-o', output], output, expected)
        assert output.read_bytes() == b'fresh'
        invalid = [(good+'UNRECOGNIZED EXTRA STDERR\n', '', 0, True),
                   (good+'internal compiler error: broken\n', '', 0, True),
                   (good+'tool: unrelated failure\n', '', 0, True),
                   (good.replace('warning:', 'fatal error:', 1), '', 0, True),
                   (rendered('warning', 'unrelated message [-Woverflow]', clang), '', 0, True),
                   (good+'1 warning generated.\n', '', 0, True),
                   (good.replace('1 warning generated.', '2 warnings generated.') if clang else good+'garbage\n', '', 0, True),
                   (good, 'unexpected stdout', 0, True), (good, '', 0, False), (good, '', 0, 'empty')]
        invalid += [(rendered('warning', msg, clang), '', 0, True) for msg in [
            'unrelated message [-Wconstant-conversion]', "unrelated initialized and declared 'extern'"]]
        invalid += [(good+f'{source}:1:1: {kind}: extra\n', '', 0, True) for kind in ['warning', 'error', 'note']]
        invalid += [(good, '', status, True) for status in [1, -6, -9, -11, 2, 127]]
        for stderr, stdout, status, creates in invalid:
            fake_tool(stderr, stdout, status, creates)
            output.write_bytes(b'stale')
            try:
                producer([fake, '-c', source, '-o', output], output, expected)
            except AssertionError:
                assert not output.exists() or output.read_bytes() != b'stale'
            else:
                raise AssertionError(('corrupt producer accepted', clang, stderr, stdout, status, creates))
        # Successful keyword probes must ALSO create fresh objects, not just rc0.
        fake_tool('', creates=False)
        output.write_bytes(b'stale')
        try:
            features_for(fake, source, output)
        except AssertionError:
            assert not output.exists()
        else:
            raise AssertionError('keyword success accepted stale/missing object')
        # A failed keyword probe may not leave an object either. Construct an
        # otherwise exact supported legacy signature, then poison its artifact.
        original = PROBES['typeof']
        if clang:
            missing = rendered('error', 'expected function body after function declarator', True)
        else:
            missing = ''.join(rendered('error', msg) for msg in [
                "return type defaults to 'int' [-Wimplicit-int]",
                "expected declaration specifiers before 'cell'", "expected '{' at end of input"])
        fake_tool(missing, status=1, creates=True)
        output.write_bytes(b'stale')
        try:
            features_for(fake, source, output)
        except AssertionError:
            assert output.read_bytes() == b'fresh'
        else:
            raise AssertionError('failed keyword producer accepted an object')
        original = 'extern int cell=42;'

    source.write_text('int public_cell=0x12345678; static short private_cell=-7; '
                      'short *slot(void) { return &private_cell; }\n')
    producer([HOST, '-fno-common', '-c', source, '-o', output], output)
    storage_evidence(output, {'public_cell': (4, 0x12345678, True), 'private_cell': (2, -7, False)})
    print('Harness self-test passed: full-stream keyword/constraint/producer adversarial controls, '
          'freshness and actual ELF bytes/binding verified')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-only', action='store_true')
    parser.add_argument('--harness-self-test', action='store_true')
    options = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='kcc integer initializers ') as tmp:
        directory = Path(tmp)
        harness_self_test(directory)
        if options.harness_self_test:
            return
        owner, companion, native_obj, companion_obj, il, assembly, kcc_obj, exe = [directory/n for n in
            ['owner.c', 'companion.c', 'native.o', 'companion.o', 'k.ssa', 'k.s', 'k.o', 'program']]
        compilers = [HOST]
        clang = os.environ.get('CLANG_CC') or shutil.which('clang') or (HOST if 'clang' in Path(HOST).name else None)
        if clang and os.path.realpath(shutil.which(HOST) or HOST) != os.path.realpath(shutil.which(clang) or clang):
            compilers.append(clang)
        print('Native compilers:', ', '.join(compilers), flush=True)
        if not clang:
            print('Clang unavailable: NOT counted as a comparison', flush=True)
        supported = {cc: features_for(cc, owner, native_obj) for cc in compilers}
        cases = fixtures()
        assert len({fixture.name for fixture in cases}) == len(cases)
        counts = {cc: [0, 0, 0] for cc in compilers}  # agreements, feature gaps, constraints
        kcc_cases = qbe_cases = rejection_count = 0
        for fixture in cases:
            owner.write_text(fixture.owner+'\n')
            companion.write_text(fixture.companion+'\n')
            for cc in compilers:
                if not set(fixture.features) <= supported[cc]:
                    counts[cc][1] += 1
                    continue
                producer([cc, '-std=c2x', '-pedantic-errors', '-fno-common', '-fsigned-char',
                          '-O0', '-c', owner, '-o', native_obj], native_obj, expected_warnings(fixture, clang_style(cc)))
                storage_evidence(native_obj, fixture.objects)
                objects = [native_obj]
                if fixture.companion:
                    producer([cc, '-std=c2x', '-pedantic-errors', '-fno-common', '-fsigned-char',
                              '-O0', '-c', companion, '-o', companion_obj], companion_obj)
                    # Companions may own their explicitly separate private cell,
                    # never an external definition of an owner's public symbol.
                    entries = elf_objects(companion_obj)
                    for name, (_, _, public) in fixture.objects.items():
                        if public:
                            assert name not in entries, (fixture.name, name, entries)
                    objects.append(companion_obj)
                run_program(cc, objects, exe)
                counts[cc][0] += 1
            if options.native_only:
                continue
            result = invoke([KCC, owner])
            assert result.returncode == 0 and not result.stderr and result.stdout, (
                fixture.name, fixture.owner, result.returncode, result.stderr)
            for name, (_, _, public) in fixture.objects.items():
                declarations = re.findall(r'^(export )?data \$'+re.escape(name)+r' = align (\d+) \{', result.stdout, re.M)
                assert len(declarations) == 1 and bool(declarations[0][0]) == public, (fixture.name, result.stdout)
                width, bits, _ = fixture.objects[name]
                assert int(declarations[0][1]) == width, (fixture.name, result.stdout)
                body = re.search(r'^'+('export ' if public else '')+r'data \$'+re.escape(name)+r' = align \d+ \{ ([^}]+) \}$', result.stdout, re.M)
                assert body, (fixture.name, name, result.stdout)
                encoding, encoded = body[1].split()
                initialized = fixture.objects if fixture.initialized is None else fixture.initialized
                if encoding == 'z':
                    assert name not in initialized, (fixture.name, 'explicit initializer lost typed encoding', body[1])
                    assert bits == 0 and int(encoded) == width, (fixture.name, name, body[1])
                else:
                    assert name in initialized, (fixture.name, 'tentative initializer changed form', body[1])
                    assert encoding == {1: 'b', 2: 'h', 4: 'w', 8: 'l'}[width], (fixture.name, body[1])
                    assert int(encoded) == bits % (1 << (width*8)), (fixture.name, body[1])
            assert '$missing' not in result.stdout and 'data $absent' not in result.stdout, result.stdout
            kcc_cases += 1
            if QBE:
                il.write_text(result.stdout)
                producer([QBE, '-t', 'amd64_sysv', '-o', assembly, il], assembly)
                assert not re.search(r'^\s*\.(?:comm|lcomm)\b', assembly.read_text(), re.M), assembly.read_text()
                producer([HOST, '-c', assembly, '-o', kcc_obj], kcc_obj)
                storage_evidence(kcc_obj, fixture.objects, qbe_labels=True)
                objects = [kcc_obj]
                if fixture.companion:
                    producer([HOST, '-std=c2x', '-pedantic-errors', '-fno-common', '-fsigned-char',
                              '-O0', '-c', companion, '-o', companion_obj], companion_obj)
                    objects.append(companion_obj)
                run_program(HOST, objects, exe)
                qbe_cases += 1
        for text, message in CONSTRAINTS:
            owner.write_text(text+'\n')
            if not options.native_only:
                reject(owner, message)
                rejection_count += 1
            for cc in compilers:
                native_obj.unlink(missing_ok=True)
                result = invoke([cc, '-std=c2x', '-pedantic-errors', '-fno-common', '-c', owner, '-o', native_obj])
                assert native_rejection(text, result, owner, native_obj, clang_style(cc)), (cc, text, result.stderr)
                counts[cc][2] += 1
        if not options.native_only:
            for text, message in DUPLICATES:
                owner.write_text(text+'\n')
                reject(owner, message)
                rejection_count += 1
            for expression, message in ARITHMETIC:
                # In particular a prior implicit bool conversion must not turn
                # 2147483647+1 into valid unsigned arithmetic and hide overflow.
                for typ in ['int', '_Bool', 'unsigned char']:
                    owner.write_text(f'{typ} cell={expression};\n')
                    reject(owner, message)
                    rejection_count += 1
            for text in DEFERRED:
                owner.write_text(text+'\n')
                reject(owner)
                rejection_count += 1
            # Generated boundaries compile only. Initialized objects share the
            # existing 256-object / 512-declaration budgets; tentative anchors
            # consume declarations but never create extra owned data.
            for amount in [256, 257]:
                owner.write_text('int '+','.join(f'g{i}={i}' for i in range(amount))+';\n')
                if amount == 256:
                    result = invoke([KCC, owner])
                    assert result.returncode == 0 and not result.stderr, result.stderr
                    assert len(re.findall(r'^export data \$g\d+ =', result.stdout, re.M)) == 256
                else:
                    reject(owner, 'external object limit (256)')
                    rejection_count += 1
            for amount in [512, 513]:
                owner.write_text('int cell;'*(amount-1)+'int cell=42;\n')
                if amount == 512:
                    result = invoke([KCC, owner])
                    assert result.returncode == 0 and not result.stderr, result.stderr
                    assert result.stdout == 'export data $cell = align 4 { w 42 }\n', result.stdout
                else:
                    reject(owner, 'declaration limit (512)')
                    rejection_count += 1
            # Data-only producer errors still report stdout write failure.
            owner.write_text('int cell=42;\n')
            with open('/dev/full', 'w') as full:
                result = subprocess.run([str(KCC), str(owner)], stdout=full,
                                        stderr=subprocess.PIPE, text=True, timeout=20)
            assert result.returncode == 1 and result.stderr == 'kcc: error: cannot write QBE output\n', result
        print(f'Integer initializers: {len(cases)} unchanged originals; KCC {kcc_cases}; '
              f'QBE/ELF/runtime {qbe_cases}; KCC compile-only refusals {rejection_count}')
        for cc, (agreements, gaps, constraints) in counts.items():
            print(f'{cc}: {agreements} unchanged ELF/runtime agreements, {gaps} keyword-unavailable '
                  f'(NOT agreements), {constraints} native constraints; keywords {sorted(supported[cc])}')
        if options.native_only:
            print('NATIVE-ONLY: no claim of KCC coverage')
        elif not QBE:
            print('QBE unset: no claim of KCC ELF/runtime coverage')


def reject(source, message=''):
    result = invoke([KCC, source])
    assert result.returncode == 1 and not result.stdout, (source.read_text(), result)
    assert re.fullmatch(re.escape(str(source))+r':\d+:\d+: error: [^\n]+\n', result.stderr), result.stderr
    assert message in result.stderr, (source.read_text(), message, result.stderr)


if __name__ == '__main__':
    main()

"""M15i2 null-only initialized pointer definitions, unchanged native originals.

KCC=... QBE=... CLANG_CC=... python3 tests/test_null_initializers.py
--native-only never claims KCC coverage. Arithmetic and deferred forms compile
only; native acceptance of null arithmetic/const loads is NOT an oracle.
All producer, diagnostic, keyword, ELF and runtime gates are imported from the
hardened integer suite. Null storage additionally forbids slot relocations.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile

from test_integer_initializers import (
    Fixture, KCC, HOST, QBE, invoke, producer, clang_style, elf_objects,
    storage_evidence, run_program, features_for, harness_self_test, reject, native_diagnostics,
)


def native_compilers(host, clang=None):
    """Run each selected executable once; an explicit invalid path is an error."""
    primary = shutil.which(host)
    assert primary, ('native compiler unavailable', host)
    result = [host]
    if clang:
        candidate = shutil.which(clang)
        assert candidate, ('additional native compiler unavailable', clang)
        if os.path.realpath(primary) != os.path.realpath(candidate):
            result.append(clang)
    return result


def compiler_selection_self_test(directory):
    # Canonical executable identity, not spelling, determines duplicate or style.
    clang = directory/'clang-selection-fixture'
    gcc = directory/'gcc-selection-fixture'
    for executable in (clang, gcc):
        executable.write_text('#!/bin/sh\nexit 0\n')
        executable.chmod(0o755)
    alias = directory/'primary-cc'
    alias.symlink_to(clang)
    assert native_compilers(str(clang), str(clang)) == [str(clang)]
    assert native_compilers(str(alias), str(clang)) == [str(alias)]
    assert native_compilers(str(clang), str(alias)) == [str(clang)]
    assert native_compilers(str(alias)) == [str(alias)]
    assert native_compilers(str(gcc), str(clang)) == [str(gcc), str(clang)]
    assert clang_style(str(alias)) and not clang_style(str(gcc))
    for host, additional in ((str(clang), str(directory/'missing-clang')),
                             (str(directory/'missing-primary'), str(clang))):
        try:
            native_compilers(host, additional)
        except AssertionError as error:
            assert 'unavailable' in str(error), error
        else:
            raise AssertionError('invalid explicit compiler silently ignored')


def fixtures():
    cases = []
    # Deliberately selected coverage, not a target/source/storage cross product.
    rows = [
        ('object zero', 'int *cell', '0', '', ()),
        ('private zero ICE', 'int *cell', '2-2', 'static ', ()),
        ('extern zero', 'int *cell', '0', 'extern ', ()),
        ('pointee const', 'const int *cell', '(void *)0', '', ()),
        ('top const', 'int *const cell', '0', 'static ', ()),
        ('both const', 'const int *const cell', '(const int *)0', '', ()),
        ('void', 'void *cell', '(int *)0', '', ()),
        ('qualified void', 'const void *cell', '(const int *)0', 'static ', ()),
        ('nested pointer', 'int **cell', '0', '', ()),
        ('incomplete array', 'int (*cell)[]', '(void *)0', '', ()),
        ('complete array', 'int (*cell)[3]', '0', 'static ', ()),
        ('function', 'int (*cell)(int)', '0', '', ()),
        ('function void NPC', 'int (*cell)(int)', '(void *)0', 'static ', ()),
        ('function typed', 'int (*cell)(int)', '(int (*)(int))0', '', ()),
        ('typed cast chain', 'int *cell', '(int *)(void *)(int *)0', '', ()),
        ('typed function chain', 'int (*cell)(int)', '(int (*)(int))(void *)0', '', ()),
        ('unsigned zero', 'int *cell', '4294967295U+1U', '', ()),
        ('cast zero', 'int *cell', '(unsigned char)256', '', ()),
        ('short circuit ICE', 'int *cell', '0 && (1/0)', '', ()),
        ('conditional integer ICE', 'int *cell', '1?0:1/0', '', ()),
        ('sizeof self ICE', 'int *cell', 'sizeof cell-8', '', ()),
        ('nullptr object', 'int *cell', 'nullptr', '', ('nullptr',)),
        ('nullptr function', 'int (*cell)(int)', 'nullptr', '', ('nullptr',)),
        ('nullptr incomplete', 'int (*cell)[]', 'nullptr', 'static ', ('nullptr',)),
        ('nullptr typed cast', 'int *cell', '(int *)nullptr', '', ('nullptr',)),
        ('nullptr type zero', 'int *cell', '(typeof(nullptr))0', '', ('typeof', 'nullptr')),
        ('nullptr type void zero', 'int *cell', '(typeof(nullptr))(void *)0', '', ('typeof', 'nullptr')),
        ('nullptr repeated casts', 'int *cell', '(typeof(nullptr))(typeof(nullptr))nullptr', '', ('typeof', 'nullptr')),
        ('nullptr nested casts', 'int *cell', '(int *)(typeof(nullptr))nullptr', '', ('typeof', 'nullptr')),
    ]
    for name, declaration, expression, storage, features in rows:
        prior = 'static ' if storage == 'static ' else ''
        # Escaping the address to a separately compiled function keeps even
        # internal const pointer objects observable to both native compilers.
        owner = (f'{prior}{declaration}; {storage}{declaration}={expression}; '
                 f'extern {declaration}; {prior}{declaration}; extern int *absent; '
                 'int observe(const void *); int main(void) { '
                 'if(sizeof cell!=8 || cell!=0) return 1; '
                 'if(!observe(&cell)) return 2; return 42; }')
        companion = 'int observe(const void *p) { return p!=0; }'
        cases.append(Fixture(name, owner, {'cell': (8, 0, storage != 'static ')},
                             companion, features))
    for name, declaration, expression, features in [
        ('alias', 'P cell', '(P)0', ()),
        ('query', 'typeof((int *)0) cell', 'nullptr', ('typeof', 'nullptr')),
        ('unqualified query', 'typeof_unqual((int *const)0) cell', '0', ('typeof_unqual',)),
    ]:
        cases.append(Fixture(name, 'typedef int *P; '+declaration+'='+expression+'; '
                             'int observe(const void *); int main(void) { '
                             'return cell==0 && observe(&cell)?42:1; }',
                             {'cell': (8, 0, True)},
                             'int observe(const void *p) { return p!=0; }', features))
    cases.extend([
        # These owner sources are the exact removed unsupported originals.
        # Separate companions observe null without adapting either original.
        Fixture('extern function', 'extern int (*fp)(int)=0;',
                {'fp': (8, 0, True)},
                'extern int (*fp)(int); int main(void) { return fp==0?42:1; }'),
        Fixture('extern alias', 'typedef int *T; extern T x=0;',
                {'x': (8, 0, True)},
                'extern int *x; int main(void) { return x==0?42:1; }'),
        Fixture('definition before tentative',
                'int *cell=0; int *cell; extern int *cell; '
                'int main(void) { return cell==0?42:1; }', {'cell': (8, 0, True)}),
        Fixture('same list ownership',
                'int *cell,*cell=0,*cell; int main(void) { return cell==0?42:1; }',
                {'cell': (8, 0, True)}),
        Fixture('cross TU mutable escape',
                'int *cell=0; extern int *absent; int **slot(void) { return &cell; } '
                'int check(void); int main(void) { return check(); }',
                {'cell': (8, 0, True)},
                'extern int *cell; int **slot(void); int check(void) { '
                'int x=42; if(cell!=0 || *slot()!=0 || slot()!=&cell) return 1; '
                '*slot()=&x; if(cell!=&x || *cell!=42) return 2; '
                '*slot()=0; return cell==0?42:3; }'),
        Fixture('internal extern definition',
                'static int *cell; extern int *cell=0; int *read(void) { return cell; } '
                'int check(void); int main(void) { return check(); }',
                {'cell': (8, 0, False)},
                'int *read(void); int check(void) { return read()==0?42:1; }'),
    ])
    # Exact former subset original: &* cancels without dereferencing null.
    cases.append(Fixture('promoted null address indirection', 'int *cell=&*(int *)0;',
                         {'cell': (8, 0, True)},
                         'extern int *cell; int main(void) { return cell==0?42:1; }'))
    # Exact former subset originals; query-derived nullptr scalar storage is
    # now supported by the storage milestone as well as pointer null slots.
    for name, owner in [
        ('promoted query nullptr value', 'typeof(nullptr) cell=nullptr;'),
        ('promoted query nullptr zero', 'typeof(nullptr) cell=0;'),
    ]:
        cases.append(Fixture(name, owner, {'cell': (8, 0, True)},
            'extern typeof(nullptr) cell; int main(void) { return cell==nullptr?42:1; }',
            ('typeof', 'nullptr')))
    return cases


# Native constraints are not conflated with supported-subset refusals. These
# execute nowhere. Native rejection strings are checked in full, per original.
CONSTRAINTS = [
    ('int *cell=1;', 'supported null constant expression',
     "initialization of 'int *' from 'int' makes pointer from integer without a cast [-Wint-conversion]",
     "incompatible integer to pointer conversion initializing 'int *' with an expression of type 'int' [-Wint-conversion]"),
    ('int *cell=(const void *)0;', 'pointer conversion',
     "initialization discards 'const' qualifier from pointer target type [-Wdiscarded-qualifiers]",
     "initializing 'int *' with an expression of type 'const void *' discards qualifiers [-Werror,-Wincompatible-pointer-types-discards-qualifiers]"),
    ('int *cell=(long *)0;', 'pointer conversion',
     "initialization of 'int *' from incompatible pointer type 'long int *' [-Wincompatible-pointer-types]",
     "incompatible pointer types initializing 'int *' with an expression of type 'long *' [-Werror,-Wincompatible-pointer-types]"),
]
DUPLICATES = [
    'int *cell=0; int *cell=0;',
    'static int *cell=0; static int *cell=(int *)0;',
    'extern int *cell=0; int *cell=0;',
    'int *cell=0,*cell=0;',
    'typedef int *P; P cell=0; typeof(cell) cell=0;',
]
DEFERRED = [
    'int *cell=(1?(int *)0:(int *)0);',
    'int *cell=(0,(int *)0);',
    'int *cell=(0,nullptr);',
    'int *other=0; int *cell=other;',
    'int *const other=0; int *cell=other;',
    'typeof(nullptr) other; int *cell=other;',
    'int *cell=cell;',
    'void *cell=cell;',
    'int *cell=(int *)1;',
    'int *cell=(int *)(_Bool)nullptr;',
    'int *cell=(int *)(long)(void *)0;',
    'int *cell=(int *)(typeof(nullptr))(0,nullptr);',
    'typeof(nullptr) other; int *cell=(int *)(typeof(nullptr))other;',
    'typeof(nullptr) get(void); int *cell=(int *)(typeof(nullptr))get();',
    'int *get(void); int *cell=get();',
    '_Bool cell=(int *)0;',  # Pointer support must not broaden integer ICEs.
    'long cell=(long)(int *)0;',
    'int *main=0;',
]
# No evaluated pointer arithmetic, even null+0. No native run/acceptance score.
ARITHMETIC = [
    'int *cell=(int *)0+0;', 'int *cell=(int *)0-0;',
    'int *cell=0*(1/0);',
    'int *cell=(2147483647+1)*0;',
    'int *cell=0*(1ULL<<64);',
    'int *cell=0*(-1<<1);',
    'int *cell=0*((-2147483647-1)/-1);',
    'int *cell=(int *)(0*(1/0));',
    'int *cell=(int *)((2147483647+1)*0);',
    'int *cell=(int *)(0*(1ULL<<64));',
    'int *cell=(int *)(0*(-1<<1));',
    'int *cell=(int *)(0*((-2147483647-1)/-1));',
]


def no_slot_relocations(path, names):
    """Zero bytes alone can hide R_X86_64_64 relocations. Check actual ELF slots."""
    data = path.read_bytes()
    assert data[:7] == b'\x7fELF\x02\x01\x01'
    h = struct.unpack_from('<16sHHIQQQIHHHHHH', data)
    assert h[1:3] == (1, 62) and h[11] == 64
    sections = [struct.unpack_from('<IIQQQQIIQQ', data, h[6]+i*h[11]) for i in range(h[12])]
    slots = []
    for s in sections:
        if s[1] != 2:
            continue
        assert s[9] == 24 and s[5] % 24 == 0
        strings_section = sections[s[6]]
        strings = data[strings_section[4]:strings_section[4]+strings_section[5]]
        for pos in range(s[4], s[4]+s[5], 24):
            name, _, _, section, offset, _ = struct.unpack_from('<IBBHQQ', data, pos)
            label = strings[name:strings.index(b'\0', name)].decode()
            if label in names and 0 < section < len(sections):
                slots.append((label, section, offset))
    assert sorted(n for n, _, _ in slots) == sorted(names), (path, slots, names)
    for s in sections:
        if s[1] not in (4, 9):  # SHT_RELA / SHT_REL
            continue
        width = 24 if s[1] == 4 else 16
        assert s[9] == width and s[5] % width == 0 and 0 < s[7] < len(sections)
        for pos in range(s[4], s[4]+s[5], width):
            offset = struct.unpack_from('<Q', data, pos)[0]
            for label, section, begin in slots:
                assert not (s[7] == section and begin <= offset < begin+8), (
                    path, label, 'relocation in null pointer storage', offset)


def expected_warnings(fixture, clang):
    if fixture.name in ('extern zero', 'extern function', 'extern alias', 'internal extern definition'):
        return (('warning', "'extern' variable has an initializer [-Wextern-initializer]" if clang
                 else "'"+{'extern function': 'fp', 'extern alias': 'x'}.get(fixture.name, 'cell')+"' initialized and declared 'extern'"),)
    nonliteral = (('warning', "expression which evaluates to zero treated as a null pointer constant of type 'int *' [-Wnon-literal-null-conversion]"),)
    if clang and fixture.name in ('private zero ICE', 'unsigned zero', 'cast zero', 'sizeof self ICE'):
        return nonliteral
    if clang and fixture.name in ('short circuit ICE', 'conditional integer ICE'):
        return (('warning', 'division by zero is undefined [-Wdivision-by-zero]'),) + nonliteral

    return ()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-only', action='store_true')
    parser.add_argument('--harness-self-test', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='kcc null initializers ') as tmp:
        d = Path(tmp)
        compiler_selection_self_test(d)
        harness_self_test(d)
        owner, companion, native, other, il, assembly, obj, exe = [d/n for n in
            ('owner.c', 'companion.c', 'native.o', 'other.o', 'k.ssa', 'k.s', 'k.o', 'program')]
        # Adversarial ELF self-check: native relocation has zero slot bytes, but
        # must fail this additional null-only authority gate.
        owner.write_text('int target; int *cell=&target;\n')
        producer([HOST, '-std=c2x', '-pedantic-errors', '-fno-common', '-c', owner, '-o', native], native)
        assert elf_objects(native)['cell'][0][-1] == bytes(8)
        try:
            no_slot_relocations(native, {'cell'})
        except AssertionError as error:
            assert 'relocation in null pointer storage' in str(error), error
        else:
            raise AssertionError('null relocation gate accepted a symbolic address')
        if args.harness_self_test:
            print('Null relocation trap and imported hardened harness self-tests passed')
            return
        clang = os.environ.get('CLANG_CC') or shutil.which('clang')
        compilers = native_compilers(HOST, clang)
        print('Native compilers:', ', '.join(compilers), flush=True)
        supported = {cc: features_for(cc, owner, native) for cc in compilers}
        counts = {cc: [0, 0, 0] for cc in compilers}
        kcc_count = qbe_count = rejected = 0
        cases = fixtures()
        assert len({f.name for f in cases}) == len(cases)
        for f in cases:
            owner.write_text(f.owner+'\n')
            companion.write_text(f.companion+'\n')
            for cc in compilers:
                if not set(f.features) <= supported[cc]:
                    counts[cc][1] += 1
                    continue
                if clang_style(cc) and f.name in ('nullptr type zero', 'nullptr type void zero'):
                    # Explicit compile-only implementation discrepancy, NOT a
                    # keyword gap or native agreement; never adapt the source.
                    native.unlink(missing_ok=True)
                    result = invoke([cc, '-std=c2x', '-pedantic-errors', '-fno-common',
                                     '-O0', '-c', owner, '-o', native])
                    source_type = 'int' if f.name == 'nullptr type zero' else 'void *'
                    expected = (('error', f"cannot cast an object of type '{source_type}' to 'nullptr_t'"),)
                    assert result.returncode == 1 and not result.stdout and not native.exists(), (f.name, result)
                    assert native_diagnostics(result.stderr, owner, f.owner+'\n', True) == expected, (f.name, result.stderr)
                    counts[cc][2] += 1
                    continue
                producer([cc, '-std=c2x', '-pedantic-errors', '-fno-common', '-O0',
                          '-c', owner, '-o', native], native, expected_warnings(f, clang_style(cc)))
                storage_evidence(native, f.objects)
                no_slot_relocations(native, f.objects)
                objects = [native]
                if f.companion:
                    producer([cc, '-std=c2x', '-pedantic-errors', '-fno-common', '-O0',
                              '-c', companion, '-o', other], other)
                    assert not (set(f.objects) & elf_objects(other).keys())
                    objects.append(other)
                run_program(cc, objects, exe)
                counts[cc][0] += 1
            if args.native_only:
                continue
            result = invoke([KCC, owner])
            assert result.returncode == 0 and not result.stderr and result.stdout, (f.name, result)
            data_lines = re.findall(r'^(?:export )?data .*$', result.stdout, re.M)
            expected = [('export ' if public else '')+f'data ${name} = align 8 {{ l 0 }}'
                        for name, (_, _, public) in f.objects.items()]
            assert sorted(data_lines) == sorted(expected), (f.name, result.stdout, expected)
            kcc_count += 1
            if QBE:
                il.write_text(result.stdout)
                producer([QBE, '-t', 'amd64_sysv', '-o', assembly, il], assembly)
                assert not re.search(r'^\s*\.(?:comm|lcomm)\b', assembly.read_text(), re.M)
                producer([HOST, '-c', assembly, '-o', obj], obj)
                storage_evidence(obj, f.objects, qbe_labels=True)
                no_slot_relocations(obj, f.objects)
                objects = [obj]
                if f.companion:
                    # These unchanged new companions themselves name the C23
                    # nullptr type. Choose a proven-capable compiler, never
                    # rewrite that type as an ABI-incompatible extern integer.
                    companion_cc = HOST
                    if f.name in ('promoted query nullptr value', 'promoted query nullptr zero'):
                        companion_cc = next((cc for cc in compilers if set(f.features) <= supported[cc]), None)
                        if companion_cc is None:
                            print(f'{f.name}: QBE storage checked; runtime NOT counted (no C23 companion compiler)')
                            continue
                    producer([companion_cc, '-std=c2x', '-pedantic-errors', '-fno-common', '-O0',
                              '-c', companion, '-o', other], other)
                    assert not (set(f.objects) & elf_objects(other).keys())
                    objects.append(other)
                run_program(HOST, objects, exe)
                qbe_count += 1
        # Import the same complete diagnostic parser, not a substring waiver.
        for text, message, gcc_error, clang_error in CONSTRAINTS:
            owner.write_text(text+'\n')
            if not args.native_only:
                reject(owner, 'error: '+('unsupported pointer conversion (incompatible pointers or integer/pointer conversion)' if message == 'pointer conversion' else 'file-scope pointer initializer requires a supported null or direct address constant expression')+'\n')
                rejected += 1
            for cc in compilers:
                native.unlink(missing_ok=True)
                result = invoke([cc, '-std=c2x', '-pedantic-errors', '-fno-common', '-c', owner, '-o', native])
                expected = (('error', clang_error if clang_style(cc) else gcc_error),)
                assert result.returncode == 1 and not result.stdout and not native.exists(), (cc, text, result)
                assert native_diagnostics(result.stderr, owner, text+'\n', clang_style(cc)) == expected, (cc, text, result.stderr, expected)
        if not args.native_only:
            for text in DUPLICATES + DEFERRED + ARITHMETIC:
                owner.write_text(text+'\n')
                message = 'file-scope pointer initializer requires a supported null or direct address constant expression'
                if text in DUPLICATES:
                    message = 'multiple initialized definitions of object'
                elif text in (
                        'int *cell=(int *)1;', 'int *cell=(int *)(_Bool)nullptr;',
                        'int *cell=(int *)(long)(void *)0;', 'long cell=(long)(int *)0;') or (
                        text in ARITHMETIC and '(int *)(' in text):
                    # Ordinary sema constraints can refuse a cast before the
                    # pure source validator sees its operand; not ICE evidence.
                    message = 'unsupported pointer conversion (incompatible pointers or integer/pointer conversion)'
                elif text.startswith('typeof(nullptr) cell='):
                    message = "query-derived external declarations require ';' for non-integer initializers"
                elif text == '_Bool cell=(int *)0;':
                    message = 'file-scope initializer must be an integer constant expression'
                elif text == 'int *main=0;':
                    message = 'initialized main object is not supported on the Linux target'
                elif text == 'int *cell=0*(1/0);':
                    message = 'division by zero in integer constant expression'
                elif text in ('int *cell=(2147483647+1)*0;', 'int *cell=0*((-2147483647-1)/-1);'):
                    message = 'signed overflow in integer constant expression'
                elif text == 'int *cell=0*(1ULL<<64);':
                    message = 'invalid shift count in integer constant expression'
                elif text == 'int *cell=0*(-1<<1);':
                    message = 'negative left operand in constant shift'
                reject(owner, 'error: '+message+'\n')
                rejected += 1
        print(f'Null initializers: {len(cases)} unchanged originals; KCC {kcc_count}; '
              f'QBE/ELF/no-relocation/runtime {qbe_count}; compile-only refusals {rejected}')
        for cc, (agreements, gaps, discrepancies) in counts.items():
            print(f'{cc}: {agreements} unchanged ELF/runtime agreements; {gaps} keyword-unavailable '
                  f'(NOT agreements); {discrepancies} exact compile-only conversion discrepancies (NOT agreements); 3 exact native constraints')
        if args.native_only:
            print('NATIVE-ONLY: no claim of KCC coverage')
        elif not QBE:
            print('QBE unset: no claim of KCC ELF/runtime coverage')


if __name__ == '__main__':
    main()

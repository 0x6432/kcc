"""P1 direct zero-addend address definitions: exact originals and ELF relocations.

KCC=... QBE=... CLANG_CC=... python3 tests/test_direct_address_initializers.py
--native-only validates unchanged originals, never claims KCC passed.
Every slot needs R_X86_64_64 to its actual object/function/literal base, with
normalized addend zero. Native section-symbol relocations are resolved against
the expected local symbol or literal storage, not mistaken for pointer offsets.
Only curated defined originals run. Deferred forms/UB examples compile only.
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
    Fixture, KCC, HOST, QBE, invoke, producer, clang_style, elf_objects,
    storage_evidence, run_program, features_for, harness_self_test, reject,
)
from test_null_initializers import no_slot_relocations, native_compilers, compiler_selection_self_test


@dataclass(frozen=True)
class Reference:
    kind: str
    name: str = ''
    contents: bytes = b''
    string_id: int = 0


@dataclass
class AddressFixture(Fixture):
    references: dict = None
    nulls: tuple = ()


def fixture(name, owner, companion, references, extra=None, private=(), features=(), nulls=(), initialized=None):
    objects = {n: (8, 0, n not in private) for n in references}
    objects.update({n: (8, 0, n not in private) for n in nulls})
    objects.update(extra or {})
    return AddressFixture(name, owner, objects, companion, features,
                          references=references, nulls=nulls, initialized=initialized)


def fixtures():
    obj = lambda name: Reference('object', name)
    fn = lambda name: Reference('function', name)
    string = lambda text, number=0: Reference('string', contents=text, string_id=number)
    migrated = [
        fixture('migrated tentative target original', 'int target; int *cell=&target;',
                'extern int target; extern int *cell; int main(void) { return cell==&target && *cell==0?42:1; }',
                {'cell': obj('target')}, {'target': (4, 0, True)}, initialized=('cell',)),
        fixture('migrated other tentative original', 'int other; int *cell=&other;',
                'extern int other; extern int *cell; int main(void) { return cell==&other && *cell==0?42:1; }',
                {'cell': obj('other')}, {'other': (4, 0, True)}, initialized=('cell',)),
        fixture('migrated string original', 'char *cell="x";',
                'extern char *cell; int main(void) { return cell[0]==120 && cell[1]==0?42:1; }',
                {'cell': string(b'x\0')}),
        fixture('migrated void function original', 'int f(void); int (*cell)(void)=f;',
                'int f(void) { return 42; } extern int (*cell)(void); int main(void) { return cell==f?cell():1; }',
                {'cell': fn('f')}),
        fixture('migrated int function original', 'int f(int); int (*cell)(int)=f;',
                'int f(int x) { return x+2; } extern int (*cell)(int); int main(void) { return cell==f?cell(40):1; }',
                {'cell': fn('f')}),
    ]
    return migrated + [
        fixture('extern object, canonical pointer owner',
                'extern int target; int *cell; int *cell=&target; extern int *cell; int *cell; '
                'int **slot(void) { return &cell; }',
                'int target=42; extern int *cell; int **slot(void); int main(void) { '
                'int x=40; if(cell!=&target || *cell!=42 || slot()!=&cell) return 1; '
                '*slot()=&x; if(*cell!=40) return 2; *slot()=&target; return *cell; }',
                {'cell': obj('target')}),
        fixture('defined object and sole owner',
                'int target=42; int *cell=&target; int target; extern int *cell;',
                'extern int target; extern int *cell; int main(void) { '
                'return cell==&target && *cell==42?42:1; }',
                {'cell': obj('target')}, {'target': (4, 42, True)}),
        fixture('multiple distinct bases and local section offset',
                'int first=40; static int target=42; int *cell=&target; int *other=&first;',
                'extern int first; extern int *cell; extern int *other; int main(void) { '
                'return *cell==42 && other==&first && *other==40 && cell!=other?42:1; }',
                {'cell': obj('target'), 'other': obj('first')},
                {'first': (4, 40, True), 'target': (4, 42, False)}),
        fixture('later defined object',
                'extern int target; int *cell=&target; int target=42;',
                'extern int target; extern int *cell; int main(void) { '
                'return cell==&target?*cell:1; }',
                {'cell': obj('target')}, {'target': (4, 42, True)}),
        fixture('private base and const pointer escape',
                'static int target=42; static int *const cell=&target; '
                'int *get(void) { return cell; } const void *slot(void) { return &cell; }',
                'int *get(void); const void *slot(void); int main(void) { '
                'return slot()!=0 && *get()==42?42:1; }',
                {'cell': obj('target')}, {'target': (4, 42, False)}, private=('cell',)),
        fixture('internal extern initialized definition',
                'extern int target; static int *cell; extern int *cell=&target; '
                'int *get(void) { return cell; }',
                'int target=42; int *get(void); int main(void) { '
                'return get()==&target?*get():1; }', {'cell': obj('target')}, private=('cell',)),
        fixture('self address', 'void *cell=&cell;',
                'extern void *cell; int main(void) { return cell==&cell?42:1; }',
                {'cell': obj('cell')}),
        fixture('address of pointer object not load', 'int *base=0; int **cell=&base;',
                'extern int *base; extern int **cell; int main(void) { int x=42; '
                'if(cell!=&base || *cell!=0) return 1; *cell=&x; '
                'if(base!=&x || **cell!=42) return 2; *cell=0; return 42; }',
                {'cell': obj('base')}, nulls=('base',)),
        fixture('incomplete array decay', 'extern int target[]; int *cell=target;',
                'int target[3]={40,41,42}; extern int *cell; int main(void) { '
                'return cell==target && cell[2]==42?42:1; }', {'cell': obj('target')}),
        fixture('incomplete array address then completion',
                'extern int target[]; int (*cell)[]=&target; extern int target[3];',
                'int target[3]={40,41,42}; extern int (*cell)[]; int main(void) { '
                'int (*p)[3]=cell; return cell==&target && (*p)[2]==42?42:1; }',
                {'cell': obj('target')}),
        fixture('array decay versus whole array',
                'extern int target[3]; int *cell=target; int (*whole)[3]=&target;',
                'int target[3]={40,41,42}; extern int *cell; extern int (*whole)[3]; '
                'int main(void) { return cell==target && whole==&target && '
                'cell[2]==42 && (*whole)[1]==41?42:1; }',
                {'cell': obj('target'), 'whole': obj('target')}),
        fixture('function designator and address plus null',
                'int target(int); int (*cell)(int)=target; int (*other)(int)=&target; '
                'int (*empty)(int)=0;',
                'int target(int x) { return x+2; } extern int (*cell)(int); '
                'extern int (*other)(int); extern int (*empty)(int); int main(void) { '
                'return cell==target && other==&target && empty==0 && cell(40)==42?42:1; }',
                {'cell': fn('target'), 'other': fn('target')}, nulls=('empty',)),
        fixture('private function and pointer',
                'static int target(int x) { return x+2; } '
                'static int (*const cell)(int)=&target; int call(int x) { return cell(x); } '
                'const void *slot(void) { return &cell; }',
                'int call(int); const void *slot(void); int main(void) { '
                'return slot()!=0 && call(40)==42?42:1; }',
                {'cell': fn('target')}, private=('cell',)),
        fixture('extern function pointer definition',
                'int target(int); extern int (*cell)(int)=&target;',
                'int target(int x) { return x+2; } extern int (*cell)(int); '
                'int main(void) { return cell==target?cell(40):1; }', {'cell': fn('target')}),
        fixture('alias pointer target',
                'typedef const int *P; extern int target; P cell=&target;',
                'int target=42; extern const int *cell; int main(void) { '
                'return cell==&target?*cell:1; }', {'cell': obj('target')}),
        fixture('query target',
                'extern int target; typeof(&target) cell=&target;',
                'int target=42; extern int *cell; int main(void) { '
                'return cell==&target?*cell:1; }', {'cell': obj('target')}, features=('typeof',)),
        fixture('compatible object void qualifier conversions',
                'extern int target; const void *cell=(const void *)&target; '
                'const int *other=(const int *)(void *)&target;',
                'int target=42; extern const void *cell; extern const int *other; '
                'int main(void) { return cell==&target && other==&target && *other==42?42:1; }',
                {'cell': obj('target'), 'other': obj('target')}),
        fixture('compatible incomplete array cast',
                'extern int target[3]; int (*cell)[]=(int (*)[])&target;',
                'int target[3]={40,41,42}; extern int (*cell)[]; int main(void) { '
                'int (*p)[3]=cell; return p==&target && (*p)[2]==42?42:1; }',
                {'cell': obj('target')}),
        fixture('concatenated embedded NUL string', 'char *cell="ab\\0c" "d";',
                'extern char *cell; int main(void) { return cell[0]==97 && cell[1]==98 && '
                'cell[2]==0 && cell[3]==99 && cell[4]==100 && cell[5]==0?42:1; }',
                {'cell': string(b'ab\0cd\0')}),
        fixture('address of string array', 'char (*cell)[4]=&"abc";',
                'extern char (*cell)[4]; int main(void) { return sizeof *cell==4 && '
                '(*cell)[0]==97 && (*cell)[2]==99 && (*cell)[3]==0?42:1; }',
                {'cell': string(b'abc\0')}),
        fixture('string qualifier void conversion', 'const void *cell=(const void *)"xy";',
                'extern const void *cell; int main(void) { const char *p=cell; '
                'return p[0]==120 && p[1]==121 && p[2]==0?42:1; }',
                {'cell': string(b'xy\0')}),
        fixture('mixed strings without pooling assumption',
                'const char *cell="same"; const char *other="same"; const char *last="other";',
                'extern const char *cell; extern const char *other; extern const char *last; int main(void) { '
                'return cell[0]==115 && cell[3]==101 && cell[4]==0 && '
                'other[0]==115 && other[3]==101 && other[4]==0 && last[0]==111 && last[4]==114 && last[5]==0?42:1; }',
                {'cell': string(b'same\0'), 'other': string(b'same\0', 1), 'last': string(b'other\0', 2)}),
    ]


class ElfRelocations:
    """Minimal strict ELF64 relocation extension to the imported storage oracle."""
    def __init__(self, path):
        self.data = path.read_bytes()
        assert len(self.data) >= 64 and self.data[:7] == b'\x7fELF\x02\x01\x01'
        h = struct.unpack_from('<16sHHIQQQIHHHHHH', self.data)
        assert h[1:3] == (1, 62) and h[11] == 64 and h[12] > 0
        assert h[6]+h[11]*h[12] <= len(self.data)
        self.sections = [struct.unpack_from('<IIQQQQIIQQ', self.data, h[6]+i*64) for i in range(h[12])]
        self.symbols = []
        self.relocations = []
        tables = {}
        for index, section in enumerate(self.sections):
            if section[1] != 8:
                assert section[4]+section[5] <= len(self.data)
            if section[1] != 2:
                continue
            assert section[9] == 24 and section[5] % 24 == 0
            assert section[6] < len(self.sections)
            strings = self.section_bytes(section[6])
            table = []
            for offset in range(section[4], section[4]+section[5], 24):
                name, info, _, target, value, size = struct.unpack_from('<IBBHQQ', self.data, offset)
                assert name < len(strings) and b'\0' in strings[name:]
                label = strings[name:strings.index(b'\0', name)].decode()
                symbol = dict(name=label, kind=info & 15, binding=info >> 4,
                              section=target, value=value, size=size)
                self.symbols.append(symbol)
                table.append(symbol)
            tables[index] = table
        assert tables
        for section in self.sections:
            if section[1] not in (4, 9):
                continue
            assert section[1] == 4, 'x86-64 address slots require explicit RELA addends'
            assert section[9] == 24 and section[5] % 24 == 0
            assert section[6] in tables and 0 < section[7] < len(self.sections)
            for pos in range(section[4], section[4]+section[5], 24):
                offset, info, addend = struct.unpack_from('<QQq', self.data, pos)
                assert info >> 32 < len(tables[section[6]])
                self.relocations.append(dict(section=section[7], offset=offset, kind=info & 0xffffffff,
                                             symbol=tables[section[6]][info >> 32], addend=addend))

    def section_bytes(self, index):
        section = self.sections[index]
        assert section[1] != 8
        return self.data[section[4]:section[4]+section[5]]

    def symbol(self, name):
        matches = [s for s in self.symbols if s['name'] == name]
        assert len(matches) == 1, (name, matches)
        return matches[0]

    def slot_relocation(self, slot):
        symbol = self.symbol(slot)
        assert 0 < symbol['section'] < len(self.sections)
        matches = [r for r in self.relocations if r['section'] == symbol['section'] and
                   symbol['value'] <= r['offset'] < symbol['value']+8]
        assert len(matches) == 1, (slot, 'one relocation required', matches)
        relocation = matches[0]
        assert relocation['offset'] == symbol['value'], (slot, 'wrong SLOT offset', relocation)
        assert relocation['kind'] == 1, (slot, 'R_X86_64_64 required', relocation)
        return relocation

    def check(self, references):
        for name, expected in references.items():
            relocation = self.slot_relocation(name)
            symbol = relocation['symbol']
            if expected.kind == 'string':
                assert 0 < symbol['section'] < len(self.sections)
                section = self.sections[symbol['section']]
                assert section[2] & 2 and not section[2] & 4  # ALLOC, not EXECINSTR
                offset = symbol['value']+relocation['addend']
                contents = self.section_bytes(symbol['section'])
                assert 0 <= offset and offset+len(expected.contents) <= len(contents)
                assert contents[offset:offset+len(expected.contents)] == expected.contents, (
                    name, 'wrong literal base or addend', relocation, expected.contents)
                # Native assemblers may strip literal labels, using a section
                # symbol + literal-start offset. Literal content establishes the
                # semantic base; no assumption about equal-literal pooling.
            else:
                target = self.symbol(expected.name)
                if symbol['name'] == expected.name:
                    assert relocation['addend'] == 0, (name, 'nonzero base addend', relocation)
                else:
                    # Only a genuine section-symbol representation can stand in
                    # for the exact expected local symbol. A different named
                    # symbol at the same address is not silently accepted.
                    assert symbol['kind'] == 3 and target['section'] != 0
                    assert symbol['section'] == target['section']
                    assert symbol['value']+relocation['addend'] == target['value'], (
                        name, 'wrong local base/addend', relocation, target)
                if target['section']:
                    section = self.sections[target['section']]
                    assert bool(section[2] & 4) == (expected.kind == 'function')


def check_il(text, case):
    strings = {}
    pattern = r'^data \$\.Lkcc\.string\.(\d+) = align 1 \{\n((?:\tb \d+,?\n)+)\}$'
    for number, body in re.findall(pattern, text, re.M):
        assert int(number) not in strings
        strings[int(number)] = bytes(int(n) for n in re.findall(r'\tb (\d+)', body))
    expected_strings = {r.string_id: r.contents for r in case.references.values() if r.kind == 'string'}
    assert strings == expected_strings, (case.name, strings, expected_strings, text)
    remaining = re.sub(pattern, '', text, flags=re.M)
    actual = re.findall(r'^(?:export )?data .*$', remaining, re.M)
    expected = []
    for name, (width, bits, public) in case.objects.items():
        if name in case.references:
            reference = case.references[name]
            base = f'.Lkcc.string.{reference.string_id}' if reference.kind == 'string' else reference.name
            value = 'l $'+base
        elif case.initialized is not None and name not in case.initialized:
            value = 'z '+str(width)
        else:
            value = {4: 'w', 8: 'l'}[width]+' '+str(bits)
        expected.append(('export ' if public else '')+f'data ${name} = align {width} {{ {value} }}')
    assert sorted(actual) == sorted(expected), (case.name, actual, expected, text)


# Valid C but beyond direct zero-addend forms, plus deliberately undefined null
# arithmetic. None run and native acceptance is never scored as proof.
# Seven exact originals promoted to test_address_offsets.py positive fixtures.
DEFERRED = [
    'int target; int *cell=1?&target:&target;',
    'int target; int *cell=(0,&target);',
    'int target; int *base=&target; int *cell=base;',
    'int target; int *const base=&target; int *cell=base;',
    'int target; void *cell=cell;',
    'int target; int *cell=(int *)(long)&target;',
    'int target; _Bool cell=&target;',
    'int target; long cell=(long)&target;',
    'int target(int); void *cell=(void *)target;',
    'char target; int *cell=(int *)(void *)&target;',
    'char target; int *cell=(void *)&target;',
    'int *cell=(int *)0+0;',
    'int target[3]; int *cell=(target+4)-1;',
]
DUPLICATES = [
    'int target; int *cell=&target; int *cell=&target;',
    'int target; int *cell=0; int *cell=&target;',
    'int target; int *cell=&target; int *cell=0;',
]


CONSTRAINTS = [
    ('static int target(int); int (*cell)(int)=target;', 'referenced internal function requires a definition'),
    ('const int target=42; int *cell=&target;', 'unsupported pointer conversion (incompatible pointers or integer/pointer conversion)'),
    ('int target(int); int (*cell)(long)=target;', 'unsupported pointer conversion (incompatible pointers or integer/pointer conversion)'),
    ('int *cell=&missing;', 'use of undeclared identifier'),
]


def warnings(case, clang):
    if case.name in ('internal extern initialized definition', 'extern function pointer definition'):
        return (('warning', "'extern' variable has an initializer [-Wextern-initializer]" if clang
                 else "'cell' initialized and declared 'extern'"),)
    return ()


def controls(directory):
    """Adversarial missing/wrong slot/type/base/addend controls on real ELF."""
    import copy
    source, output = directory/'control.c', directory/'control.o'
    source.write_text('extern int target; extern int wrong; int *cell=&target;\n')
    producer([HOST, '-std=c2x', '-pedantic-errors', '-fno-common', '-c', source, '-o', output], output)
    original = ElfRelocations(output)
    expected = {'cell': Reference('object', 'target')}
    original.check(expected)
    for mutation in ('missing', 'slot', 'type', 'base', 'addend', 'duplicate'):
        damaged = copy.deepcopy(original)
        relocation = damaged.slot_relocation('cell')
        if mutation == 'missing':
            damaged.relocations.remove(relocation)
        elif mutation == 'slot':
            relocation['offset'] += 1
        elif mutation == 'type':
            relocation['kind'] = 10  # R_X86_64_32 is not a pointer slot relocation.
        elif mutation == 'base':
            relocation['symbol']['name'] = 'wrong'
        elif mutation == 'addend':
            relocation['addend'] = 1
        else:
            damaged.relocations.append(copy.deepcopy(relocation))
        try:
            damaged.check(expected)
        except AssertionError:
            pass
        else:
            raise AssertionError('address relocation oracle accepted '+mutation)
    # Pure zero bytes with NO relocation must not pass as an address.
    source.write_text('int *cell=0;\n')
    producer([HOST, '-std=c2x', '-pedantic-errors', '-fno-common', '-c', source, '-o', output], output)
    storage_evidence(output, {'cell': (8, 0, True)})
    try:
        ElfRelocations(output).check(expected)
    except AssertionError:
        pass
    else:
        raise AssertionError('zero bytes without an address relocation accepted')
    # A second defined local is intentionally NOT at section offset zero.
    source.write_text('static int first=40; static int target=42; int *cell=&target; '
                      'int read(void) { return first; }\n')
    producer([HOST, '-std=c2x', '-pedantic-errors', '-fno-common', '-O0', '-c', source, '-o', output], output)
    local = ElfRelocations(output)
    target = local.symbol('target')
    section_symbol = next(s for s in local.symbols if s['kind'] == 3 and s['section'] == target['section'])
    relocation = local.slot_relocation('cell')
    relocation['symbol'] = section_symbol
    relocation['addend'] = target['value']-section_symbol['value']
    local.check(expected)
    for mutation in ('section', 'addend', 'target'):
        damaged = copy.deepcopy(local)
        relocation = damaged.slot_relocation('cell')
        if mutation == 'section':
            relocation['symbol']['section'] = next(i for i, s in enumerate(damaged.sections) if s[2] & 4)
        elif mutation == 'addend':
            relocation['addend'] += 1
        else:
            relocation['addend'] = damaged.symbol('first')['value']-relocation['symbol']['value']
        try:
            damaged.check(expected)
        except AssertionError:
            pass
        else:
            raise AssertionError('local section relocation oracle accepted '+mutation)
    source.write_text('char *cell="alpha"; char *other="bravo"; int read(void) { return 0; }\n')
    producer([HOST, '-std=c2x', '-pedantic-errors', '-fno-common', '-O0', '-c', source, '-o', output], output)
    literal = ElfRelocations(output)
    expected_literal = {'cell': Reference('string', contents=b'alpha\0')}
    literal.check(expected_literal)
    for mutation in ('addend', 'target', 'bytes'):
        damaged = copy.deepcopy(literal)
        relocation = damaged.slot_relocation('cell')
        if mutation == 'addend':
            relocation['addend'] += 1
        elif mutation == 'target':
            other = damaged.slot_relocation('other')
            relocation['symbol'], relocation['addend'] = other['symbol'], other['addend']
        else:
            symbol = relocation['symbol']
            offset = damaged.sections[symbol['section']][4]+symbol['value']+relocation['addend']
            damaged.data = damaged.data[:offset]+b'Z'+damaged.data[offset+1:]
        try:
            damaged.check(expected_literal)
        except AssertionError:
            pass
        else:
            raise AssertionError('string relocation oracle accepted '+mutation)
    il_case = fixture('IL control', '', '', {'cell': Reference('string', contents=b'ab\0')})
    il = 'data $.Lkcc.string.0 = align 1 {\n\tb 97,\n\tb 98,\n\tb 0\n}\nexport data $cell = align 8 { l $.Lkcc.string.0 }\n'
    check_il(il, il_case)
    for damaged in (
            il.replace('l $.Lkcc.string.0', 'l 0'),
            il.replace('l $.Lkcc.string.0', 'l $.Lkcc.string.1'),
            il.replace('l $.Lkcc.string.0', 'l $.Lkcc.string.0 + 1'),
            il.replace('align 8', 'align 4'),
            il.replace('b 98', 'b 99')):
        try:
            check_il(damaged, il_case)
        except AssertionError:
            pass
        else:
            raise AssertionError('direct address IL oracle accepted damaged base/storage')
    print('Address relocation controls passed: named/local/string slot/type/base/addend/duplicate, zero-only storage and exact IL')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-only', action='store_true')
    parser.add_argument('--harness-self-test', action='store_true')
    options = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='kcc direct addresses ') as tmp:
        d = Path(tmp)
        harness_self_test(d)
        controls(d)
        compiler_selection_self_test(d)
        if options.harness_self_test:
            return
        owner, companion, native, other, il, assembly, obj, exe = [d/n for n in
            ('owner.c', 'companion.c', 'native.o', 'other.o', 'k.ssa', 'k.s', 'k.o', 'program')]
        clang = os.environ.get('CLANG_CC') or shutil.which('clang')
        compilers = native_compilers(HOST, clang)
        if not clang:
            print('Clang unavailable: NOT counted as a comparison')
        supported = {cc: features_for(cc, owner, native) for cc in compilers}
        counts = {cc: [0, 0] for cc in compilers}
        kcc_count = qbe_count = refused = 0
        cases = fixtures()
        assert len({f.name for f in cases}) == len(cases)
        for case in cases:
            owner.write_text(case.owner+'\n')
            companion.write_text(case.companion+'\n')
            for cc in compilers:
                if not set(case.features) <= supported[cc]:
                    counts[cc][1] += 1
                    continue
                producer([cc, '-std=c2x', '-pedantic-errors', '-fno-common', '-O0',
                          '-c', owner, '-o', native], native, warnings(case, clang_style(cc)))
                storage_evidence(native, case.objects)
                ElfRelocations(native).check(case.references)
                if case.nulls:
                    no_slot_relocations(native, case.nulls)
                producer([cc, '-std=c2x', '-pedantic-errors', '-fno-common', '-O0',
                          '-c', companion, '-o', other], other)
                entries = elf_objects(other)
                assert all(name not in entries for name, (_, _, public) in case.objects.items() if public)
                run_program(cc, [native, other], exe)
                counts[cc][0] += 1
            if options.native_only:
                continue
            result = invoke([KCC, owner])
            assert result.returncode == 0 and not result.stderr and result.stdout, (case.name, result)
            check_il(result.stdout, case)
            kcc_count += 1
            if QBE:
                il.write_text(result.stdout)
                producer([QBE, '-t', 'amd64_sysv', '-o', assembly, il], assembly)
                assert not re.search(r'^\s*\.(?:comm|lcomm)\b', assembly.read_text(), re.M)
                producer([HOST, '-c', assembly, '-o', obj], obj)
                storage_evidence(obj, case.objects, qbe_labels=True)
                ElfRelocations(obj).check(case.references)
                if case.nulls:
                    no_slot_relocations(obj, case.nulls)
                producer([HOST, '-std=c2x', '-pedantic-errors', '-fno-common', '-O0',
                          '-c', companion, '-o', other], other)
                entries = elf_objects(other)
                assert all(name not in entries for name, (_, _, public) in case.objects.items() if public)
                run_program(HOST, [obj, other], exe)
                qbe_count += 1
        if not options.native_only:
            for text, message in CONSTRAINTS:
                owner.write_text(text+'\n')
                reject(owner, 'error: '+message+'\n')
                refused += 1
            for text in DUPLICATES:
                owner.write_text(text+'\n')
                reject(owner, 'error: multiple initialized definitions of object\n')
                refused += 1
            for text in DEFERRED:
                owner.write_text(text+'\n')
                message = 'file-scope pointer initializer requires a supported null or direct address constant expression'
                if text in ('int target; int *cell=(int *)(long)&target;',
                            'int target; long cell=(long)&target;',
                            'int target(int); void *cell=(void *)target;'):
                    message = 'unsupported pointer conversion (incompatible pointers or integer/pointer conversion)'
                elif text == 'int target; _Bool cell=&target;':
                    message = 'file-scope initializer must be an integer constant expression'
                if text == 'int target[3]; int *cell=(target+4)-1;':
                    message = 'static pointer offset is outside its captured object bounds'
                reject(owner, 'error: '+message+'\n')
                refused += 1
        print(f'Direct addresses: {len(cases)} unchanged originals; KCC {kcc_count}; '
              f'QBE/exact-relocation/runtime {qbe_count}; compile-only refusals {refused}')
        for cc, (agreements, gaps) in counts.items():
            print(f'{cc}: {agreements} unchanged exact-relocation/runtime agreements; '
                  f'{gaps} keyword-unavailable (NOT agreements)')
        if options.native_only:
            print('NATIVE-ONLY: no claim of KCC coverage')
        elif not QBE:
            print('QBE unset: no claim of KCC ELF/runtime coverage')


if __name__ == '__main__':
    main()

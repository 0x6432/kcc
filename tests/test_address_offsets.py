"""Checked pointer constant offsets: unchanged originals and exact logical addends.

KCC=... QBE=... CLANG_CC=... python3 tests/test_address_offsets.py
--native-only never claims KCC coverage; --harness-self-test runs negative controls.
Only curated defined originals execute. Invalid bounds, overflowing indices and
conservative subset cases are KCC compile-only, NEVER a native UB oracle.
Imports the release's hardened producer/diagnostic/storage/compiler-selection
helpers; section-symbol representation offsets are not logical pointer addends.
"""
import argparse
import copy
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import tempfile

from test_integer_initializers import (
    KCC, HOST, QBE, invoke, producer, elf_objects, storage_evidence, run_program,
    features_for, harness_self_test, reject, clang_style,
)
from test_null_initializers import native_compilers, compiler_selection_self_test
from test_direct_address_initializers import (
    Reference, ElfRelocations, fixture, check_il as check_direct_il,
    controls as direct_controls,
)


@dataclass(frozen=True)
class OffsetReference(Reference):
    byte_addend: int = 0


class OffsetRelocations(ElfRelocations):
    """Compare symbol identity AND logical byte addend after normalization."""
    def check(self, references):
        for name, expected in references.items():
            assert 0 <= expected.byte_addend <= (1 << 63)-1
            relocation = self.slot_relocation(name)
            symbol = relocation['symbol']
            if expected.kind == 'string':
                assert 0 < symbol['section'] < len(self.sections)
                section = self.sections[symbol['section']]
                assert section[2] & 2 and not section[2] & 4
                # The bytes prove the literal's START, even for one-past and
                # embedded-NUL offsets; checking only a suffix would be weak.
                base = symbol['value']+relocation['addend']-expected.byte_addend
                contents = self.section_bytes(symbol['section'])
                assert 0 <= base and base+len(expected.contents) <= len(contents)
                assert contents[base:base+len(expected.contents)] == expected.contents, (
                    name, 'wrong literal base/logical addend', relocation, expected)
            else:
                target = self.symbol(expected.name)
                if symbol['name'] == expected.name:
                    logical = relocation['addend']
                else:
                    assert symbol['kind'] == 3 and target['section'] != 0
                    assert symbol['section'] == target['section']
                    logical = symbol['value']+relocation['addend']-target['value']
                assert logical == expected.byte_addend, (name, 'wrong logical addend', logical, expected)
                if target['section']:
                    section = self.sections[target['section']]
                    assert bool(section[2] & 4) == (expected.kind == 'function')


def check_storage(path, case, qbe_labels=False):
    storage_evidence(path, case.objects, qbe_labels=qbe_labels)
    arrays = getattr(case, 'arrays', {})
    records = elf_objects(path, {n: width for n, (width, _, _) in arrays.items()} if qbe_labels else None)
    for name, (width, alignment, public) in arrays.items():
        entries = records.get(name, [])
        assert len(entries) == 1, (name, entries)
        binding, size, actual_alignment, offset, contents = entries[0]
        assert (binding, size, contents) == (int(public), width, bytes(width)), (name, entries)
        assert actual_alignment >= alignment and offset % alignment == 0, (name, entries)
    if arrays:
        nm = invoke(['nm', '-S', path])
        assert nm.returncode == 0 and not nm.stderr
        for name in arrays:
            lines = [line.split() for line in nm.stdout.splitlines() if line.split()[-1] == name]
            assert len(lines) == 1 and lines[0][-2] in 'BDbd', (name, nm.stdout)


def check_il(text, case):
    for name, (width, alignment, public) in getattr(case, 'arrays', {}).items():
        line = ('export ' if public else '')+f'data ${name} = align {alignment} {{ z {width} }}'
        assert text.splitlines().count(line) == 1, (case.name, line, text)
        text = text.replace(line+'\n', '', 1)
    # Normalize ONLY exact expected slots; the direct oracle still checks all
    # data blocks, linkage, alignment, literals and unexpected/missing objects.
    for name, reference in case.references.items():
        if reference.byte_addend:
            base = (f'.Lkcc.string.{reference.string_id}' if reference.kind == 'string'
                    else reference.name)
            public = case.objects[name][2]
            prefix = ('export ' if public else '')+f'data ${name} = align 8 {{ '
            wanted = prefix+f'l ${base} + {reference.byte_addend} }}'
            assert text.splitlines().count(wanted) == 1, (case.name, wanted, text)
            text = text.replace(wanted, prefix+f'l ${base} }}', 1)
    check_direct_il(text, case)


def fixtures():
    cases = []
    obj = lambda addend, name='target': OffsetReference('object', name, byte_addend=addend)
    def array(name, expression, position, typ='int', width=4, features=()):
        cases.append(fixture(name, f'extern {typ} target[3]; {typ} *cell={expression};',
            f'{typ} target[3]={{40,41,42}}; extern {typ} *cell; int main(void) {{ '
            f'if(cell!=target+{position}) return 1; '
            +(f'return *cell=={40+position}?42:2;' if position < 3 else 'return cell[-1]==42?42:2;')+' }',
            {'cell': obj(position*width)}, features=features))
    for name, expression, position in [
        ('array forward', 'target+2', 2),
        ('commuted integer plus pointer', '2+target', 2),
        ('subtract negative index', 'target-(-2)', 2),
        ('onepast', 'target+3', 3),
        ('onepast moveback', '(target+3)-1', 2),
        ('negative signed moveback', '(target+3)+(-2)', 1),
        ('back to origin', '(target+3)-3', 0),
        ('nested positive intermediate', '((target+1)+1)-1', 1),
        ('unsigned zero strict ICE', 'target+(4294967295U+1U)', 0),
        ('unsigned negative narrowed to zero', 'target+(unsigned char)256', 0),
        ('shortcircuit strict ICE', 'target+(1?2:1/0)', 2),
        ('sizeof strict ICE', 'target+(sizeof(int)-2)', 2),
        ('negative unsigned narrow promotion', '(target+3)-(unsigned char)2', 1),
        ('compatible restored cast domain', '(int *)(void *)(target+1)+1', 2),
    ]:
        array(name, expression, position)
    array('short stride two', 'target+2', 2, 'short', 2)
    array('long long stride eight', '(target+3)-1', 2, 'long long', 8)
    array('char stride one', 'target+1', 1, 'char', 1)
    for name, expression, position in [
        ('scalar zero', '&target+0', 0),
        ('scalar onepast', '&target+1', 1),
        ('scalar moveback', '(&target+1)-1', 0),
        ('scalar negative moveback', '(&target+1)+(-1)', 0),
    ]:
        cases.append(fixture(name, f'extern int target; int *cell={expression};',
            'int target=42; extern int *cell; int main(void) { '
            f'return cell==&target+{position} && '+('*cell==42' if not position else 'cell[-1]==42')+'?42:1; }',
            {'cell': obj(4*position)}))
    cases += [
        fixture('private local base with representation offset',
            'static int first=40; static int target=42; static int *const cell=&target+1; '
            'int *get(void) { return cell; } const void *slot(void) { return &cell; } int read(void) { return first; }',
            'int *get(void); const void *slot(void); int read(void); int main(void) { return slot()!=0 && read()==40 && get()[-1]==42?42:1; }',
            {'cell': obj(4)}, {'first': (4, 40, False), 'target': (4, 42, False)}, private=('cell',)),
        fixture('canonical single pointer owner',
            'extern int target[3]; int *cell; int *cell=target+2; extern int *cell; int *cell; '
            'int **slot(void) { return &cell; }',
            'int target[3]={40,41,42}; extern int *cell; int **slot(void); int main(void) { '
            'if(slot()!=&cell || cell!=target+2 || *cell!=42) return 1; '
            '*slot()=target; if(*cell!=40) return 2; *slot()=target+2; return *cell; }',
            {'cell': obj(8)}),
        fixture('const void destination preserves offset',
            'extern const int target[3]; const void *cell=(const void *)(target+2);',
            'const int target[3]={40,41,42}; extern const void *cell; int main(void) { '
            'const int *p=cell; return p==target+2 && *p==42?42:1; }', {'cell': obj(8)}),
        fixture('pointer scalar stride', 'extern int *target; int **cell=&target+1;',
            'int value=42; int *target=&value; extern int **cell; int main(void) { '
            'return cell==&target+1 && *cell[-1]==42?42:1; }', {'cell': obj(8)}),
        fixture('known source-point bound before redeclaration',
            'extern int target[3]; int *cell=target+3; extern int target[];',
            'int target[3]={40,41,42}; extern int *cell; int main(void) { '
            'return cell==target+3 && cell[-1]==42?42:1; }', {'cell': obj(12)}),
    ]
    for name, literal, contents, expression, position in [
        ('string interior', '"abc"', b'abc\0', '"abc"+2', 2),
        ('string terminator', '"abc"', b'abc\0', '"abc"+3', 3),
        ('string onepast', '"abc"', b'abc\0', '"abc"+4', 4),
        ('string onepast moveback', '"abc"', b'abc\0', '("abc"+4)-2', 2),
        ('embedded NUL string', '"ab\\0c" "d"', b'ab\0cd\0', '("ab\\0c" "d"+6)-3', 3),
        ('empty string onepast', '""', b'\0', '""+1', 1),
    ]:
        # No comparison to a separately spelled literal: pooling is unspecified.
        access = f'cell[{len(contents)-1-position}]==0'
        if position < len(contents)-1:
            access += f' && cell[0]=={contents[position]}'
        cases.append(fixture(name, f'const char *cell={expression};',
            'extern const char *cell; int main(void) { return '+access+'?42:1; }',
            {'cell': OffsetReference('string', contents=contents, byte_addend=position)}))
    for name, expression, position in [
        ('subscript address interior', '&target[2]', 2),
        ('commuted subscript address', '&2[target]', 2),
        ('subscript address onepast', '&target[3]', 3),
        ('address indirection cancellation', '&*(target+2)', 2),
        ('address indirection onepast', '&*(target+3)', 3),
    ]:
        array(name, expression, position)
    for name, expression, position in [
        ('whole array zero', '&target+0', 0),
        ('whole array onepast', '&target+1', 1),
        ('whole array moveback', '(&target+1)-1', 0),
    ]:
        cases.append(fixture(name, f'extern int target[3]; int (*cell)[3]={expression};',
            'int target[3]={40,41,42}; extern int (*cell)[3]; int main(void) { '
            f'return cell==&target+{position} && '+
            ('(*cell)[2]==42' if not position else 'cell[-1][2]==42')+'?42:1; }',
            {'cell': obj(position*12)}))
    for name, declaration, expression, addend, check in [
        ('row array decay', 'int (*cell)[3]', 'target+1', 12, 'cell==target+1 && (*cell)[2]==42'),
        ('row onepast', 'int (*cell)[3]', 'target+2', 24, 'cell==target+2 && cell[-1][2]==42'),
        ('row onepast moveback', 'int (*cell)[3]', '(target+2)-1', 12, 'cell==target+1 && (*cell)[2]==42'),
        ('row address', 'int (*cell)[3]', '&target[1]', 12, 'cell==target+1 && (*cell)[2]==42'),
        ('inner subobject address', 'int *cell', '&target[1][2]', 20, 'cell==target[1]+2 && *cell==42'),
        ('inner subobject decay', 'int *cell', 'target[1]+2', 20, 'cell==target[1]+2 && *cell==42'),
        ('inner subobject onepast', 'int *cell', 'target[1]+3', 24, 'cell==target[1]+3 && cell[-1]==42'),
        ('inner subobject moveback', 'int *cell', '(target[1]+3)-2', 16, 'cell==target[1]+1 && cell[1]==42'),
        ('whole matrix onepast', 'int (*cell)[2][3]', '&target+1', 24, 'cell==&target+1 && cell[-1][1][2]==42'),
    ]:
        cases.append(fixture(name, f'extern int target[2][3]; {declaration}={expression};',
            f'int target[2][3]={{ {{10,11,12}}, {{40,41,42}} }}; extern {declaration}; '
            f'int main(void) {{ return {check}?42:1; }}', {'cell': obj(addend)}))
    cases.append(fixture('three dimensional subobject address',
        'extern int target[2][2][3]; int *cell=&target[1][1][2];',
        'int target[2][2][3]={{{1,2,3},{4,5,6}},{{7,8,9},{40,41,42}}}; '
        'extern int *cell; int main(void) { return cell==target[1][1]+2 && *cell==42?42:1; }',
        {'cell': obj(44)}))
    # Exact source originals promoted from the direct-address subset list.
    # The source is deliberately NOT rewritten to extern or split declarations.
    for name, owner, addend, extent in [
        ('promoted scalar plus zero', 'int target; int *cell=&target+0;', 0, 1),
        ('promoted array plus one', 'int target[3]; int *cell=target+1;', 4, 3),
        ('promoted subscript zero', 'int target[3]; int *cell=&target[0];', 0, 3),
        ('promoted address indirection', 'int target; int *cell=&*(&target);', 0, 1),
    ]:
        target_decl = 'extern int target;' if extent == 1 else 'extern int target[3];'
        compare = '&target' if extent == 1 else f'target+{addend//4}'
        case = fixture(name, owner, target_decl+' extern int *cell; int main(void) { '
            f'return cell=={compare} && *cell==0?42:1; }}', {'cell': obj(addend)},
            {'target': (4, 0, True)} if extent == 1 else {}, initialized=('cell',))
        if extent != 1:
            case.arrays = {'target': (12, 4, True)}
        cases.append(case)
    for name, owner, position in [
        ('unknown bound plus zero', 'extern int target[]; int *cell=target+0;', 0),
        ('unknown bound plus two', 'extern int target[]; int *cell=target+2;', 2),
        ('unknown bound then later completion', 'extern int target[]; int *cell=target+1; extern int target[3];', 1),
        ('unknown bound moveback', 'extern int target[]; int *cell=(target+3)-2;', 1),
    ]:
        cases.append(fixture(name, owner, 'int target[3]={40,41,42}; extern int *cell; int main(void) { '
            f'return cell==target+{position} && *cell=={40+position}?42:1; }}', {'cell': obj(position*4)}))
    cases.append(fixture('unknown outer bound known inner subobject',
        'extern int target[][3]; int *cell=target[1]+2;',
        'int target[2][3]={{10,11,12},{40,41,42}}; extern int *cell; int main(void) { '
        'return cell==target[1]+2 && *cell==42?42:1; }', {'cell': obj(20)}))
    cases.append(fixture('whole string onepast', 'char (*cell)[4]=&"abc"+1;',
        'extern char (*cell)[4]; int main(void) { return cell[-1][2]==99 && cell[-1][3]==0?42:1; }',
        {'cell': OffsetReference('string', contents=b'abc\0', byte_addend=4)}))
    # Exact originals promoted once explicit aligned reinterpret conversions
    # were included. No incompatible function call or aliasing dereference.
    cases += [
        fixture('promoted int address to char', 'int target; char *cell=(char *)&target;',
            'extern int target; extern char *cell; int main(void) { '
            'return cell==(char *)&target && cell[0]==0?42:1; }',
            {'cell': obj(0)}, {'target': (4, 0, True)}, initialized=('cell',)),
        fixture('promoted explicit qualifier discard',
            'const int target; int *cell=(int *)(const void *)&target;',
            'extern const int target; extern int *cell; int main(void) { '
            'return cell==(int *)&target && *cell==0?42:1; }',
            {'cell': obj(0)}, {'target': (4, 0, True)}, initialized=('cell',)),
        fixture('promoted function signature cast identity only',
            'int target(int); long (*cell)(long)=(long (*)(long))target;',
            'int target(int x) { return x; } extern long (*cell)(long); int main(void) { '
            'return cell==(long (*)(long))target?42:1; }',
            {'cell': OffsetReference('function', 'target')}),
        fixture('aligned incompatible object cast identity only',
            'extern long target; int *cell=(int *)&target;',
            'long target=42; extern int *cell; int main(void) { '
            'return (void *)cell==(void *)&target?42:1; }', {'cell': obj(0)}),
        fixture('array decay byteview of first element',
            'extern int target[3]; char *cell=(char *)target+1;',
            'int target[3]={40,41,42}; extern char *cell; int main(void) { '
            'return cell==(char *)target+1 && cell[-1]==40?42:1; }', {'cell': obj(1)}),
        fixture('explicit qualifier discard preserves array domain',
            'extern const int target[3]; int *cell=(int *)(const void *)target+0;',
            'const int target[3]={40,41,42}; extern int *cell; int main(void) { '
            'return cell==(int *)target && cell[2]==42?42:1; }', {'cell': obj(0)}),
        fixture('byteview subobject interior',
            'extern int target[3]; char *cell=(char *)(target+1)+3;',
            'int target[3]={40,41,42}; extern char *cell; int main(void) { '
            'return cell==(char *)(target+1)+3 && cell[-3]==41?42:1; }', {'cell': obj(7)}),
        fixture('byteview scalar onepast moveback',
            'extern int target; char *cell=((char *)&target+4)-4;',
            'int target=42; extern char *cell; int main(void) { '
            'return cell==(char *)&target && cell[0]==42?42:1; }', {'cell': obj(0)}),
        fixture('byteview whole array onepast',
            'extern int target[3]; char *cell=(char *)&target+12;',
            'int target[3]={40,41,42}; extern char *cell; int main(void) { '
            'return cell==(char *)&target+12 && cell[-4]==42?42:1; }', {'cell': obj(12)}),
    ]
    cases.append(fixture('unsigned character view of pointed scalar',
        'extern int target; unsigned char *cell=(unsigned char *)&target+1;',
        'int target=42; extern unsigned char *cell; int main(void) { '
        'return cell==(unsigned char *)&target+1 && cell[-1]==42?42:1; }', {'cell': obj(1)}))
    array('compatible origin restored through short cast', '(int *)(short *)target+2', 2)
    array('array domain restored at character onepast', '(int *)((char *)target+4)+1', 2)
    array('array domain restored through unsigned character onepast', '(int *)((unsigned char *)target+4)+1', 2)
    return cases


# No native compiler invocation or execution for ANY entry in these lists.
INVALID = [
    'extern int target[3]; int *cell=target+4;',
    'extern int target[3]; int *cell=target-1;',
    'extern int target[3]; int *cell=(target+4)-1;',
    'extern int target[3]; int *cell=(target-1)+1;',
    'extern int target[3]; int *cell=(target+3)+1;',
    'extern int target[3]; int *cell=target+18446744073709551615ULL;',
    'extern int target[3]; int *cell=target-18446744073709551615ULL;',
    'extern int target[3]; int *cell=target+(-9223372036854775807LL-1LL);',
    'extern int target[3]; int *cell=target-(-9223372036854775807LL-1LL);',
    'extern int target[3]; int *cell=target+(1/0);',
    'extern int target[3]; int *cell=target+(2147483647+1);',
    'extern int target; int *cell=&target+2;',
    'extern int target; int *cell=&target-1;',
    'char *cell="abc"+5;',
    'char *cell=("abc"+5)-1;',
    'char *cell=""-1;',
    'extern int target[2][3]; int (*cell)[3]=target+3;',
    'extern int target[2][3]; int *cell=target[2];',
    'extern int target[2][3]; int *cell=target[0]+4;',
    'extern int target[2][3]; int *cell=(target[0]+4)-1;',
    'extern int target[2][3]; int *cell=target[1]-1;',
    'extern int target[3]; int (*cell)[3]=&target+2;',
    'extern int target[3]; int *cell=&target[4];',
    'extern int target[3]; int *cell=&*(target+4);',
    'extern int target[]; int *cell=target-1;',
    'extern int target[]; int *cell=(target-1)+1;',
    'extern int target[]; int *cell=target+18446744073709551615ULL;',
    'extern int target[][3]; int *cell=target[0]+4;',
    'extern int target[2][2][3]; int *cell=target[0][1]+4;',
    'extern int target[2][2][3]; int *cell=target[0][2];',
    'extern int target[3]; char *cell=(char *)target+5;',
    'extern int target[3]; char *cell=(char *)(target+1)-1;',
    'extern int target[3]; char *cell=((char *)target+5)-1;',
    'extern int target[3]; char *cell=(char *)&target+13;',
    'extern int target[3]; signed char *cell=(signed char *)((unsigned char *)target+3)+2;',
]
DEFERRED = [
    'extern int target[]; int (*cell)[3]=(int (*)[3])&target+0;',
    'extern int target[3]; int *cell=1?target+1:target;',
    'extern int target[3]; int *cell=(0,target+1);',
    'extern int target[3]; int n; int *cell=target+n;',
    'extern int target[3]; const int n=1; int *cell=target+n;',
    'extern int target[3]; int *base=target; int *cell=base+1;',
    'int *cell=(int *)0+0;',
    'int *cell=((int *)0+1)-1;',
    'extern char target[3]; int *cell=(int *)(void *)target+0;',
    'extern int target[3]; void *cell=(void *)target+0;',
    'int target(void); int (*cell)(void)=target+0;',
    'extern long target; int *cell=(int *)&target+1;',
    'extern int target; int *cell=(int *)((char *)&target+1);',
    'extern int target; char *cell=(char *)(&target+1)+0;',
]


def refuses(source, text):
    source.write_text(text+'\n')
    # Hardened helper checks exit status, empty IL and exactly one complete
    # location-bearing diagnostic. Query statuses are checked by the AST suite.
    message = ''
    if text in INVALID:
        message = 'static pointer offset is outside its captured object bounds'
        if '(1/0)' in text:
            message = 'division by zero in integer constant expression'
        elif '(2147483647+1)' in text:
            message = 'signed overflow in integer constant expression'
        elif text in ('extern int target[2][3]; int *cell=target[2];',
                       'extern int target[2][2][3]; int *cell=target[0][2];'):
            message = 'static pointer decay requires an existing array subobject'
        elif text == 'extern int target[]; int *cell=target+18446744073709551615ULL;':
            message = 'static pointer offset exceeds the relocation addend limit'
    reject(source, 'error: '+message+'\n' if message else '')


def must_fail(action, label):
    try:
        action()
    except AssertionError:
        return
    raise AssertionError('offset oracle accepted '+label)


STRING_WARNINGS = (
    ('warning', "adding 'int' to a string does not append to the string [-Wstring-plus-int]"),
    ('note', 'use array indexing to silence this warning'),
)


def diagnostic_flags(cc):
    # Keep diagnostics, including notes, intact. Clang's diagrammatic insertion
    # fix-its contain source edits outside the inherited caret parser's grammar.
    return ['-fno-diagnostics-fixit-info'] if clang_style(cc) else []


def controls(directory):
    direct_controls(directory)
    source, output = directory/'offset-control.c', directory/'offset-control.o'
    source.write_text('extern int target[3]; int *cell=target+2;\n')
    producer([HOST, *diagnostic_flags(HOST), '-std=c2x', '-pedantic-errors', '-fno-common', '-O0', '-c', source, '-o', output], output)
    original = OffsetRelocations(output)
    expected = {'cell': OffsetReference('object', 'target', byte_addend=8)}
    original.check(expected)
    for mutation in ('missing', 'slot', 'type', 'base', 'addend', 'negative', 'duplicate'):
        damaged = copy.deepcopy(original)
        r = damaged.slot_relocation('cell')
        if mutation == 'missing': damaged.relocations.remove(r)
        elif mutation == 'slot': r['offset'] += 1
        elif mutation == 'type': r['kind'] = 10
        elif mutation == 'base': r['symbol']['name'] = 'wrong'
        elif mutation == 'addend': r['addend'] = 0
        elif mutation == 'negative': r['addend'] = -8
        else: damaged.relocations.append(copy.deepcopy(r))
        must_fail(lambda: damaged.check(expected), mutation)
    source.write_text('int first=40; static int target=42; int *cell=&target+1; '
                      'int read(void) { return first; }\n')
    producer([HOST, *diagnostic_flags(HOST), '-std=c2x', '-pedantic-errors', '-fno-common', '-O0', '-c', source, '-o', output], output)
    local = OffsetRelocations(output)
    expected = {'cell': OffsetReference('object', 'target', byte_addend=4)}
    local.check(expected)
    target = local.symbol('target')
    assert target['value'] > 0, 'local control must not collapse representation offset to zero'
    section = next(s for s in local.symbols if s['kind'] == 3 and s['section'] == target['section'])
    r = local.slot_relocation('cell')
    r['symbol'], r['addend'] = section, target['value']-section['value']+4
    local.check(expected)
    for addend in (4, target['value']-section['value'], target['value']-section['value']+8):
        damaged = copy.deepcopy(local)
        damaged.slot_relocation('cell')['addend'] = addend
        must_fail(lambda: damaged.check(expected), 'local representation/logical offset confusion')
    source.write_text('char *cell="ab\\0cd"+6; char *other="other"+2;\n')
    producer([HOST, *diagnostic_flags(HOST), '-std=c2x', '-pedantic-errors', '-fno-common', '-O0', '-c', source, '-o', output], output, STRING_WARNINGS*2 if clang_style(HOST) else ())
    literal = OffsetRelocations(output)
    expected = {'cell': OffsetReference('string', contents=b'ab\0cd\0', byte_addend=6)}
    literal.check(expected)
    for mutation in ('addend', 'base', 'bytes'):
        damaged = copy.deepcopy(literal)
        r = damaged.slot_relocation('cell')
        if mutation == 'addend': r['addend'] -= 1
        elif mutation == 'base':
            other = damaged.slot_relocation('other')
            r['symbol'], r['addend'] = other['symbol'], other['addend']+4
        else:
            base = r['symbol']['value']+r['addend']-6
            offset = damaged.sections[r['symbol']['section']][4]+base
            damaged.data = damaged.data[:offset]+b'Z'+damaged.data[offset+1:]
        must_fail(lambda: damaged.check(expected), 'literal '+mutation)
    case = fixture('offset IL control', '', '', {'cell': OffsetReference('object', 'target', byte_addend=8)})
    il = 'export data $cell = align 8 { l $target + 8 }\n'
    check_il(il, case)
    for damaged in (il.replace('+ 8', '+ 4'), il.replace(' + 8', ''), il.replace('+ 8', '- 8'),
                    il.replace('$target', '$wrong'), il.replace('l $', 'w $'),
                    il.replace('align 8', 'align 4'), il+il):
        must_fail(lambda: check_il(damaged, case), 'IL base/type/alignment/addend/duplicate')
    print('Offset negative controls passed: exact named/local/string logical addends and QBE IL')


def warnings(case, cc):
    if case.name in ('string interior', 'string terminator', 'string onepast',
                     'string onepast moveback', 'embedded NUL string', 'empty string onepast') and clang_style(cc):
        return STRING_WARNINGS
    if case.name == 'shortcircuit strict ICE' and clang_style(cc):
        return (('warning', 'division by zero is undefined [-Wdivision-by-zero]'),)
    return ()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-only', action='store_true')
    parser.add_argument('--harness-self-test', action='store_true')
    options = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='kcc address offsets ') as tmp:
        d = Path(tmp)
        harness_self_test(d)
        compiler_selection_self_test(d)
        controls(d)
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
                producer([cc, *diagnostic_flags(cc), '-std=c2x', '-pedantic-errors', '-fno-common', '-O0', '-c', owner, '-o', native], native, warnings(case, cc))
                check_storage(native, case)
                OffsetRelocations(native).check(case.references)
                producer([cc, *diagnostic_flags(cc), '-std=c2x', '-pedantic-errors', '-fno-common', '-O0', '-c', companion, '-o', other], other)
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
                check_storage(obj, case, qbe_labels=True)
                OffsetRelocations(obj).check(case.references)
                producer([HOST, *diagnostic_flags(HOST), '-std=c2x', '-pedantic-errors', '-fno-common', '-O0', '-c', companion, '-o', other], other)
                entries = elf_objects(other)
                assert all(name not in entries for name, (_, _, public) in case.objects.items() if public)
                run_program(HOST, [obj, other], exe)
                qbe_count += 1
        if not options.native_only:
            for text in INVALID+DEFERRED:
                refuses(owner, text)
                refused += 1
        print(f'Address offsets: {len(cases)} unchanged originals; KCC {kcc_count}; '
              f'QBE/exact-logical-relocation/runtime {qbe_count}; compile-only refusals {refused}')
        for cc, (agreements, gaps) in counts.items():
            print(f'{cc}: {agreements} unchanged exact-relocation/runtime agreements; '
                  f'{gaps} keyword-unavailable (NOT agreements)')
        if options.native_only:
            print('NATIVE-ONLY: no claim of KCC coverage')
        elif not QBE:
            print('QBE unset: no claim of KCC ELF/runtime coverage')


if __name__ == '__main__':
    main()

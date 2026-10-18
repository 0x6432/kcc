"""Independent M16 record identity/layout oracle. No aggregate by-value ABI.

HOST_CC/GCC13_CC/CLANG_CC/KCC/QBE select real tools. --native-only does not
claim KCC passed. Only defined originals execute, without source rewriting.
"""
import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import tempfile

from test_integer_initializers import (producer, invoke, elf_objects,
    native_diagnostics, clang_style, harness_self_test as inherited_self_test)

ROOT = Path(__file__).resolve().parents[1]
KCC = Path(os.environ.get('KCC', ROOT / 'build/kcc'))
QBE = os.environ.get('QBE', '/data/kcc-qbe/qbe-1.2/qbe')


@dataclass(frozen=True)
class Case:
    name: str
    declarations: str
    record: str
    size: int
    alignment: int
    members: tuple  # (designator, offset, assignment, expected scalar value)
    extra: str = ''


def cases():
    return [
        Case('member-static-assert-layout', 'struct I { short x; }; struct R { char lead; _Static_assert(sizeof(struct I)==2, "prior complete"); int value; _Static_assert(sizeof(int)==4, "int width"); };', 'struct R', 8, 4, (('lead', 0, '7', 7), ('value', 4, '42', 42))),
        Case('tail-padding', 'struct R { char a; int b; char c; };', 'struct R', 12, 4,
             (('a', 0, '-7', -7), ('b', 4, '1234567', 1234567), ('c', 8, '42', 42))),
        Case('signed-widths', 'struct R { signed char a; unsigned char b; short c; unsigned short d; long e; };',
             'struct R', 16, 8, (('a', 0, '-101', -101), ('b', 1, '255', 255),
             ('c', 2, '-12345', -12345), ('d', 4, '65535', 65535), ('e', 8, '4294967297L', 4294967297))),
        Case('union-overlay', 'union R { char a; long b; int c[3]; };', 'union R', 16, 8,
             (('a', 0, '42', 42), ('b', 0, '4294967297L', 4294967297), ('c[2]', 8, '73', 73))),
        Case('nested-array-tail', 'struct I { int a; char b; }; union U { long x; char bytes[9]; }; struct R { char lead; struct I items[3]; union U u; short tail; };',
             'struct R', 56, 8, (('lead', 0, '11', 11), ('items[0].a', 4, '43', 43),
             ('items[1].a', 12, '-42', -42), ('items[2].b', 24, '41', 41),
             ('u.x', 32, '123456789L', 123456789), ('tail', 48, '-99', -99))),
        Case('pointer-function-members', 'struct R { char lead; int *p; int (*fn)(int); struct R *next; };',
             'struct R', 32, 8, (('lead', 0, '42', 42),),
             'int check_pointers(void) { return cell.p==&anchor && cell.fn==callback && cell.next==&cell && cell.fn(*cell.p)==42; }'),
        Case('anonymous-promotion', 'struct R { char lead; union { int value; long wide; }; struct { short small; char last; }; };',
             'struct R', 24, 8, (('lead', 0, '4', 4), ('wide', 8, '4294967297L', 4294967297),
             ('small', 16, '-101', -101), ('last', 18, '42', 42))),
        Case('forward-typedef-namespace', 'struct R; typedef struct R Alias; typedef int R; struct R { R number; Alias *next; };',
             'Alias', 16, 8, (('number', 0, '42', 42),)),
        Case('qualified-member', 'struct I { long x; }; struct R { const int frozen; unsigned int changing; const struct I *p; };',
             'struct R', 16, 8, (('changing', 4, '42', 42),)),
        Case('record-array-multidimensional', 'struct I { char c; long x; }; struct R { struct I grid[2][3]; char tail; };',
             'struct R', 104, 8, (('grid[0][1].x', 24, '42', 42), ('grid[1][2].c', 80, '-7', -7), ('tail', 96, '99', 99))),
    ]


def original(case):
    # This exact owner is submitted to every compiler; no offsetof builtins or
    # host headers make an unsupported keyword look like an agreement.
    owner = case.declarations + '\nint anchor; int callback(int x) { return x+2; }\n'
    owner += f'{case.record} cell; static {case.record} private_cell;\n'
    owner += 'void *address(void) { return &cell; } void *private_address(void) { return &private_cell; }\n'
    owner += f'long record_size(void) {{ return sizeof({case.record}); }} long record_align(void) {{ return _Alignof({case.record}); }}\n'
    for i, (member, offset, assignment, value) in enumerate(case.members):
        owner += f'long offset_{i}(void) {{ return (char *)&cell.{member}-(char *)&cell; }}\n'
        owner += f'long read_{i}(void) {{ return cell.{member}; }}\n'
    owner += case.extra + '\n'
    companion = case.declarations + '\nextern int anchor; int callback(int);\n'
    companion += f'extern {case.record} cell; void *address(void); void *private_address(void); long record_size(void); long record_align(void);\n'
    for i in range(len(case.members)):
        companion += f'long offset_{i}(void); long read_{i}(void);\n'
    if case.extra:
        companion += 'int check_pointers(void);\n'
    companion += 'int main(void) { unsigned long i; unsigned char *p=address(); unsigned char *q=private_address();\n'
    companion += f'if(address()!=&cell || private_address()==&cell || record_size()!={case.size} || sizeof cell!={case.size} || record_align()!={case.alignment} || _Alignof({case.record})!={case.alignment}) return 1;\n'
    companion += f'if((unsigned long)p%{case.alignment} || (unsigned long)q%{case.alignment}) return 2;\n'
    companion += f'for(i=0;i<{case.size};i++) if(p[i] || q[i]) return 3;\n'
    # Union alternatives are assigned/read one at a time: never inactive-member
    # interpretation, uninitialized padding reads, pointer punning, or UB.
    for i, (member, offset, assignment, value) in enumerate(case.members):
        companion += f'if(offset_{i}()!={offset} || (char *)&cell.{member}-(char *)&cell!={offset}) return 4; cell.{member}={assignment}; if(read_{i}()!={value}L) return 5;\n'
    if case.extra:
        companion += 'anchor=40; cell.p=&anchor; cell.fn=callback; cell.next=&cell; if(!check_pointers()) return 6;\n'
    companion += 'return 42; }\n'
    return owner, companion


# These are valid C, deliberately separate from language constraints. They may
# be rejected only as the stated future milestone, never native disagreements.
UNSUPPORTED = {
    'M17 braced initializer': 'struct R { int x; }; struct R cell={42};',
    'M21 by-value argument': 'struct R { int x; }; int f(struct R r) { return r.x; }',
    'M21 by-value return': 'struct R { int x; }; struct R f(struct R *p) { return *p; }',
    'M22 bitfield': 'struct R { unsigned x:3; }; struct R cell;',
    'M22 flexible array': 'struct R { int n; char bytes[]; }; struct R cell;',
}
# Exact diagnostics supplied by the frozen implementation are intentionally not
# inferred from baseline failures. Native signatures below are case-specific.
CONSTRAINTS = {
    'duplicate-member': 'struct R { int x; int x; };',
    'void-member': 'struct R { void x; };',
    'function-member': 'struct R { int f(void); };',
    'self-by-value': 'struct R { struct R child; };',
    'incomplete-member': 'struct I; struct R { struct I child; };',
    'tag-kind': 'struct R; union R *p;',
    'tag-redefinition': 'struct R { int x; }; struct R { int y; };',
    'anonymous-duplicate': 'struct R { int x; struct { int x; }; };',
    'member-assert-false': 'struct R { int x; _Static_assert(0, "record false"); };',
    'member-assert-forward': 'struct I; struct R { _Static_assert(sizeof(struct I)==4, "incomplete"); int x; }; struct I { int x; };',
    'member-assert-self': 'struct R { int x; _Static_assert(sizeof(struct R)==4, "self incomplete"); };',
    'nominal-incompatible': 'struct A { int x; }; struct B { int x; }; struct A *p; void f(void) { struct B *q; p=q; }',
}
# No invalid/UB fixture is ever executed.


# Tag scope controls use the same originals on all tools. Their scalar results
# distinguish standalone shadowing from referring to the visible outer tag.
SCOPE_ORIGINALS = {
    'block-shadow': 'struct T { long x; }; int main(void) { struct T a; if(sizeof a!=8) return 1; { struct T; struct T { char x; }; struct T b; if(sizeof b!=1) return 2; } return sizeof(struct T)==8?42:3; }',
    'tag-ordinary-namespace': 'typedef int T; struct T { T x; }; int main(void) { struct T a; a.x=42; return a.x; }',
    'prototype-visible-file-tag': 'struct T; int f(struct T *); struct T { int x; }; int f(struct T *p) { return p->x; } int main(void) { struct T a; a.x=42; return f(&a); }',
    'definition-parameter-tag-scope': 'int f(struct T { int x; } *p) { struct T *q=p; return q->x; } int main(void) { return 42; }',
    'anonymous-distinct': 'struct { int x; } a; struct { int x; } b; int main(void) { a.x=40; b.x=2; return a.x+b.x; }',
}

GCC_ERRORS = {
    'member-assert-false': (('error', 'static assertion failed: "record false"'),),
    'member-assert-forward': (('error', "invalid application of 'sizeof' to incomplete type 'struct I'"), ('error', 'expression in static assertion is not an integer')),
    'member-assert-self': (('error', "invalid application of 'sizeof' to incomplete type 'struct R'"), ('error', 'expression in static assertion is not an integer')),

    'duplicate-member': (("error", "duplicate member 'x'"),),
    'void-member': (("error", "variable or field 'x' declared void"),),
    'function-member': (("error", "field 'f' declared as a function"),),
    'self-by-value': (("error", "field 'child' has incomplete type"),),
    'incomplete-member': (("error", "field 'child' has incomplete type"),),
    'tag-kind': (("error", "'R' defined as wrong kind of tag"),),
    'tag-redefinition': (("error", "redefinition of 'struct R'"), ("note", "originally defined here")),
    'anonymous-duplicate': (("error", "duplicate member 'x'"),),
    'nominal-incompatible': (("error", "assignment to 'struct A *' from incompatible pointer type 'struct B *' [-Wincompatible-pointer-types]"),),
}
CLANG_ERRORS = {
    'member-assert-false': (('error', 'static assertion failed: record false'),),
    'member-assert-forward': (('error', "invalid application of 'sizeof' to an incomplete type 'struct I'"), ('note', "forward declaration of 'struct I'")),
    'member-assert-self': (('error', "invalid application of 'sizeof' to an incomplete type 'struct R'"), ('note', "definition of 'struct R' is not complete until the closing '}'")),

    'duplicate-member': (("error", "duplicate member 'x'"), ("note", "previous declaration is here")),
    'void-member': (("error", "field has incomplete type 'void'"),),
    'function-member': GCC_ERRORS['function-member'],
    'self-by-value': (("error", "field has incomplete type 'struct R'"), ("note", "definition of 'struct R' is not complete until the closing '}'")),
    'incomplete-member': (("error", "field has incomplete type 'struct I'"), ("note", "forward declaration of 'struct I'")),
    'tag-kind': (("error", "use of 'R' with tag type that does not match previous declaration"), ("note", "previous use is here")),
    'tag-redefinition': (("error", "redefinition of 'R'"), ("note", "previous definition is here")),
    'anonymous-duplicate': (("error", "member of anonymous struct redeclares 'x'"), ("note", "previous declaration is here")),
    'nominal-incompatible': (("error", "incompatible pointer types assigning to 'struct A *' from 'struct B *' [-Werror,-Wincompatible-pointer-types]"),),
}


def native_constraints(tools, source, output):
    for cc in tools:
        for name, text in CONSTRAINTS.items():
            source.write_text(text+'\n'); output.unlink(missing_ok=True)
            flags = ['-fno-caret-diagnostics'] if clang_style(cc) and name == 'tag-kind' else []
            r = invoke([cc, '-std=c2x', '-pedantic-errors', *flags, '-fno-common', '-c', source, '-o', output])
            assert r.returncode == 1 and not r.stdout and not output.exists(), (cc, name, r)
            expected = (CLANG_ERRORS if clang_style(cc) else GCC_ERRORS)[name]
            if flags:
                # Exact complete no-caret stream, not a general parser waiver.
                assert r.stderr == (f"{source}:1:11: error: use of 'R' with tag type that does not match previous declaration\n"
                                    f"{source}:1:8: note: previous use is here\n"), r.stderr
            else:
                actual = native_diagnostics(r.stderr, source, source.read_text(), clang_style(cc))
                assert actual == expected, (cc, name, actual, expected, r.stderr)
    print(f'Native exact constraint rejections: {len(tools)*len(CONSTRAINTS)}')


KCC_CONSTRAINT_ERRORS = {
    'duplicate-member': 'duplicate or ambiguous record member name',
    'anonymous-duplicate': 'duplicate or ambiguous record member name',
    'void-member': 'record member must have complete object type (no void, function or incomplete member)',
    'function-member': 'record member must have complete object type (no void, function or incomplete member)',
    'self-by-value': 'record member must have complete object type (no void, function or incomplete member)',
    'incomplete-member': 'record member must have complete object type (no void, function or incomplete member)',
    'tag-kind': 'tag declared with a different record kind',
    'tag-redefinition': 'redefinition of record tag',
    'nominal-incompatible': 'unsupported pointer conversion (incompatible pointers or integer/pointer conversion)',
    'member-assert-false': 'static assertion failed: "record false"',
    'member-assert-forward': 'sizeof requires a complete object type',
    'member-assert-self': 'sizeof requires a complete object type',
}
KCC_FUTURE_ERRORS = {
    'M17 braced initializer': 'file-scope object initializers are not supported yet',
    'M21 by-value argument': 'aggregate function arguments are not supported yet (M21)',
    'M21 by-value return': 'aggregate function returns are not supported yet (M21)',
    'M22 bitfield': 'bit-fields are not supported yet (M22)',
    'M22 flexible array': 'flexible array members are not supported yet (M22)',
}


def kcc_reject(source, text, expected):
    source.write_text(text+'\n')
    result = invoke([KCC, source])
    assert result.returncode == 1 and not result.stdout, (text, result)
    pattern = re.escape(str(source))+r':1:([0-9]+): error: '+re.escape(expected)+r'\n'
    match = re.fullmatch(pattern, result.stderr)
    assert match and 1 <= int(match[1]) <= len(text), (text, expected, result.stderr)


def check_storage(path, case, qbe=False):
    records = elf_objects(path, {'cell': case.size, 'private_cell': case.size} if qbe else None)
    for name, binding in [('cell', 1), ('private_cell', 0)]:
        entries = records.get(name, [])
        assert len(entries) == 1, (case.name, name, entries)
        bind, size, alignment, offset, contents = entries[0]
        assert (bind, size, contents) == (binding, case.size, bytes(case.size)), (case.name, name, entries)
        assert alignment >= case.alignment and offset % case.alignment == 0, (case.name, name, entries)



def record_self_test(directory):
    inherited_self_test(directory)
    # Actual record-shaped ELF, independently adversarial against size, binding,
    # byte content and alignment. A fresh producer is required for every mutant.
    assembly, output = directory/'control.s', directory/'control.o'
    case = Case('harness-control', '', '', 12, 4, ())
    base = ('.data\n.balign {alignment}\n.globl cell\n.type cell,@object\n'
            'cell: .byte {byte}\n.zero 11\n.size cell,12\n'
            '.balign {alignment}\n{private_binding}.type private_cell,@object\n'
            'private_cell: .zero 12\n.size private_cell,12\n'
            '.section .note.GNU-stack,"",@progbits\n')
    cc = os.environ.get('HOST_CC', 'gcc')
    for alignment, byte, private_binding, must_pass in [
            (4, 0, '', True), (1, 0, '', False), (4, 1, '', False),
            (4, 0, '.globl private_cell\n', False)]:
        assembly.write_text(base.format(alignment=alignment, byte=byte, private_binding=private_binding))
        producer([cc, '-c', assembly, '-o', output], output)
        try:
            check_storage(output, case)
        except AssertionError:
            assert not must_pass
        else:
            assert must_pass, ('ELF mutant escaped', alignment, byte, private_binding)
    print('Record-shaped ELF alignment/bytes/binding mutation controls passed')

def compilers():
    values = [os.environ.get('HOST_CC', 'gcc'), os.environ.get('GCC13_CC', '/data/kcc-gcc13/gcc13'),
              os.environ.get('CLANG_CC', '/data/kcc-init-clang18/usr/bin/clang-18')]
    assert len(set(os.path.realpath(shutil.which(c) or c) for c in values)) == 3, values
    for major, cc in zip((11, 13, 18), values):
        version = invoke([cc, '--version'])
        assert version.returncode == 0 and not version.stderr, (cc, version.stderr)
        if major == 18:
            assert re.search(r'clang version 18[.]', version.stdout), (cc, version.stdout)
        else:
            identity = invoke([cc, '-dumpversion'])
            assert identity.returncode == 0 and not identity.stderr and identity.stdout.split('.')[0].strip() == str(major), (cc, identity)
        print(cc, version.stdout.splitlines()[0], flush=True)
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-only', action='store_true')
    parser.add_argument('--harness-self-test', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='kcc record layout ') as tmp:
        d = Path(tmp)
        record_self_test(d)
        if args.harness_self_test:
            return
        tools = compilers()
        owner, companion, obj, other, exe, il, asm, kobj = [d/n for n in ['owner.c', 'companion.c', 'owner.o', 'companion.o', 'program', 'owner.ssa', 'owner.s', 'kcc.o']]
        total = 0
        for case in cases():
            a, b = original(case)
            owner.write_text(a); companion.write_text(b)
            for cc in tools:
                flags = ['-std=c2x', '-pedantic-errors', '-fno-common', '-fsigned-char', '-O0']
                producer([cc, *flags, '-c', owner, '-o', obj], obj)
                check_storage(obj, case)
                producer([cc, *flags, '-c', companion, '-o', other], other)
                assert 'cell' not in elf_objects(other), case.name
                producer([cc, obj, other, '-o', exe], exe)
                r = invoke([exe]); assert (r.returncode, r.stdout, r.stderr) == (42, '', ''), (cc, case.name, r)
                total += 1
            if args.native_only:
                continue
            r = invoke([KCC, owner])
            assert r.returncode == 0 and not r.stderr and r.stdout, (case.name, r.returncode, r.stderr)
            for name, public in [('cell', True), ('private_cell', False)]:
                match = re.findall(r'^(export )?data \$'+name+r' = align (\d+) \{ z (\d+) \}$', r.stdout, re.M)
                assert match == [('export ' if public else '', str(case.alignment), str(case.size))], (case.name, name, r.stdout)
            il.write_text(r.stdout)
            producer([QBE, '-o', asm, il], asm)
            producer([tools[0], '-c', asm, '-o', kobj], kobj)
            check_storage(kobj, case, True)
            producer([tools[0], kobj, other, '-o', exe], exe)
            r = invoke([exe]); assert (r.returncode, r.stdout, r.stderr) == (42, '', ''), (case.name, r)
        scope_runs = 0
        for name, text in SCOPE_ORIGINALS.items():
            owner.write_text(text+'\n')
            for cc in tools:
                expected = ()
                if name == 'definition-parameter-tag-scope':
                    expected = (('warning', "declaration of 'struct T' will not be visible outside of this function [-Wvisibility]" if clang_style(cc)
                                 else "'struct T' declared inside parameter list will not be visible outside of this definition or declaration"),)
                producer([cc, '-std=c2x', '-pedantic-errors', '-fno-common', '-O0', '-c', owner, '-o', obj], obj, expected)
                producer([cc, obj, '-o', exe], exe)
                r = invoke([exe]); assert (r.returncode, r.stdout, r.stderr) == (42, '', ''), (name, r)
                scope_runs += 1
            if not args.native_only:
                r = invoke([KCC, owner])
                assert r.returncode == 0 and not r.stderr and r.stdout, (name, r)
                il.write_text(r.stdout)
                producer([QBE, '-o', asm, il], asm)
                producer([tools[0], '-c', asm, '-o', kobj], kobj)
                producer([tools[0], kobj, '-o', exe], exe)
                r = invoke([exe]); assert (r.returncode, r.stdout, r.stderr) == (42, '', ''), (name, r)
        print(f'Native scope original runs: {scope_runs}')
        native_constraints(tools, owner, obj)
        for name, text in UNSUPPORTED.items():
            owner.write_text(text+'\n')
            for cc in tools:
                producer([cc, '-std=c2x', '-pedantic-errors', '-fno-common', '-c', owner, '-o', obj], obj)
        if not args.native_only:
            assert set(KCC_CONSTRAINT_ERRORS) == set(CONSTRAINTS)
            assert set(KCC_FUTURE_ERRORS) == set(UNSUPPORTED)
            for name, text in CONSTRAINTS.items():
                kcc_reject(owner, text, KCC_CONSTRAINT_ERRORS[name])
            for name, text in UNSUPPORTED.items():
                kcc_reject(owner, text, KCC_FUTURE_ERRORS[name])
            print(f'KCC exact constraints: {len(CONSTRAINTS)}; valid unsupported: {len(UNSUPPORTED)} (separate, NOT agreements)')
        print(f'Native valid-future-milestone acceptances: {len(tools)*len(UNSUPPORTED)} (NOT M16 agreements)')
        print(f'Native defined original runs: {total}; KCC layout cases: {0 if args.native_only else len(cases())}', flush=True)


if __name__ == '__main__':
    main()

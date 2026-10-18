"""C inline TU-end linkage, external identity, and restricted-body release gate.

KCC=... QBE=... HOST_CC=gcc CLANG_CC=... python3 tests/test_inline_linkage.py
--native-only validates unchanged originals, never claims KCC coverage.
No optimization is required: every fixture has identical inline/external results.
Only defined originals execute; invalid sources are KCC compile-only refusals.
"""
import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import tempfile

from test_integer_initializers import (
    KCC, HOST, QBE, invoke, producer, run_program, features_for, harness_self_test, reject, clang_style, native_diagnostics,
)
from test_null_initializers import native_compilers, compiler_selection_self_test


@dataclass(frozen=True)
class InlineFixture:
    name: str
    source: str
    ownership: str = 'inline'  # inline-only, external definition, or static definition
    features: tuple = ()


BODY = 'inline int target(int x) { return x+2; }'
OBSERVE = 'int (*cell)(int)=target; int call(int x) { return target(x); }'


def fixtures():
    cases = [
        InlineFixture('inline definition', BODY),
        InlineFixture('repeated inline', 'inline inline int target(int x) { return x+2; }'),
        InlineFixture('specifier position', 'int inline target(int x) { return x+2; }'),
        InlineFixture('prior inline', 'inline int target(int); '+BODY),
        InlineFixture('later inline', BODY+' inline int target(int);'),
        InlineFixture('both inline declarations', 'inline int target(int); '+BODY+' inline int target(int);'),
        InlineFixture('extern before', 'extern int target(int); '+BODY, 'external'),
        InlineFixture('extern after', BODY+' extern int target(int);', 'external'),
        InlineFixture('plain before', 'int target(int); '+BODY, 'external'),
        InlineFixture('plain after', BODY+' int target(int);', 'external'),
        InlineFixture('extern inline before', 'extern inline int target(int); '+BODY, 'external'),
        InlineFixture('extern inline after', BODY+' extern inline int target(int);', 'external'),
        InlineFixture('extern inline definition', 'extern inline int target(int x) { return x+2; }', 'external'),
        InlineFixture('inline declaration ordinary definition',
                      'inline int target(int); int target(int x) { return x+2; }', 'external'),
        InlineFixture('block extern does not count', BODY+
                      ' int block(void) { extern int target(int); return target(40); }'),
        InlineFixture('block plain does not count', BODY+
                      ' int block(void) { int target(int); return target(40); }'),
        InlineFixture('block inline participates in definition requirement only', BODY+
                      ' int block(void) { inline int target(int); return target(40); }'),
        InlineFixture('static inline', 'static inline int target(int x) { return x+2; }', 'static'),
        InlineFixture('static repeated inline', 'inline static inline int target(int x) { return x+2; }', 'static'),
        InlineFixture('internal inherited extern', 'static inline int target(int); '
                      'extern inline int target(int x) { return x+2; }', 'static'),
        InlineFixture('return alias', 'typedef int I; inline I target(int x) { return x+2; }'),
        InlineFixture('function alias inline declarations',
                      'typedef int F(int); inline F target; '+BODY+' inline F target;'),
        InlineFixture('plain function alias after',
                      'typedef int F(int); '+BODY+' F target;', 'external'),
        InlineFixture('extern function alias before',
                      'typedef int F(int); extern F target; '+BODY, 'external'),
        InlineFixture('function query inline declaration', BODY+' inline typeof(target) target;', features=('typeof',)),
        InlineFixture('function query plain after', BODY+' typeof(target) target;', 'external', ('typeof',)),
        InlineFixture('const static permitted',
                      'inline int target(int x) { static const int n=2; return x+n; }'),
        InlineFixture('defer mutable static restriction until plain after',
                      'inline int target(int x) { static int n=2; return x+n; } int target(int);', 'external'),
        InlineFixture('defer internal reference restriction until extern after',
                      'static int n=2; inline int target(int x) { return x+n; } extern int target(int);', 'external'),
        InlineFixture('plain before allows internal reference',
                      'static int n=2; int target(int); inline int target(int x) { return x+n; }', 'external'),
        InlineFixture('internal inline permits mutable static',
                      'static inline int target(int x) { static int n=2; return x+n; }', 'static'),
        InlineFixture('unrelated private identifier is not a body reference',
                      'static int n=91; '+BODY+' int unrelated(void) { return n; }'),
        InlineFixture('external object reference allowed',
                      'int n=2; inline int target(int x) { return x+n; }'),
        InlineFixture('automatic shadow does not reference internal identifier',
                      'static int n=91; inline int target(int x) { int n=2; return x+n; } '
                      'int unrelated(void) { return n; }'),
        InlineFixture('automatic local allowed',
                      'inline int target(int x) { int n=2; return x+n; }'),
    ]
    assert len({c.name for c in cases}) == len(cases)
    return cases


# Deliberately separate from native disagreements: C compilers may diagnose some
# constraints as warnings. No failing or undefined original is ever executed.
CONSTRAINTS = [
    ('inline object', 'inline int object;'),
    ('inline initialized object', 'inline int object=42;'),
    ('inline pointer object', 'inline int (*pointer)(int);'),
    ('inline typedef', 'typedef inline int F(int);'),
    ('inline object alias', 'typedef int I; inline I object;'),
    ('inline pointer alias', 'typedef int (*P)(int); inline P object;'),
    ('inline parameter', 'int f(inline int x) { return x; }'),
    ('inline type name', 'int f(void) { return sizeof(inline int); }'),
    ('inline local object', 'int f(void) { inline int x=0; return x; }'),
    ('undefined unused inline', 'inline int missing(int);'),
    ('undefined inline after plain', 'int missing(int); inline int missing(int);'),
    ('undefined inline before extern', 'inline int missing(int); extern int missing(int);'),
    ('undefined inline function alias', 'typedef int F(int); inline F missing;'),
    ('undefined inline function query', 'int f(void); inline typeof(f) missing;'),
    ('undefined block inline', 'int f(void) { inline int missing(int); return 42; }'),
    ('internal reference in unreachable body', 'static int x=1; inline int f(void) { if(0) return x; return 42; }'),
    ('inline main', 'inline int main(void) { return 0; }'),
    ('main later inline', 'int main(void) { return 0; } inline int main(void);'),
    ('modifiable static in inline-only', 'inline int f(void) { static int x=42; return x; }'),
    ('modifiable static in nested block', 'inline int f(void) { { static int x=42; return x; } }'),
    ('const pointer is not const object', 'inline int f(void) { static const int *p=0; return p==0; }'),
    ('thread object in inline-only', 'inline int f(void) { static _Thread_local int x=42; return x; }'),
    ('internal object reference', 'static int x=42; inline int f(void) { return x; }'),
    ('internal const object reference', 'static const int x=42; inline int f(void) { return x; }'),
    ('internal object sizeof reference', 'static int x; inline int f(void) { return sizeof x; }'),
    ('internal function reference', 'static int g(void) { return 42; } inline int f(void) { return g(); }'),
    ('internal function sizeof reference', 'static int g(void) { return 42; } '
     'inline int f(void) { return sizeof &g; }'),
    ('internal object typeof reference', 'static int x; inline int f(void) { typeof(x) y=42; return y; }'),
    ('omitted body undeclared name', 'inline int f(void) { return missing; }'),
    ('omitted body incompatible return', 'inline int *f(void) { return 42; }'),
    ('omitted body invalid call', 'inline int f(void) { int x=0; return x(); }'),
    ('duplicate inline bodies', 'inline int f(void) { return 1; } inline int f(void) { return 2; }'),
    ('incompatible inline declarations', 'inline int f(int); inline long f(int x) { return x; }'),
]


def symbol_records(path):
    result = invoke(['nm', '--format=posix', path])
    assert result.returncode == 0 and not result.stderr, (path, result)
    records = [line.split() for line in result.stdout.splitlines()]
    assert records and all(len(r) >= 2 for r in records), (path, result.stdout)
    return records


def ownership_evidence(path, ownership, kcc=False):
    records = symbol_records(path)
    # KCC may give internal functions private generated labels, not C spelling.
    matches = [r for r in records if r[0] == 'target']
    if ownership == 'inline':
        assert len(matches) == 1 and matches[0][1] == 'U', (path, records)
    elif ownership == 'external':
        assert len(matches) == 1 and matches[0][1] == 'T', (path, records)
    elif not kcc:
        assert len(matches) == 1 and matches[0][1] == 't', (path, records)
    else:
        assert not any(r[0] == 'target' and r[1] in ('T', 'U') for r in records), (path, records)
        assert any(r[1] == 't' for r in records), (path, records)


def companion(ownership):
    definition = 'int target(int x) { return x+2; }' if ownership != 'external' else 'int target(int);'
    identity = 'cell==target' if ownership != 'static' else 'cell!=target'
    return (definition+' extern int (*cell)(int); int call(int); '
            'int main(void) { return '+identity+' && cell(40)==42 && call(40)==42?42:1; }')




def shared_header_identity(directory, compilers, native_only):
    """Two inline-only TUs plus one native external owner: no duplicate body."""
    sources = [directory/'header-user-a.c', directory/'header-user-b.c']
    objects = [directory/'header-user-a.o', directory/'header-user-b.o']
    for label, source in zip(('a', 'b'), sources):
        source.write_text(BODY+f' int (*cell_{label})(int)=target; '
                          f'int call_{label}(int x) {{ return target(x); }}\n')
    peer = directory/'header-owner.c'
    peer.write_text('int target(int x) { return x+2; } '
                    'extern int (*cell_a)(int); extern int (*cell_b)(int); '
                    'int call_a(int); int call_b(int); int main(void) { '
                    'return cell_a==target && cell_b==target && cell_a==cell_b && '
                    'call_a(40)==42 && call_b(40)==42 && cell_a(40)==42?42:1; }\n')
    other, exe = directory/'header-owner.o', directory/'header-program'
    for cc in compilers:
        for source, obj in zip(sources, objects):
            producer([cc, '-std=c2x', '-pedantic-errors', '-O0', '-fno-inline',
                      '-c', source, '-o', obj], obj)
            ownership_evidence(obj, 'inline')
        producer([cc, '-std=c2x', '-pedantic-errors', '-c', peer, '-o', other], other)
        run_program(cc, [*objects, other], exe)
    if not native_only:
        for index, (source, obj) in enumerate(zip(sources, objects)):
            result = invoke([KCC, source])
            assert result.returncode == 0 and not result.stderr and result.stdout, result
            assert not re.search(r'^(?:export )?function[^\n]*\$target\(', result.stdout, re.M)
            if QBE:
                il, assembly = directory/f'header-{index}.ssa', directory/f'header-{index}.s'
                il.write_text(result.stdout)
                producer([QBE, '-t', 'amd64_sysv', '-o', assembly, il], assembly)
                producer([HOST, '-c', assembly, '-o', obj], obj)
                ownership_evidence(obj, 'inline', kcc=True)
        if QBE:
            for cc in compilers:
                producer([cc, '-std=c2x', '-pedantic-errors', '-c', peer, '-o', other], other)
                run_program(cc, [*objects, other], exe)
    print('Shared-header 3-TU function identity: native'+
          (', KCC/QBE' if not native_only and QBE else '')+' passed')

def native_policy(case, cc, source, output):
    flags = [cc, '-std=c2x', '-pedantic-errors', '-fno-common', '-O0', '-fno-inline']
    expected = ()
    if not clang_style(cc):
        return flags, expected
    # Formatting-only: do not permit fix-it source insertions through the
    # hardened parser. Warnings themselves remain enabled and exactly checked.
    flags += ['-fno-diagnostics-fixit-info']
    if case.name in ('repeated inline', 'static repeated inline'):
        expected = (('warning', "duplicate 'inline' declaration specifier [-Wduplicate-decl-specifier]"),)
    if case.name == 'defer mutable static restriction until plain after':
        expected = (
            ('warning', 'non-constant static local variable in inline function may be different in different files [-Wstatic-local-in-inline]'),
            ('note', "use 'static' to give inline function 'target' internal linkage"),
        )
    if case.name in ('defer internal reference restriction until extern after',
                     'plain before allows internal reference'):
        # Clang18 diagnoses these standard-valid external-definition bodies.
        # Record strict disagreements; NEVER retry with permissive flags or
        # count rejected originals as native agreements/runtime passes.
        notes = (('note', "use 'static' to give inline function 'target' internal linkage"),
                 ('note', "'n' declared here"))
        output.unlink(missing_ok=True)
        strict = invoke([*flags, '-c', source, '-o', output])
        assert strict.returncode == 1 and not strict.stdout and not output.exists(), strict
        assert native_diagnostics(strict.stderr, source, source.read_text(), True) == (
            ('error', "static variable 'n' is used in an inline function with external linkage [-Werror,-Wstatic-in-inline]"), *notes), strict.stderr
        print(f'{cc}: exact strict diagnostic disagreement for {case.name}; NOT an agreement/runtime pass')
        return None, ()
    return flags, expected

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-only', action='store_true')
    options = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='kcc-inline-') as td:
        d = Path(td)
        harness_self_test(d)
        compiler_selection_self_test(d)
        clang = os.environ.get('CLANG_CC') or shutil.which('clang')
        compilers = native_compilers(HOST, clang)
        if not clang:
            print('Clang unavailable: NOT counted as a comparison')
        source, peer, native, other, il, assembly, obj, exe = [d/n for n in
            ('owner.c', 'peer.c', 'native.o', 'peer.o', 'owner.ssa', 'owner.s', 'owner.o', 'program')]
        supported = {cc: features_for(cc, source, native) for cc in compilers}
        counts = {cc: [0, 0, 0] for cc in compilers}
        kcc_count = qbe_count = rejected = 0
        for case in fixtures():
            original = case.source+' '+OBSERVE+'\n'
            source.write_text(original)
            peer.write_text(companion(case.ownership)+'\n')
            for cc in compilers:
                if not set(case.features) <= supported[cc]:
                    counts[cc][1] += 1
                    continue
                flags, expected = native_policy(case, cc, source, native)
                if flags is None:
                    counts[cc][2] += 1
                    continue
                producer([*flags, '-c', source, '-o', native], native, expected)
                assert source.read_text() == original, 'native original was rewritten'
                ownership_evidence(native, case.ownership)
                producer([*flags, '-c', peer, '-o', other], other)
                run_program(cc, [native, other], exe)
                counts[cc][0] += 1
            if options.native_only:
                continue
            result = invoke([KCC, source])
            assert result.returncode == 0 and not result.stderr and result.stdout, (case.name, result)
            if case.ownership == 'inline':
                assert not re.search(r'^(?:export )?function[^\n]*\$target\(', result.stdout, re.M), (case.name, result.stdout)
            kcc_count += 1
            if QBE:
                il.write_text(result.stdout)
                producer([QBE, '-t', 'amd64_sysv', '-o', assembly, il], assembly)
                producer([HOST, '-c', assembly, '-o', obj], obj)
                ownership_evidence(obj, case.ownership, kcc=True)
                # Every selected native toolchain supplies its own external body
                # and identity observer to the very same KCC-produced owner.
                for cc in compilers:
                    producer([cc, '-std=c2x', '-pedantic-errors', '-O0', '-fno-inline',
                              '-c', peer, '-o', other], other)
                    run_program(cc, [obj, other], exe)
                qbe_count += 1
        shared_header_identity(d, compilers, options.native_only)
        if not options.native_only:
            for name, text in CONSTRAINTS:
                source.write_text(text+'\n')
                try:
                    reject(source)
                except AssertionError as error:
                    raise AssertionError((name, text, error)) from error
                rejected += 1
        for cc, (passed, gaps, discrepancies) in counts.items():
            print(f'{cc}: {passed} unchanged inline originals, ownership+multi-TU runtime; {gaps} keyword gaps; {discrepancies} strict diagnostic discrepancies (NOT agreements)')
        print(f'KCC inline originals {kcc_count}; QBE/nm/multi-toolchain runtime {qbe_count}; compile-only refusals {rejected}')
        if options.native_only:
            print('NATIVE-ONLY: no claim of KCC coverage')
        elif not QBE:
            print('QBE unset: no claim of KCC object/runtime coverage')


if __name__ == '__main__':
    main()

"""M16 exact legacy lexical promotions and defined record witnesses.

The unchanged originals '->' and 'struct' from test_lex.c are TOKEN fragments,
not C translation units. They MUST succeed unchanged in --tokens mode with exact
kind/offset/EOF output; they cannot honestly be counted as runtime/native C cases.
The separate witnesses below exercise their new C semantics without replacing the
original checks. No full C legacy rejection was removed: 'int struct;' remains a
constraint violation in test_compile.py, and thread-storage native companions
already used records only in the native compiler.

[KCC=...] [HOST_CC=...] [QBE=...] python3 tests/test_record_promotions.py
QBE enables real object production and defined unchanged runtime comparisons.
The authoritative C23 vacuous-tag-storage matrix adds 112 fresh-tag programs,
36 scoped-tag programs, and 300 constraints (including exact source-point failures). Its runtime is tested, but native C23 keyword availability is
not counted as agreement; only the three portable witnesses compare natively.
"""
import os
from pathlib import Path
import subprocess
import tempfile

from test_integer_initializers import (invoke, producer, native_diagnostics,
    harness_self_test as producer_self_test, run_program)
from test_null_initializers import native_compilers, compiler_selection_self_test

ROOT = Path(__file__).resolve().parents[1]
KCC = Path(os.environ.get('KCC', ROOT / 'build' / 'kcc'))
HOST = os.environ.get('HOST_CC', 'cc')
QBE = os.environ.get('QBE')

# Exact original spellings and origin contexts are mandatory regression data.
# Appending a newline would change the original token fixture, so write exactly.
PROMOTIONS = [
    {'origin': 'tests/test_lex.c:test_errors/cases (baseline line 110)',
     'text': '->', 'tokens': '0:->\n2:eof\n',
     'formerly': 'token_invalid plus one diagnostic'},
    {'origin': 'tests/test_lex.c:test_errors/keyword (baseline line 120)',
     'text': 'struct', 'tokens': '0:struct\n6:eof\n',
     'formerly': 'token_unsupported_keyword without diagnostics'},
]

# Additional coverage, never substituted for the exact originals above.
TOKENS = [
    ('union', '0:union\n5:eof\n'),
    ('.', '0:.\n1:eof\n'),
    ('p->x.y', '0:identifier\n1:->\n3:identifier\n4:.\n5:identifier\n6:eof\n'),
    ('#define JOIN(a,b) a##b\nJOIN(str,uct)', '23:struct\n36:eof\n'),
]

WITNESSES = [
    ('dot-arrow',
     'struct S { int x; }; int main(void) { struct S s; struct S *p=&s; '
     'p->x=41; s.x++; return p->x; }\n', 42),
    ('union-anonymous',
     'struct S { union { int x; long y; }; }; '
     'int main(void) { struct S s; s.y=42; return s.y; }\n', 42),
    ('forward-and-nominal-self-pointer',
     'struct S; struct S { struct S *next; int value; }; '
     'int main(void) { struct S s; s.next=&s; s.value=42; return s.next->value; }\n', 42),
]


def tag_storage_cases():
    """N3096 6.7/6.7.1/6.7.2.1/6.7.4/6.9, not GCC warning policy.

    All accepted flags are vacuous: no object/function/typedef-name is declared.
    Combination constraints and ordinary object storage checks remain mandatory.
    Native keyword availability is NOT used as an oracle for this C23 matrix.
    """
    accepted, rejected = [], []
    for aggregate in ('struct', 'union'):
        for suffix in (f'{aggregate} S;', f'{aggregate} S {{int x;}};'):
            for storage in ('', 'extern ', 'static ', 'typedef ', 'thread_local ',
                            '_Thread_local ', 'thread_local static ', 'static thread_local ',
                            'thread_local extern ', 'extern _Thread_local ', 'const ', 'const static '):
                accepted.append((f'file/{storage}{suffix}', storage + suffix +
                                 ' int main(void) {return 42;}\n', 42))
                accepted.append((f'block/{storage}{suffix}', 'int main(void) {' +
                                 storage + suffix + 'return 42;}\n', 42))
            for storage in ('register ', 'auto '):
                accepted.append((f'block/{storage}{suffix}', 'int main(void) {' +
                                 storage + suffix + 'return 42;}\n', 42))
                rejected.append((f'file/{storage}{suffix}', storage + suffix + '\n'))
            for storage in ('inline ', 'auto static ', 'auto extern ', 'auto register ',
                            'auto typedef ', 'static extern ', 'thread_local typedef ',
                            'thread_local register ', 'thread_local auto ', 'static static ',
                            'typedef typedef ', 'thread_local thread_local '):
                rejected.append((f'file/{storage}{suffix}', storage + suffix + '\n'))
                rejected.append((f'block/{storage}{suffix}', 'int main(void) {' +
                                 storage + suffix + 'return 42;}\n'))
    accepted += [
        ('vacuous typedef preserves existing alias',
         'typedef int S; typedef struct S {int x;}; '
         'int main(void){ S x=42; return x;}\n', 42),
        ('vacuous typedef introduces no alias',
         'typedef struct S {int x;}; int S=42; int main(void){return S;}\n', 42),
        ('block typedef preserves existing alias',
         'typedef int S; int main(void){typedef struct S {int x;}; S x=42; return x;}\n', 42),
        ('block typedef introduces no alias',
         'int main(void){typedef struct S {int x;}; int S=42; return S;}\n', 42),
        ('vacuous register no object',
         'int main(void){register struct S {int x;}; struct S s; s.x=42; return s.x;}\n', 42),
        ('anonymous members valid',
         'struct S {union {int x;}; struct {int y;};}; '
         'int main(void){struct S s;s.x=41;s.y=1;return s.x+s.y;}\n', 42),
        ('tagged members with declarators valid',
         'struct S {struct I {int x;} i; int y;}; '
         'int main(void){struct S s;s.i.x=41;s.y=1;return s.i.x+s.y;}\n', 42),
        ('qualified tag completes same type',
         'const struct S; struct S {int x;}; '
         'int main(void){struct S s;s.x=42;return s.x;}\n', 42),
    ]
    rejected += [
        ('tagged member forward', 'struct O {struct I; int y;};\n'),
        ('tagged member definition', 'struct O {struct I {int x;}; int y;};\n'),
        ('qualified tagged member', 'struct O {const struct I {int x;}; int y;};\n'),
        ('file anonymous no entity', 'struct {int x;};\n'),
        ('block anonymous no entity', 'int main(void){struct {int x;};return 0;}\n'),
        ('no typedef alias introduced', 'typedef struct S; S object;\n'),
        ('block no typedef alias introduced',
         'int main(void){typedef struct S; S object;return 0;}\n'),
        ('ordinary block thread object unchanged',
         'int main(void){thread_local struct S {int x;} object;return 0;}\n'),
        ('ordinary auto inference unchanged', 'int main(void){auto object;return 0;}\n'),
        ('ordinary combined auto unchanged',
         'int main(void){auto static struct S {int x;} object;return 0;}\n'),
    ]
    return accepted, rejected


def prefixed_tag_cases():
    """6.7.2.3p10-13: only the exact plain form unconditionally declares.

    A prefixed/qualified no-definition reference to ANY visible tag declares no
    entity (6.7p2). Without a visible tag it introduces a fresh one, covered by
    tag_storage_cases. Definitions declare independently of the prefix.
    """
    accepted, rejected = [], []
    for aggregate in ('struct', 'union'):
        tag = f'{aggregate} S'
        incomplete, complete = tag + ';', tag + ' {long x;};'
        other = ('union' if aggregate == 'struct' else 'struct') + ' S;'
        prefixes = ('extern ', 'static ', 'typedef ', 'thread_local ', '_Thread_local ',
                    'thread_local static ', 'static thread_local ', 'thread_local extern ',
                    'extern _Thread_local ', 'const ', 'const static ')
        for prefix in prefixes:
            declaration = prefix + tag + ';'
            for prior in (incomplete, complete):
                rejected.append((f'file-visible/{prior}/{prefix}',
                                 prior + declaration + '\n'))
                rejected.append((f'block-visible/{prior}/{prefix}',
                                 'int main(void){' + prior + declaration + 'return 0;}\n'))
                rejected.append((f'outer-visible/{prior}/{prefix}',
                                 prior + 'int main(void){' + declaration + 'return 0;}\n'))
            rejected.append((f'outer-wrong-kind/{aggregate}/{prefix}',
                             other + 'int main(void){' + declaration + 'return 0;}\n'))
            # A prefixed definition shadows an outer visible tag normally.
            # The vacuous flag may not declare ordinary storage or a typedef.
            accepted.append((f'prefixed-definition/{aggregate}/{prefix}', complete +
                             'int main(void){' + prefix + tag + ' {int x;};' +
                             f'return sizeof({tag})==sizeof(int)?42:1;}}\n', 42))
        for prefix in ('register ', 'auto '):
            for prior in (incomplete, complete):
                declaration = prefix + tag + ';'
                rejected.append((f'block-visible/{prior}/{prefix}',
                                 'int main(void){' + prior + declaration + 'return 0;}\n'))
                rejected.append((f'outer-visible/{prior}/{prefix}',
                                 prior + 'int main(void){' + declaration + 'return 0;}\n'))
            rejected.append((f'outer-wrong-kind/{aggregate}/{prefix}',
                             other + 'int main(void){' + prefix + tag + ';return 0;}\n'))
        for declaration in (tag + ' const;', 'const ' + tag + ' const;',
                            'const const ' + tag + ';', tag + ' const const;'):
            rejected.append((f'postfix-qualifier/{aggregate}',
                             complete + 'int main(void){' + declaration + 'return 0;}\n'))
            accepted.append((f'fresh-postfix-qualifier/{aggregate}/{declaration}',
                             declaration + tag + ' {int x;}; int main(void){return 42;}\n', 42))
        accepted.append((f'plain-forward-shadow/{aggregate}', complete +
                         'int main(void){' + tag + ';' + tag + ' {int x;};' +
                         f'return sizeof({tag})==sizeof(int)?42:1;}}\n', 42))
        accepted.append((f'plain-forward-outer-wrong-kind/{aggregate}', other +
                         'int main(void){' + tag + ';' + tag + ' {int x;};' +
                         f'return sizeof({tag})==sizeof(int)?42:1;}}\n', 42))
        accepted.append((f'plain-forward-redeclaration/{aggregate}',
                         incomplete + complete + tag + '; int main(void){return 42;}\n', 42))
    return accepted, rejected


PREFIX_ACCEPT, PREFIX_REJECT = prefixed_tag_cases()
assert len(PREFIX_ACCEPT) == 36 and len(PREFIX_REJECT) == 182


TAG_ACCEPT, TAG_REJECT = tag_storage_cases()
assert len(TAG_ACCEPT) == 112 and len(TAG_REJECT) == 114


def require_success(result, context):
    assert result.returncode == 0 and not result.stderr, (context, result.returncode, result.stdout, result.stderr)


def exact_rejection(result, source, original, message):
    return (source.read_text() == original and result.returncode == 1 and not result.stdout and
            native_diagnostics(result.stderr, source, original, False) == (('error', message),))


def rejection_message(name):
    exact = {
        'tagged member forward': 'member declaration requires a declarator or anonymous record definition',
        'tagged member definition': 'member declaration requires a declarator or anonymous record definition',
        'qualified tagged member': 'member declaration requires a declarator or anonymous record definition',
        'file anonymous no entity': 'declaration without a declarator requires a tag name',
        'block anonymous no entity': 'declaration without a declarator requires a tag name',
        'no typedef alias introduced': 'expected integer type specifier',
        'block no typedef alias introduced': "expected ';' after expression",
        'ordinary block thread object unchanged': 'block-scope thread_local requires static or extern',
        'ordinary auto inference unchanged': 'inferred auto requires an assignment initializer',
        'ordinary combined auto unchanged': 'combined auto storage requires an inferred type',
    }
    if name in exact:
        return exact[name]
    spelling = name.split('/', 1)[1]
    prefixes = [
        ('register ', 'register storage class requires block scope'),
        ('auto static ', 'combined auto storage requires an inferred type'),
        ('auto extern ', 'combined auto storage requires an inferred type'),
        ('auto register ', 'combined auto storage requires an inferred type'),
        ('auto typedef ', 'multiple storage-class specifiers in one declaration'),
        ('static extern ', 'multiple storage-class specifiers in one declaration'),
        ('thread_local typedef ', 'thread_local may combine only with static or extern storage'),
        ('thread_local register ', 'thread_local may combine only with static or extern storage'),
        ('thread_local auto ', 'thread_local auto inference is not supported yet'),
        ('static static ', 'duplicate static storage-class specifier'),
        ('typedef typedef ', 'duplicate typedef storage-class specifier'),
        ('thread_local thread_local ', 'duplicate thread_local storage-class specifier'),
        ('inline ', 'inline requires a function identifier declaration'),
        ('auto ', 'file-scope auto declarations are not supported yet'),
    ]
    for prefix, message in prefixes:
        if spelling.startswith(prefix):
            return message
    raise AssertionError(('unclassified fixed constraint fixture', name))


def rejection_controls(source):
    original = 'int main(void) { int struct; return 0; }'
    message = 'record cannot combine with other type specifiers'
    source.write_text(original)
    stderr = f'{source}:1:22: error: {message}\n'
    good = subprocess.CompletedProcess([], 1, '', stderr)
    assert exact_rejection(good, source, original, message)
    for status in (0, 2, 127, -6, -9, -11):
        assert not exact_rejection(subprocess.CompletedProcess([], status, '', stderr), source, original, message)
    for poison in ('UNRELATED STDERR\n', f'{source}:1:1: warning: extra\n',
                   f'{source}:1:1: note: extra\n', f'{source}:1:1: error: extra\n',
                   'internal compiler error: failure\n', '1 error generated.\n'):
        assert not exact_rejection(subprocess.CompletedProcess([], 1, '', stderr + poison), source, original, message)
    for bad in (stderr.rstrip('\n'), stderr.replace(message, 'unrelated failure'), ''):
        assert not exact_rejection(subprocess.CompletedProcess([], 1, '', bad), source, original, message)
    assert not exact_rejection(subprocess.CompletedProcess([], 1, 'unexpected IL', stderr), source, original, message)
    source.write_text('int unrelated;')
    assert not exact_rejection(good, source, original, message)


with tempfile.TemporaryDirectory(prefix='kcc record exact promotions ') as temporary:
    directory = Path(temporary)
    compiler_selection_self_test(directory)
    producer_self_test(directory)
    compilers = native_compilers(HOST, os.environ.get('CLANG_CC'))
    source = directory / 'unchanged original.c'
    rejection_controls(source)
    for fixture in PROMOTIONS:
        source.write_text(fixture['text'])
        result = invoke([KCC, '--tokens', source])
        require_success(result, fixture)
        assert result.stdout == fixture['tokens'], (fixture, result.stdout)
    for text, expected in TOKENS:
        source.write_text(text)
        result = invoke([KCC, '--tokens', source])
        require_success(result, text)
        assert result.stdout == expected, (text, result.stdout, expected)

    # Exact unchanged reserved-keyword source and its intended diagnostic.
    original = 'int main(void) { int struct; return 0; }'
    source.write_text(original)
    result = invoke([KCC, source])
    assert exact_rejection(result, source, original, 'record cannot combine with other type specifiers'), result

    for index, (name, text, status) in enumerate(WITNESSES + TAG_ACCEPT + PREFIX_ACCEPT):
        assert status == 42  # shared run_program validates status AND empty streams
        source.write_text(text)
        result = invoke([KCC, source])
        require_success(result, name)
        assert result.stdout.strip(), (name, 'missing IL')
        if name.startswith(('file/', 'block/')):
            assert 'data ' not in result.stdout and '$S' not in result.stdout, (name, result.stdout)
        if QBE:
            il = directory / f'case-{index}.ssa'
            assembly = directory / f'case-{index}.s'
            obj = directory / f'case-{index}.o'
            executable = directory / f'case-{index}-kcc'
            il.write_text(result.stdout)
            producer([QBE, '-t', 'amd64_sysv', '-o', assembly, il], assembly)
            producer([HOST, '-c', assembly, '-o', obj], obj)
            assert obj.read_bytes().startswith(b'\x7fELF'), (name, 'not a produced ELF object')
            run_program(HOST, [obj], executable)
            if index < len(WITNESSES):
                for lane, cc in enumerate(compilers):
                    native_obj = directory / f'case-{index}-native-{lane}.o'
                    native_executable = directory / f'case-{index}-native-{lane}'
                    producer([cc, '-std=c11', '-pedantic-errors', '-fno-common', '-c', source, '-o', native_obj], native_obj)
                    run_program(cc, [native_obj], native_executable)

    for name, text in TAG_REJECT:
        source.write_text(text)
        result = invoke([KCC, source])
        assert exact_rejection(result, source, text, rejection_message(name)), (name, result)

    for name, text in PREFIX_REJECT:
        source.write_text(text)
        result = invoke([KCC, source])
        assert exact_rejection(result, source, text, 'declaration does not declare an entity'), (name, result)

    for aggregate in ('struct', 'union'):
        # Source-point completeness cannot be rescued by later completion.
        original = (f'{aggregate} S {{long x;}}; int main(void){{'
                    f'{aggregate} S; int n=sizeof({aggregate} S); '
                    f'{aggregate} S {{int x;}}; return n;}}\n')
        source.write_text(original)
        result = invoke([KCC, source])
        assert exact_rejection(result, source, original, 'sizeof requires a complete object type'), result
        other = 'union' if aggregate == 'struct' else 'struct'
        original = f'{other} S; {aggregate} S;\n'
        source.write_text(original)
        result = invoke([KCC, source])
        assert exact_rejection(result, source, original, 'tag declared with a different record kind'), result

print(f'{len(PROMOTIONS)} exact M16 lexical originals and {len(TOKENS)} additional token cases passed; '
      f'{len(WITNESSES)} defined C witnesses and {len(TAG_ACCEPT)} fresh-tag accepts; '
      f'{len(PREFIX_ACCEPT)} scoped-tag accepts; '
      f'{len(TAG_REJECT) + len(PREFIX_REJECT) + 4} constraints retained' +
      (' with QBE/ELF/runtime (native witnesses only)' if QBE else ' (runtime not requested)'))

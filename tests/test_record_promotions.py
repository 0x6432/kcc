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
The authoritative C23 vacuous-tag-storage matrix adds 112 accepted programs and
114 constraints. Its runtime is tested, but native C23 keyword availability is
not counted as agreement; only the three portable witnesses compare natively.
"""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
KCC = Path(os.environ.get('KCC', ROOT / 'build' / 'kcc'))
HOST = shlex.split(os.environ.get('HOST_CC', 'cc'))
QBE = shlex.split(os.environ['QBE']) if os.environ.get('QBE') else None

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


TAG_ACCEPT, TAG_REJECT = tag_storage_cases()
assert len(TAG_ACCEPT) == 112 and len(TAG_REJECT) == 114


def run(arguments):
    return subprocess.run([str(x) for x in arguments], capture_output=True,
                          text=True, timeout=15)


def require_success(result, context):
    assert result.returncode == 0 and not result.stderr, (context, result.returncode, result.stderr)


with tempfile.TemporaryDirectory(prefix='kcc record exact promotions ') as temporary:
    directory = Path(temporary)
    source = directory / 'unchanged original.c'
    for fixture in PROMOTIONS:
        source.write_text(fixture['text'])
        result = run([KCC, '--tokens', source])
        require_success(result, fixture)
        assert result.stdout == fixture['tokens'], (fixture, result.stdout)
    for text, expected in TOKENS:
        source.write_text(text)
        result = run([KCC, '--tokens', source])
        require_success(result, text)
        assert result.stdout == expected, (text, result.stdout, expected)

    # Preserve a real reserved-keyword rejection from test_compile.py exactly.
    # M16 promotes the token, NOT use of 'struct' as an ordinary identifier.
    source.write_text('int main(void) { int struct; return 0; }')
    result = run([KCC, source])
    assert result.returncode == 1 and 'error:' in result.stderr and not result.stdout, result

    for index, (name, text, status) in enumerate(WITNESSES + TAG_ACCEPT):
        # Matrix labels contain source punctuation: use a bounded index for paths.
        native_comparison = index < len(WITNESSES)
        source.write_text(text)  # unchanged bytes for BOTH compilers when compared
        result = run([KCC, source])
        require_success(result, name)
        assert result.stdout.strip(), (name, 'missing IL')
        if name.startswith(('file/', 'block/')):
            assert 'data ' not in result.stdout and '$S' not in result.stdout, (name, result.stdout)
        if QBE:
            il = directory / f'case-{index}.ssa'
            assembly = directory / f'case-{index}.s'
            obj = directory / f'case-{index}.o'
            executable = directory / f'case-{index}-kcc'
            native = directory / f'case-{index}-native'
            il.write_text(result.stdout)
            produced = run([*QBE, '-t', 'amd64_sysv', '-o', assembly, il])
            assert produced.returncode == 0, (name, produced.stderr)
            assert assembly.is_file() and assembly.stat().st_size > 0, name
            produced = run([*HOST, '-c', assembly, '-o', obj])
            assert produced.returncode == 0, (name, produced.stderr)
            assert obj.read_bytes().startswith(b'\x7fELF'), (name, 'not a produced ELF object')
            produced = run([*HOST, obj, '-o', executable])
            assert produced.returncode == 0, (name, produced.stderr)
            assert run([executable]).returncode == status, name
            if native_comparison:
                produced = run([*HOST, '-std=c11', '-pedantic-errors', '-fno-common', source, '-o', native])
                require_success(produced, name)
                assert run([native]).returncode == status, name

    for name, text in TAG_REJECT:
        source.write_text(text)
        result = run([KCC, source])
        assert result.returncode == 1 and 'error:' in result.stderr and not result.stdout, (name, result)

print(f'{len(PROMOTIONS)} exact M16 lexical originals and {len(TOKENS)} additional token cases passed; '
      f'{len(WITNESSES)} defined C witnesses and {len(TAG_ACCEPT)} tag-storage accepts; '
      f'{len(TAG_REJECT)} constraints retained' + (' with QBE/ELF/runtime (native witnesses only)' if QBE else ' (runtime not requested)'))

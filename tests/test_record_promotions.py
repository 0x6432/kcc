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

    for name, text, status in WITNESSES:
        source.write_text(text)  # unchanged bytes for BOTH compilers
        result = run([KCC, source])
        require_success(result, name)
        assert result.stdout.strip(), (name, 'missing IL')
        if QBE:
            il = directory / f'{name}.ssa'
            assembly = directory / f'{name}.s'
            obj = directory / f'{name}.o'
            executable = directory / f'{name}-kcc'
            native = directory / f'{name}-native'
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
            produced = run([*HOST, '-std=c11', '-pedantic-errors', '-fno-common', source, '-o', native])
            require_success(produced, name)
            assert run([native]).returncode == status, name

print(f'{len(PROMOTIONS)} exact M16 lexical originals and {len(TOKENS)} additional token cases passed; '
      f'{len(WITNESSES)} defined C witnesses accepted' + (' with QBE/ELF/native runtime' if QBE else ' (runtime not requested)'))

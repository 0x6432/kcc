"""Chosen ASCII/signed-byte character policy in preprocessing expressions."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root/'build'/'kcc'
oracle = root/'build'/'pp_oracle'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
characters = [(f"'{chr(value)}'", value) for value in range(32, 127) if value not in (39, 92)]
characters += [
    (r"'\0'", 0), (r"'\7'", 7), (r"'\12'", 10), (r"'\123'", 83),
    (r"'\177'", 127), (r"'\200'", -128), (r"'\377'", -1),
    (r"'\x0'", 0), (r"'\x41'", 65), (r"'\x7f'", 127),
    (r"'\x80'", -128), (r"'\xFF'", -1), (r"'\x000041'", 65),
    (r"'\a'", 7), (r"'\b'", 8), (r"'\f'", 12), (r"'\n'", 10),
    (r"'\r'", 13), (r"'\t'", 9), (r"'\v'", 11), (r"'\?'", 63),
    (r"'\''", 39), (r"'\\'", 92), (r''' '\"' '''.strip(), 34),
]
expressions = [(f'{text} == {value}', True) for text, value in characters]
expressions += [
    (r"'\xff' < 0", True), (r"'\xff' < 0U", False),
    (r"(1 ? '\xff' : 0U) > 0", True),
    (r"(1 ? '\xff' : 0U/0) > 0", True),
    (r"'A'+1 == 'B'", True), (r"'\n' == 012", True),
    (r"CHAR == 'A'", True), (r"C(,'a') == 97", True),
    (r"0 && '\xff'/0", False),
]
prefix = r"#define CHAR '\x41'" + '\n#define C(a,b) a##b\n'
with tempfile.TemporaryDirectory(prefix='kcc-pp-char-') as directory:
    directory = Path(directory)
    source = directory/'input.c'
    for text, selected in expressions:
        expected = '42' if selected else '0'
        source.write_text(prefix+f'#if {text}\n42\n#else\n0\n#endif\n')
        result = subprocess.run([str(oracle), '--pp', str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        assert result.stdout == f'pp-number:{expected}\n', (text, result.stdout)
        reference = subprocess.run([host, '-std=c2x', '-E', '-P', str(source)], capture_output=True, text=True, timeout=10)
        assert reference.returncode == 0 and reference.stdout.split() == [expected], (text, reference.stderr)
    for text, message in [
        ("''", 'expected one character'), ("'ab'", 'multicharacter'),
        (r"'\1234'", 'multicharacter'), (r"'\x'", 'expected digits'),
        (r"'\x100'", 'exceeds one byte'), (r"'\400'", 'exceeds one byte'),
        (r"'\777'", 'exceeds one byte'), (r"'\q'", 'unsupported character escape'),
        (r"'\u00ff'", 'unsupported character escape'),
        ("L'a'", 'prefixed'), ("u'a'", 'prefixed'), ("U'a'", 'prefixed'), ("u8'a'", 'prefixed'),
        ("'é'", 'non-ASCII'), ("0 && 'ab'", 'multicharacter'),
    ]:
        source.write_text(f'#if {text}\n#endif\nint main(void) {{ return 0; }}\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)
    for text in (r"'A'+1 == 'B'", r"'\xff' < 0", r"(1 ? '\xff' : 0U/0)>0", r"CHAR == C(,'A')"):
        for ending in ('\n', '\r\n', '\r'):
            source.write_bytes((prefix+f'#if {text}\nint main(void) {{ return 42; }}\n#else\n#error bad\n#endif\n').replace('\n', ending).encode())
            result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
            assert result.returncode == 0 and not result.stderr, result.stderr
            if qbe:
                il, assembly, executable = [directory/name for name in ('p.ssa', 'p.s', 'p')]
                il.write_text(result.stdout)
                subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
                subprocess.run([host, str(assembly), '-o', str(executable)], check=True, timeout=10)
                assert subprocess.run([str(executable)], timeout=5).returncode == 42
                subprocess.run([host, '-std=c2x', str(source), '-o', str(executable)], check=True, timeout=10)
                assert subprocess.run([str(executable)], timeout=5).returncode == 42
print(f'Character conditions passed ({len(expressions)} target host/model agreements; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

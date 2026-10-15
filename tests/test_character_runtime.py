"""Ordinary character constants: full target bytes, int type, macro provenance."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root/'build'/'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
characters = [(f"'{chr(value)}'", value) for value in range(32, 127) if value not in (39, 92)]
characters += [(f"'\\{value:03o}'", value if value < 128 else value-256) for value in range(256)]
characters += [(f"'\\x{value:02x}'", value if value < 128 else value-256) for value in range(256)]
characters += [(r"'\a'", 7), (r"'\b'", 8), (r"'\f'", 12), (r"'\n'", 10),
               (r"'\r'", 13), (r"'\t'", 9), (r"'\v'", 11), (r"'\?'", 63),
               (r"'\''", 39), (r"'\\'", 92), (r''' '\"' '''.strip(), 34),
               (r"'\x00000041'", 65)]
programs = []
for offset in range(0, len(characters), 24):
    checks = ''.join(f'if({text}!={value}) return 1;'
                     for text, value in characters[offset:offset+24])
    programs.append('int main(void) {'+checks+'return 42; }')
expressions = [(r"'\xff'<0", 1), (r"'\xff'<0U", 0), (r"'\xff'<0L", 1),
               (r"'\xff'<0UL", 0), (r"'\xff'+1", 0), (r"~'\xff'", 0),
               (r"'\x80'>>7", -1), (r"-'\x80'", 128), (r"!'\0'", 1),
               (r"'A'+1=='B'", 1), (r"(unsigned long long)'\xff'==18446744073709551615ULL", 1)]
programs += [f'int main(void) {{ if(({expression})=={value}) return 42; return 1; }}'
             for expression, value in expressions]
programs += [r"long long f(int x) { return x; } int main(void) { if(f('\xff')==-1LL) return 42; return 1; }",
             r"int main(void) { int x='\0'; if('A') x=41; return x+('\xff'||0); }",
             r"int main(void) { int x=0; 'A' && (x=42); '\0' && (x=1); return x; }"]
macro = "#define CHAR '\\x41'\n#define ID(x) x\n#define C(a,b) a##b\n"
for ending in ('\n', '\r\n', '\r'):
    programs.append((macro+"int main(void) { if(ID(CHAR)==C(,'A')) return 42; return 1; }\n").replace('\n', ending))
programs.append("int main(void) { if('\\x4\\\n1'==65) return 42; return 1; }\n")
with tempfile.TemporaryDirectory(prefix='kcc runtime character ') as directory:
    directory = Path(directory)
    source, il, assembly, executable = [directory/name for name in ('p.c', 'p.ssa', 'p.s', 'p')]
    for text in programs:
        source.write_bytes(text.encode())
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
            subprocess.run([host, str(assembly), '-o', str(executable)], check=True, timeout=10)
            assert subprocess.run([str(executable)], timeout=5).returncode == 42, text
        subprocess.run([host, '-std=c2x', '-fsigned-char', str(source), '-o', str(executable)],
                       capture_output=True, check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, text
    rejected = [("''", 'expected one character'), ("'ab'", 'multicharacter'),
                (r"'\x'", 'expected digits'), (r"'\x100'", 'exceeds one byte'),
                (r"'\400'", 'exceeds one byte'), (r"'\1234'", 'multicharacter'),
                (r"'\q'", 'unsupported character escape'), (r"'\u0041'", 'unsupported character escape'),
                ("'é'", 'non-ASCII'), ("L'a'", 'prefixed'), ("u'a'", 'prefixed'),
                ("U'a'", 'prefixed'), ("u8'a'", 'prefixed')]
    for spelling, message in rejected:
        source.write_text(f'int main(void) {{ return {spelling}; }}\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, result.stderr
    for definition, invocation, message in [(r"#define BAD '\x100'", 'BAD', 'exceeds one byte'),
                                             ('#define C(a,b) a##b', "C(u8,'A')", 'prefixed')]:
        source.write_text(definition+f'\nint main(void) {{ return {invocation}; }}\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, result.stderr
        assert ':2:25: error:' in result.stderr, result.stderr
    source.write_text("int main(void) { 'A'=0; return 0; }\n")
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 1 and not result.stdout and 'lvalue' in result.stderr, result.stderr
print(f'Runtime characters passed ({len(characters)} byte/escape checks in {len(programs)} host/model programs; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

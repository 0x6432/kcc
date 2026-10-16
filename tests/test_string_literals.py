"""Ordinary byte strings have static array storage and explicit decay.

No literal is modified and separate occurrences are never subtracted/ordered.
No equality result between different occurrences is promised.
"""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root / 'build' / 'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
programs = [
    'int main(void) { char *s=""; if(s[0]!=0 || (s+1)-s!=1) return 1; return 42; }',
    'int main(void) { char *s="abc"; if(s[0]!=97 || s[1]!=98 || 2[s]!=99 || s[3]!=0) return 1; '
    'if((s+4)-s!=4L || &s[4]!=s+4 || *"x"!=120 || "xy"[1]!=121) return 2; return 42; }',
    'int main(void) { char *s="a\\0b"; if(s[0]!=97 || s[1]!=0 || s[2]!=98 || s[3]!=0) return 1; return 42; }',
    'int main(void) { char *s="\\a\\b\\f\\n\\r\\t\\v\\\'\\\"\\?\\\\"; '
    'if(s[0]!=7 || s[1]!=8 || s[2]!=12 || s[3]!=10 || s[4]!=13 || s[5]!=9 || s[6]!=11) return 1; '
    'if(s[7]!=39 || s[8]!=34 || s[9]!=63 || s[10]!=92 || s[11]!=0) return 2; return 42; }',
    'int main(void) { char *s="\\1234\\xffg\\x00041"; '
    'if(s[0]!=83 || s[1]!=52 || (unsigned char)s[2]!=255 || s[3]!=103 || s[4]!=65 || s[5]!=0) return 1; return 42; }',
    'char *text(void) { return "hi"; } int main(void) { char *p=text(); '
    'if(p!=text() || p[0]!=104 || p[1]!=105 || p[2]!=0) return 1; return 42; }',
    '#define STR(x) #x\n#define OUT(x) STR(x)\nint main(void) { char *s=OUT(a + b); '
    'if(s[0]!=97 || s[1]!=32 || s[2]!=43 || s[3]!=32 || s[4]!=98 || s[5]!=0) return 1; return 42; }',
    '#define TEXT "hi"\nint main(void) { char *s=TEXT; if(s[0]!=104 || s[1]!=105 || s[2]!=0) return 1; return 42; }',
    'int main(void) { char *s="a\\\nb"; if(s[0]!=97 || s[1]!=98 || s[2]!=0) return 1; return 42; }',
    'int kcc_string_0(void) { return 42; } int main(void) { char *p="x"; if(p[0]!=120) return 1; return kcc_string_0(); }',
]
for escape in ['octal', 'hex']:
    spelling = ''.join(f'\\{i:03o}' if escape == 'octal' else f'\\x{i:02x}' for i in range(256))
    programs.append('int main(void) { char *s="' + spelling + '"; '
                    'for(int i=0;i<256;i=i+1) if((unsigned char)s[i]!=i) return 1; '
                    'if(s[256]!=0 || (s+257)-s!=257L) return 2; return 42; }')

with tempfile.TemporaryDirectory(prefix='kcc string literals ') as directory:
    directory = Path(directory)
    source, other, il, assembly, obj, executable = [directory / name for name in
                                                   ('k.c', 'h.c', 'p.ssa', 'p.s', 'h.o', 'p')]

    def compile_source(text):
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True,
                                text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)],
                           check=True, timeout=10)
        return result.stdout

    def link_and_run(host_text=None):
        objects = [str(assembly)]
        if host_text is not None:
            other.write_text(host_text)
            subprocess.run([host, '-std=c2x', '-fsigned-char', '-c', str(other),
                            '-o', str(obj)], capture_output=True, check=True, timeout=10)
            objects.append(str(obj))
        subprocess.run([host, *objects, '-o', str(executable)], check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, host_text

    for text in programs:
        compile_source(text)
        if qbe:
            link_and_run()
        result = subprocess.run([host, '-std=c2x', '-fsigned-char', str(source), '-o', str(executable)],
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, (text, result.stderr)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, text

    helpers = ('char *text(void) { return "hi\\0x"; } '
               'int inspect(char *s) { if(s[0]!=104 || s[1]!=105 || s[2]!=0) return 1; return 42; }\n')
    prototypes = 'char *text(void); int inspect(char *);\n'
    relay = 'int relay(void) { char *p="hi"; if(inspect(p)!=42) return 2; return inspect(text()); }\n'
    driver = ('int relay(void); int main(void) { char *p=text(); '
              'if(p[0]!=104 || p[1]!=105 || p[2]!=0 || p[3]!=120 || p[4]!=0) return 3; '
              'if(inspect("hi")!=42 || p!=text()) return 4; return relay(); }\n')
    for text, host_text in [(helpers + relay, prototypes + driver),
                            (prototypes + relay, helpers + driver)]:
        compile_source(text)
        if qbe:
            link_and_run(host_text)

    # Two separately compiled kcc units both start at private string ID zero.
    # Their symbols must not collide with each other or user C function names.
    if qbe:
        assemblies = []
        for i, value in enumerate(['a', 'b']):
            compile_source(f'char *text_{i}(void) {{ return "{value}"; }}')
            saved = directory / f'unit{i}.s'
            saved.write_text(assembly.read_text())
            assemblies.append(str(saved))
        other.write_text('char *text_0(void); char *text_1(void); int main(void) { '
                         'if(text_0()[0]!=97 || text_1()[0]!=98) return 1; return 42; }')
        subprocess.run([host, *assemblies, str(other), '-o', str(executable)], check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42

    result = compile_source('int f(void) { &"abc"+1; return 42; }')
    assert 'data $.Lkcc.string.0 = align 1' in result and ', 4\n' in result, result
    assert 'load' not in result and '\tb 0\n' in result, result

    for count, valid in [(126, True), (127, False)]:
        source.write_text('int f(void) { return ' + '! ' * count + '"x"; }')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'depth' in result.stderr, result.stderr

    # Compile-only resource fixtures. Generated bytes are deterministic tests,
    # not arbitrary fuzz programs, and no giant data object is executed.
    for length, valid in [(1048576, True), (1048577, False)]:
        source.write_text('char *f(void) { return "' + 'a' * length + '"; }')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=15)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr[:500]
        if not valid:
            assert 'storage/count limit' in result.stderr, result.stderr[:500]
    for count, valid in [(4096, True), (4097, False)]:
        # Block-item limits are per function; split literals between functions
        # so this fixture specifically reaches the TU literal count limit.
        bodies = ['"";' * min(2048, max(0, count - i * 2048)) for i in range(3)]
        source.write_text(''.join(f'int f{i}(void) {{ {body} return 0; }}' for i, body in enumerate(bodies)))
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr[:500]
        if not valid:
            assert 'storage/count limit' in result.stderr, result.stderr[:500]
    # Eight literals each occupy 1 MiB including their final NUL; a ninth byte
    # exceeds total storage, independently of per-literal/count limits.
    body = ''.join('"' + 'a' * 1048575 + '";' for _ in range(8))
    for extra, valid in [('', True), ('"";', False)]:
        source.write_text('int f(void) { ' + body + extra + ' return 0; }')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=30)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr[:500]
        if not valid:
            assert 'storage/count limit' in result.stderr, result.stderr[:500]

    rejected = [
        ('int main(void) { char *p=L"x"; return 0; }', 'prefixed string'),
        ('int main(void) { char *p=u8"x"; return 0; }', 'prefixed string'),
        ('int main(void) { char *p="\\q"; return 0; }', 'unsupported character escape'),
        ('int main(void) { char *p="\\x100"; return 0; }', 'exceeds one byte'),
        ('int main(void) { char *p="\\400"; return 0; }', 'exceeds one byte'),
        ('int main(void) { char *p="a" "b"; return 0; }', "expected ';'"),
        ('int main(void) { char a[2]="x"; return 0; }', 'array initializers'),
        ('int main(void) { return "x"; }', 'pointer conversion'),
        ('int main(void) { "x"="y"; return 0; }', 'modifiable lvalue'),
    ]
    for text, message in rejected:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)
print(f'String literals passed ({len(programs)} full-value programs, 512 byte escape checks, both-direction static-object ABI, '
      f'private multi-object symbols, macro/escape/storage/depth checks; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

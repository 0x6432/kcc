"""Adjacent ordinary strings concatenate decoded bytes, with one final NUL."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root / 'build' / 'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
programs = [
    'int main(void) { char *p="a" "b"; if(p[0]!=97 || p[1]!=98 || p[2]!=0 || (p+3)-p!=3) return 1; return 42; }',
    'int main(void) { char *p="" "" ""; if(p[0]!=0 || (p+1)-p!=1) return 1; return 42; }',
    'int main(void) { char *p="a\\0" "b"; if(p[0]!=97 || p[1]!=0 || p[2]!=98 || p[3]!=0) return 1; return 42; }',
    'int main(void) { char *p="\\x12" "3"; if(p[0]!=18 || p[1]!=51 || p[2]!=0) return 1; return 42; }',
    'int main(void) { char *p="\\1" "23"; if(p[0]!=1 || p[1]!=50 || p[2]!=51 || p[3]!=0) return 1; return 42; }',
    'int main(void) { char *p="\\12" "3"; if(p[0]!=10 || p[1]!=51 || p[2]!=0) return 1; return 42; }',
    'int main(void) { char *p="\\123" "4"; if(p[0]!=83 || p[1]!=52 || p[2]!=0) return 1; return 42; }',
    'int main(void) { char *p="a"/**/"b" // comment\n "c"; if(p[2]!=99 || p[3]!=0) return 1; return 42; }',
    '#define WORD "b"\nint main(void) { char *p="a" WORD "c"; if(p[0]!=97 || p[1]!=98 || p[2]!=99 || p[3]!=0) return 1; return 42; }',
    '#define S(x) #x\nint main(void) { char *p=S() S(a) S(b) S(); if(p[0]!=97 || p[1]!=98 || p[2]!=0) return 1; return 42; }',
    'int main(void) { char *p="a"\n#if 1\n"b"\n#endif\n; if(p[1]!=98 || p[2]!=0) return 1; return 42; }',
    'int main(void) { char *p="a"\\\n"b"; if(p[1]!=98 || p[2]!=0) return 1; return 42; }',
    'int main(void) { return "a" "b"[1]-56; }',
    'char *text(void) { return "h" "i"; } int main(void) { char *p=text(); if(p!=text() || p[1]!=105 || p[2]!=0) return 1; return 42; }',
]

with tempfile.TemporaryDirectory(prefix='kcc string concatenation ') as directory:
    directory = Path(directory)
    source, other, il, assembly, obj, executable = [directory / name for name in
                                                   ('k.c', 'h.c', 'p.ssa', 'p.s', 'h.o', 'p')]
    # Included literal tokens must retain child source spelling after include EOF.
    (directory / 'part.h').write_text('"b"\n')
    programs.append('int main(void) { char *p="a"\n#include "part.h"\n; if(p[0]!=97 || p[1]!=98 || p[2]!=0) return 1; return 42; }')

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
        result = compile_source(text)
        # Every curated full program has exactly one resulting literal object,
        # except text()'s string, which is likewise registered only once.
        assert result.count('data $.Lkcc.string.') == 1, result
        if qbe:
            link_and_run()
        result = subprocess.run([host, '-std=c2x', '-fsigned-char', str(source), '-o', str(executable)],
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, (text, result.stderr)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, text

    helpers = ('char *text(void) { return "h" "i\\0" "x"; } '
               'int inspect(char *s) { if(s[0]!=104 || s[1]!=105 || s[2]!=0) return 1; return 42; }\n')
    prototypes = 'char *text(void); int inspect(char *);\n'
    relay = 'int relay(void) { if(inspect("h" "i")!=42) return 2; return inspect(text()); }\n'
    driver = ('int relay(void); int main(void) { char *p=text(); '
              'if(p[0]!=104 || p[1]!=105 || p[2]!=0 || p[3]!=120 || p[4]!=0) return 3; '
              'if(inspect("h" "i")!=42 || p!=text()) return 4; return relay(); }\n')
    for text, host_text in [(helpers + relay, prototypes + driver),
                            (prototypes + relay, helpers + driver)]:
        compile_source(text)
        if qbe:
            link_and_run(host_text)

    # Compile-only exact limits; no enormous object is executed.
    boundaries = [
        ('int f(void) { ' + '"" ' * 4096 + '; return 0; }', True, ''),
        ('int f(void) { ' + '"" ' * 4097 + '; return 0; }', False, 'fragment limit'),
        ('int f(void) { ' + ('"" ' * 4096 + ';') * 4 + ' return 0; }', True, ''),
        ('int f(void) { ' + ('"" ' * 4096 + ';') * 4 + ' ""; return 0; }', False, 'fragment limit'),
    ]
    half = 'a' * 524288
    boundaries += [
        ('char *f(void) { return "' + half + '" "' + half + '"; }', True, ''),
        ('char *f(void) { return "' + half + '" "' + half + 'a"; }', False, 'storage/count limit'),
    ]
    for text, valid, message in boundaries:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=20)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr[:500]
        if not valid:
            assert message in result.stderr, result.stderr[:500]
    # Final NUL contributes once per sequence, not once per fragment.
    sequence = '"' + half + '" "' + half[:-1] + '";'
    for extra, valid in [('', True), ('"";', False)]:
        source.write_text('int f(void) { ' + sequence * 8 + extra + ' return 0; }')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=30)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr[:500]
        if not valid:
            assert 'storage/count limit' in result.stderr, result.stderr[:500]

    for text in ['int main(void) { char *p="a" L"b"; return 0; }',
                 'int main(void) { char *p="a" u8"b"; return 0; }']:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and 'prefixed string' in result.stderr, result.stderr
print(f'String concatenation passed ({len(programs)} full-value programs, escape/NUL boundaries, macro/include lifetimes, '
      f'one combined static object, both-direction ABI and exact fragment/storage constraints; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

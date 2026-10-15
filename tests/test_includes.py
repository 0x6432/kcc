"""Hermetic quoted-header resolution, source ownership and macro EOF boundaries."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root/'build'/'kcc'
oracle = root/'build'/'pp_oracle'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
with tempfile.TemporaryDirectory(prefix='kcc includes ') as directory:
    directory = Path(directory)
    (directory/'sub').mkdir()
    source = directory/'root.c'
    header = directory/'sub'/'defs.h'
    common = directory/'common.h'
    reference = directory/'reference.c'
    common_text = '#define VALUE 40\n#define ADD(x) ((x)+2)\n'
    header_text = ('#ifndef DEFS_H\n#define DEFS_H\n#include "../common.h"\n'
                   'int helper(int);\nint helper(int x) { return ADD(x); }\n#endif\n')
    program = '#include "sub/defs.h"\n#include "sub/defs.h"\nint main(void) { return helper(VALUE); }\n'
    programs = 0
    for root_ending in ('\n', '\r\n', '\r'):
        for header_ending in ('\n', '\r\n', '\r'):
            source.write_bytes(program.replace('\n', root_ending).encode())
            header.write_bytes(header_text.replace('\n', header_ending).encode())
            common.write_bytes(common_text.replace('\n', header_ending).encode())
            actual = subprocess.run([str(oracle), '--pp', str(source)], capture_output=True, text=True, timeout=5)
            assert actual.returncode == 0 and not actual.stderr, actual.stderr
            expanded = subprocess.run([host, '-std=c2x', '-E', '-P', str(source)], capture_output=True, text=True, timeout=10)
            assert expanded.returncode == 0, expanded.stderr
            reference.write_text(expanded.stdout)
            expected = subprocess.run([str(oracle), '--pp', str(reference)], capture_output=True, text=True, timeout=5)
            assert expected.returncode == 0 and actual.stdout == expected.stdout
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
            programs += 1
    # Absolute quoted paths and files whose last directive has no final newline.
    common.write_text('#define ANSWER 42')
    source.write_text(f'#include "{common}"\nint main(void) {{ return ANSWER; }}\n')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0 and not result.stderr, result.stderr
    source.write_text('#if 0\n#include "missing.h"\n#endif\nint main(void) { return 42; }\n')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0 and not result.stderr
    # F cannot acquire '(' from the parent, nor can incomplete F( acquire ')'.
    common.write_text('#define F() 42\nF')
    source.write_text('#include "common.h"\n()\n')
    actual = subprocess.run([str(oracle), '--pp', str(source)], capture_output=True, text=True, timeout=5)
    assert actual.returncode == 0 and actual.stdout == 'identifier:F\npunctuator:(\npunctuator:)\n'
    expanded = subprocess.run([host, '-std=c2x', '-E', '-P', str(source)], capture_output=True, text=True, timeout=10)
    reference.write_text(expanded.stdout)
    expected = subprocess.run([str(oracle), '--pp', str(reference)], capture_output=True, text=True, timeout=5)
    assert expanded.returncode == 0 and expected.stdout == actual.stdout
    for header_body, root_body, message in [
        ('#define F(a) a\nF(', '#include "common.h"\n)\n', 'unterminated function-like'),
        ('#endif\n', '#if 1\n#include "common.h"\n#endif\n', 'no matching opener'),
        ('#if 1\n', '#include "common.h"\n', 'unterminated conditional group in included source'),
        ('#error header problem\n', '#include "common.h"\n', 'common.h:1:2: error: #error: header problem'),
        ('int helper(void) { return missing; }\n', '#include "common.h"\n', 'common.h:1:27: error:'),
    ]:
        common.write_text(header_body)
        source.write_text('int main(void) { return 0; }\n'+root_body)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, result.stderr
    for directive, message in [
        ('#include "missing.h"', 'cannot load quoted include'),
        ('#include ""', 'only direct nonempty'), ('#include <x.h>', 'only direct nonempty'),
        ('#define H "common.h"\n#include H', 'only direct nonempty'),
        ('#include "common.h" extra', 'expected end of line'),
        (r'#include "a\b.h"', 'backslashes'), ('#include u8"common.h"', 'only direct nonempty'),
    ]:
        source.write_text(directive+'\nint main(void) { return 0; }\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, result.stderr
    # Child physical mappings remain available to sema after returning to root.
    common.write_bytes(b'int helper(void) { ret\\\r\nurn missing; }\r\n')
    source.write_text('#include "common.h"\nint main(void) { return helper(); }\n')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 1 and not result.stdout and 'common.h:2:5: error:' in result.stderr, result.stderr
print(f'Quoted includes passed ({programs+1} host pp agreements; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

"""Conditional selection oracle, structural diagnostics and executable checks."""
import os
import random
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root / 'build' / 'kcc'
oracle = root / 'build' / 'pp_oracle'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
random_source = random.Random(0x42)
examples = [
    ('#ifdef X\n12u "unused"\n#else\n42\n#endif\n', [42]),
    ('#define X Y\n#ifdef Y\n1\n#else\n42\n#endif\n', [42]),
    ('#define X\n#ifdef X\n42\n#elif garbage(\n1\n#endif\n', [42]),
    ('#ifdef X\n#if unknown(\n1\n#else\n2\n#endif\n#else\n42\n#endif\n', [42]),
    ('#ifdef X\n#unknown unused\n#include "absent.h"\n#error no\n#warning no\n'
     '#define X 7\n#endif\n#ifndef X\n42\n#endif\n', [42]),
    ('#define X\n#undef X\n#ifdef X\n1\n#else\n42\n#endif\n', [42]),
    ('%:ifndef X\n42\n%:else\n1\n%:endif\n', [42]),
]

for _ in range(100):
    defined = {f'M{i}' for i in range(4) if random_source.randrange(2)}
    prefix = ''.join(f'#define {name} 0\n' for name in sorted(defined))

    def tree(depth):
        if not depth or random_source.randrange(3) == 0:
            number = random_source.randrange(100)
            return f'{number}\n', [number]
        name = f'M{random_source.randrange(4)}'
        negate = bool(random_source.randrange(2))
        yes, yes_values = tree(depth-1)
        no, no_values = tree(depth-1)
        selected = (name in defined) != negate
        directive = 'ifndef' if negate else 'ifdef'
        return (f'#{directive} {name}\n{yes}#else\n{no}#endif\n',
                yes_values if selected else no_values)

    body, expected = tree(5)
    examples.append((prefix+body, expected))

with tempfile.TemporaryDirectory(prefix='kcc-conditions-') as directory:
    directory = Path(directory)
    source = directory / 'input.c'
    reference = directory / 'reference.c'

    def dump(path):
        result = subprocess.run([str(oracle), '--pp', str(path)],
                                capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, (path.read_text(), result.stderr)
        return result.stdout

    for text, expected in examples:
        for ending in ('\n', '\r\n', '\r'):
            source.write_bytes(text.replace('\n', ending).encode())
            actual = dump(source)
            assert actual == ''.join(f'pp-number:{number}\n' for number in expected), (text, actual)
            result = subprocess.run([host, '-std=c2x', '-E', '-P', str(source)],
                                    capture_output=True, text=True, timeout=10)
            assert result.returncode == 0, result.stderr
            reference.write_text(result.stdout)
            assert dump(reference) == actual, (text, result.stdout, actual)

    c23_cases = []
    for a in (False, True):
        for b in (False, True):
            definitions = ('#define A\n' if a else '') + ('#define B\n' if b else '')
            text = (definitions + '#ifdef A\n1\n#elifdef B\n2\n'
                    '#elifndef A\n3\n#else\n4\n#endif\n')
            expected = 1 if a else 2 if b else 3
            c23_cases.append((text, expected))
    legacy_c23 = 0
    for text, expected in c23_cases:
        source.write_text(text)
        assert dump(source) == f'pp-number:{expected}\n'
        result = subprocess.run([host, '-std=c2x', '-E', '-P', str(source)],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip() == str(expected):
            continue
        # GCC 11 ignores these newer controls in excluded groups. Not agreement.
        version = subprocess.run([host, '-dumpfullversion'], capture_output=True,
                                 text=True, timeout=5).stdout.strip()
        assert version.startswith('11.'), result.stderr
        if expected == 1:
            assert result.returncode != 0 and result.stdout.split() == ['1', '2', '3']
            assert 'invalid preprocessing directive #elifdef' in result.stderr
            assert 'invalid preprocessing directive #elifndef' in result.stderr
        else:
            assert result.returncode == 0 and result.stdout.strip() == '4'
            assert expected in (2, 3), (text, result.stdout)
        legacy_c23 += 1

    programs = [
        '#define X\n#ifdef X\nreturn 42;\n#else\n#error hidden\n#endif\n',
        '#ifdef X\n12u invalid;\n#else\nreturn 42;\n#endif\n',
        '#ifndef X\n#define X 42\n#endif\nreturn X;\n',
        '#define X\n#undef X\n#ifdef X\n#error stale\n#else\nreturn 42;\n#endif\n',
    ]
    for body in programs:
        for ending in ('\n', '\r\n', '\r'):
            text = 'int main(void) {\n' + body + '}\n'
            source.write_bytes(text.replace('\n', ending).encode())
            result = subprocess.run([str(compiler), str(source)],
                                    capture_output=True, text=True, timeout=5)
            assert result.returncode == 0 and not result.stderr, result.stderr
            if qbe:
                il, assembly, executable = [directory / name for name in ('p.ssa', 'p.s', 'p')]
                il.write_text(result.stdout)
                subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)],
                               check=True, timeout=10)
                subprocess.run([host, str(assembly), '-o', str(executable)], check=True, timeout=10)
                assert subprocess.run([str(executable)], timeout=5).returncode == 42
                subprocess.run([host, '-std=c2x', str(source), '-o', str(executable)],
                               check=True, timeout=10)
                assert subprocess.run([str(executable)], timeout=5).returncode == 42
    for text, message in [
        ('#ifdef X\n"unterminated\n#endif\n', 'unterminated'),
        ('#ifdef X\n', 'unterminated conditional group'),
        ('#ifdef X\n#else extra\n#endif\n', 'expected end of line'),
        ('#ifndef X\n#else\n#elifndef X\n#endif\n', 'follows #else'),
    ]:
        source.write_text('int main(void) { return 0; }\n'+text)
        result = subprocess.run([str(compiler), str(source)],
                                capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, result.stderr
print(f'Conditional tests passed ({len(examples)*3} host agreements; '
      f'{len(c23_cases)} C23 cases, {legacy_c23} legacy-host nonagreements; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

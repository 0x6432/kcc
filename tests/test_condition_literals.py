"""Signed preprocessing integer spelling and C23 separator cases."""
import os
import random
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root/'build'/'kcc'
oracle = root/'build'/'pp_oracle'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
rng = random.Random(0x64)
literals = ['42', '052', '0x2a', '0X2A', '0b101010', '0B101010']
examples = [(literal+suffix+' == 42', True) for literal in literals for suffix in ('', 'l', 'L', 'll', 'LL')]
examples += [
    ('0x7fffffffffffffffLL == 9223372036854775807', True),
    ('0777777777777777777777 == 9223372036854775807', True),
    ('0b'+'1'*63+' == 9223372036854775807', True),
    ('0L == 0 && 0x0LL == 0 && 0b0ll == 0', True),
]
for _ in range(60):
    value = rng.randrange(1000000)
    base = rng.randrange(4)
    literal = [str(value), '0'+format(value, 'o'), '0x'+format(value, 'x'), '0b'+format(value, 'b')][base]
    suffix = rng.choice(['', 'l', 'L', 'll', 'LL'])
    selected = bool(rng.randrange(2))
    examples.append((literal+suffix+' == '+str(value if selected else value+1), selected))
separators = [
    "1'000 == 1000", "0x7fff'ffff'ffff'ffff == 9223372036854775807",
    "0b1010'1010 == 170", "0'7'7 == 63", "42'000L == 42000",
    "0X2'A == 42", "1'2'3LL == 123",
]

with tempfile.TemporaryDirectory(prefix='kcc-pp-int-') as directory:
    directory = Path(directory)
    source = directory/'input.c'
    for text, selected in examples:
        expected = '42' if selected else '0'
        source.write_text(f'#if {text}\n42\n#else\n0\n#endif\n')
        result = subprocess.run([str(oracle), '--pp', str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        assert result.stdout == f'pp-number:{expected}\n', (text, result.stdout)
        reference = subprocess.run([host, '-std=c2x', '-E', '-P', str(source)], capture_output=True, text=True, timeout=10)
        assert reference.returncode == 0 and reference.stdout.split() == [expected], (text, reference.stderr)
    legacy = 0
    for text in separators:
        source.write_text(f'#if {text}\n42\n#else\n0\n#endif\n')
        result = subprocess.run([str(oracle), '--pp', str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr and result.stdout == 'pp-number:42\n', result.stderr
        reference = subprocess.run([host, '-std=c2x', '-E', '-P', str(source)], capture_output=True, text=True, timeout=10)
        if reference.returncode == 0 and reference.stdout.split() == ['42']:
            continue
        version = subprocess.run([host, '-dumpfullversion'], capture_output=True, text=True, timeout=5).stdout.strip()
        assert version.startswith('11.') and reference.returncode != 0, reference.stderr
        assert reference.stdout.split() == ['0'], reference.stdout
        assert any(message in reference.stderr for message in (
            'missing terminating', 'not valid', 'missing binary operator')), reference.stderr
        legacy += 1
    for literal, message in [
        ('0x', 'expected digits'), ('0b', 'expected digits'), ('08', 'invalid digit'),
        ('0b2', 'invalid digit'), ('0x1g', 'unsupported conditional integer suffix'),
        ('42lL', 'unsupported conditional integer suffix'), ('42Ll', 'unsupported conditional integer suffix'),
        ('42LLL', 'unsupported conditional integer suffix'), ('1wb', 'unsupported conditional integer suffix'),
        ('18446744073709551616', 'exceeds 64-bit'), ('0x1ffffffffffffffff', 'exceeds 64-bit'),
        ("0x'1", 'invalid separator'), ("0b1'2", 'invalid separator'),
        ('9223372036854775808', 'exceeds signed 64-bit'),
    ]:
        source.write_text(f'#if {literal}\n#endif\nint main(void) {{ return 0; }}\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (literal, result.stderr)
    # Common spellings work in executable selection with each newline policy.
    for literal in literals:
        for ending in ('\n', '\r\n', '\r'):
            text = f'#if {literal}LL == 42\nint main(void) {{ return 42; }}\n#else\n#error bad\n#endif\n'
            source.write_bytes(text.replace('\n', ending).encode())
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
print(f'Conditional literals passed ({len(examples)} host/model agreements; '
      f'{len(separators)} C23 cases, {legacy} legacy-host nonagreements; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

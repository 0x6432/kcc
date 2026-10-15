"""Runtime integer spellings share a decoder, not preprocessing's value types."""
import os
import random
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler, oracle = root/'build'/'kcc', root/'build'/'pp_oracle'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
rng = random.Random(1202)
cases = [('0', 0), ('00', 0), ('052', 42), ('0x2a', 42), ('0X2A', 42),
         ('0b101010', 42), ('0B101010', 42), ('0x7fffffff', 2147483647),
         ('017777777777', 2147483647), ('0b'+'1'*31, 2147483647)]
for _ in range(10):
    value = rng.randrange(2147483648)
    cases += [(str(value), value), ('0'+format(value, 'o'), value),
              ('0x'+format(value, 'x'), value), ('0b'+format(value, 'b'), value)]
separators = [("1'000", 1000), ("0x7fff'ffff", 2147483647), ("0b1010'1010", 170),
              ("0'7'7", 63), ("0X2'A", 42), ("1'2'3", 123)]
legacy = 0
agreements = 0
with tempfile.TemporaryDirectory(prefix='kcc integer spelling ') as directory:
    directory = Path(directory)
    source, reference, il, assembly, executable = [directory/name for name in ('p.c', 'r.c', 'p.ssa', 'p.s', 'p')]
    for spelling, value in cases+separators:
        text = f'int main(void) {{ int x={spelling}; if(x=={value}) return 42; return 1; }}\n'
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, (spelling, result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
            subprocess.run([host, str(assembly), '-o', str(executable)], check=True, timeout=10)
            assert subprocess.run([str(executable)], timeout=5).returncode == 42, spelling
        expected = subprocess.run([host, '-std=c2x', str(source), '-o', str(executable)],
                                  capture_output=True, text=True, timeout=10)
        if expected.returncode:
            version = subprocess.run([host, '-dumpfullversion'], capture_output=True, text=True, timeout=5).stdout.strip()
            assert (spelling, value) in separators and version.startswith('11.'), expected.stderr
            assert any(message in expected.stderr for message in ('missing terminating', 'expected', 'character constant'))
            legacy += 1
            reference.write_text(text.replace(spelling, str(value), 1))
            subprocess.run([host, '-std=c2x', str(reference), '-o', str(executable)], check=True, timeout=10)
        else:
            agreements += 1
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, spelling
    # Macro-pasted and phase-normalized spellings retain original pp spelling.
    for ending in ('\n', '\r\n', '\r'):
        text = '#define C(a,b) a##b\nint main(void) { return C(0x,2a); }\n'
        source.write_bytes(text.replace('\n', ending).encode())
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr and 'copy 42' in result.stdout
        expanded = subprocess.run([str(oracle), '--pp', str(source)], capture_output=True, text=True, timeout=5)
        assert expanded.returncode == 0 and 'pp-number:0x2a\n' in expanded.stdout
    for spelling, message in [('08', 'invalid digit'), ('0x', 'expected digits'), ('0b2', 'invalid digit'),
                              ("0x'1", 'invalid separator'), ('0xg', 'expected digits'),
                              ('42LL', 'unsupported numeric'),
                              ('42uLL', 'unsupported numeric'), ('42lL', 'unsupported numeric'),
                              ('2147483648', 'supported int type'), ('-2147483648', 'supported int type'),
                              ('0x10000000000000000', 'exceeds 64-bit'),
                              ('18446744073709551616', 'exceeds 64-bit')]:
        source.write_text(f'int main(void) {{ return {spelling}; }}\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (spelling, result.stderr)
print(f'Integer spellings passed ({agreements} host programs, {legacy} known legacy separator gaps; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

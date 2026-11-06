"""Wide ordinary enum behavior: target-specific 64-bit bounded slice."""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
kcc = root / 'build/kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
program = '''enum Wide {
    U=2147483648U, U_SIZE=sizeof(U),
    MAX=2147483647, NEXT, NEG=-2147483649LL
};
_Static_assert(U_SIZE==4 && sizeof(U)==8 && NEXT==2147483648LL, "types");
_Static_assert(NEG==-2147483649LL, "sign extension");
enum Full { ZERO=0, TOP=18446744073709551615ULL };
_Static_assert(sizeof(TOP)==8 && TOP==18446744073709551615ULL, "unsigned max");
enum Wide x=NEXT;
int main(void) { return x==2147483648LL && U==NEXT && NEG<0 ? 42 : 1; }
'''
invalid = [
    'enum E { A=18446744073709551615ULL, B };',
    'enum E { A=-1, B=18446744073709551615ULL };',
    'enum E { A=18446744073709551615ULL, B=-1 };',
    'enum E { A=9223372036854775807LL, B };',
]
with tempfile.TemporaryDirectory(prefix='kcc-wide-enum-') as directory:
    directory = Path(directory)
    source, il, asm, exe = [directory / name for name in ('test.c', 'test.ssa', 'test.s', 'test')]
    for text in invalid:
        source.write_text(text + '\n')
        result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 1 and not result.stdout and 'range' in result.stderr, (text, result.stderr)
    source.write_text(program)
    result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    if qbe:
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True, timeout=10)
        subprocess.run([host, str(asm), '-o', str(exe)], check=True, timeout=10)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
print('bounded wide ordinary enum checks complete')

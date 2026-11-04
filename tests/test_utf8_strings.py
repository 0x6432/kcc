"""C23 u8 strings: byte representation, type, concatenation and rejection."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')
with tempfile.TemporaryDirectory(prefix='kcc-u8-') as directory:
    path = Path(directory)
    source = path / 'test.c'
    source.write_text('''
unsigned char bytes[]=u8"é" "!";
static_assert(_Generic(u8"x", unsigned char *: 1, default: 0));
static_assert(_Generic(u8'A', unsigned char: 1, default: 0));
static_assert(sizeof(u8'A')==1 && u8'\\377'==255);
#if u8'\\377' != 255
#error UTF-8 character value is not unsigned
#endif
int main(void) {
    unsigned char *p="a" u8"é";
    if (sizeof bytes!=4 || bytes[0]!=195 || bytes[1]!=169 || bytes[2]!=33 || bytes[3]!=0) return 1;
    if (p[0]!=97 || p[1]!=195 || p[2]!=169 || p[3]!=0) return 2;
    if (u8"\\377"[0]!=255 || u8'\\377'!=255) return 3;
    return 42;
}
''', encoding='utf-8')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    if qbe:
        il, asm, exe = (path / n for n in ('test.ssa', 'test.s', 'test'))
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), '-o', str(exe)], check=True)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
    for invalid in [b'u8"\xc0\x80"', b'u8"\xed\xa0\x80"', b'u8"\xf4\x90\x80\x80"', b'u8"\xe2\x82"']:
        source.write_bytes(b'int main(void) { ' + invalid + b'; return 0; }\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode != 0 and result.stderr, invalid
print('UTF-8 string literal checks completed')

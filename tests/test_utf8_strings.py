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
#include <uchar.h>
unsigned char bytes[]=u8"é" "!";
char raw[]="é";
static_assert(sizeof(char8_t)==1 && sizeof(char16_t)==2 && sizeof(char32_t)==4 && sizeof(mbstate_t)==8);
static_assert(_Generic(u8"x", char8_t *: 1, default: 0));
unsigned char escapes[]=u8"\\u00E9\\U0001F642";
char ordinary[]="\\u00E9";
static_assert(_Generic(u8"x", unsigned char *: 1, default: 0));
static_assert(_Generic(u8'A', unsigned char: 1, default: 0));
static_assert(_Generic(u'A', unsigned short: 1, default: 0));
static_assert(_Generic(U'A', unsigned int: 1, default: 0));
static_assert(_Generic(L'A', int: 1, default: 0));
static_assert(sizeof(u'A')==2 && sizeof(U'A')==4 && sizeof(L'A')==4);
static_assert(u'é'==0xe9 && U'🙂'==0x1f642 && L'é'==0xe9);
static_assert(u'\\u00E9'==0xe9 && U'\\U0001F642'==0x1f642 && L'\\u00E9'==0xe9);
#if u'\\u00E9' != 0xe9 || U'🙂' != 0x1f642
#error Unicode character value is incorrect
#endif
static_assert(u'\\377'==255 && U'\\377'==255 && L'\\377'==255);
#if u'\\377' != 255 || U'A' != 65 || L'A' != 65
#error prefixed character value is incorrect
#endif
static_assert(sizeof(u8'A')==1 && u8'\\377'==255);
#if u8'\\377' != 255
#error UTF-8 character value is not unsigned
#endif
int main(void) {
    unsigned char *p="a" u8"é";
    if (sizeof bytes!=4 || bytes[0]!=195 || bytes[1]!=169 || bytes[2]!=33 || bytes[3]!=0) return 1;
    if (p[0]!=97 || p[1]!=195 || p[2]!=169 || p[3]!=0) return 2;
    if (u8"\\377"[0]!=255 || u8'\\377'!=255) return 3;
    if (sizeof escapes!=7 || escapes[0]!=195 || escapes[1]!=169 || escapes[2]!=240 || escapes[3]!=159 || escapes[4]!=153 || escapes[5]!=130 || escapes[6]!=0) return 4;
    if (sizeof ordinary!=3 || (unsigned char)ordinary[0]!=195 || (unsigned char)ordinary[1]!=169) return 5;
    if (sizeof raw!=3 || (unsigned char)raw[0]!=195 || (unsigned char)raw[1]!=169) return 6;
    { mbstate_t state={0}; char32_t c=0; char out[4];
      if (mbrtoc32(&c,"A",1,&state)!=1 || c!=65 || c32rtomb(out,c,&state)!=1 || out[0]!=65) return 7; }
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
    for invalid in [b"u'\\U0001F642'", b"u'\\uD800'", b"U'\\U00110000'", b"U'\\u0041'", b'u8"\xc0\x80"', b'u8"\xed\xa0\x80"', b'u8"\xf4\x90\x80\x80"', b'u8"\xe2\x82"',
                    b'u8"\\uD800"', b'u8"\\U00110000"', b'u8"\\u01"']:
        source.write_bytes(b'int main(void) { ' + invalid + b'; return 0; }\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode != 0 and result.stderr, invalid
print('UTF-8 string literal checks completed')

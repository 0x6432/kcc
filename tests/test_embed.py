"""Bounded C23 embed: raw bytes, limits, searches, and rejections."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')

with tempfile.TemporaryDirectory(prefix='kcc-embed-') as directory:
    path = Path(directory)
    (path / 'asset.bin').write_bytes(bytes([0, 10, 42, 255]))
    (path / 'empty.bin').write_bytes(b'')
    (path / 'special@asset.bin').write_bytes(bytes([42]))
    (path / 'oversized.bin').write_bytes(bytes(4097))
    source = path / 'main.c'
    source.write_text('''
#define RESOURCE "asset.bin"
#if !defined(__has_embed) || !defined(__STDC_EMBED_FOUND__)
#error embed query macros unavailable
#endif
#if __has_embed(RESOURCE) != __STDC_EMBED_FOUND__
#error present binary resource not found
#endif
#if __has_embed("empty.bin") != __STDC_EMBED_EMPTY__
#error empty resource not identified
#endif
#if __has_embed("missing.bin") != __STDC_EMBED_NOT_FOUND__ || __has_embed("oversized.bin") != __STDC_EMBED_NOT_FOUND__
#error unavailable resource was reported usable
#endif
#if __has_embed("asset.bin" __limit__(0)) != __STDC_EMBED_EMPTY__ || __has_embed("oversized.bin" limit(2wb+1uwb)) != __STDC_EMBED_FOUND__
#error limited resource query failed
#endif
#if __has_embed("asset.bin" prefix(7,) suffix(,8)) != __STDC_EMBED_FOUND__ || __has_embed("empty.bin" if_empty(9)) != __STDC_EMBED_EMPTY__
#error standard embed parameters not recognized
#endif
static_assert(__STDC_EMBED_NOT_FOUND__==0 && __STDC_EMBED_FOUND__==1 && __STDC_EMBED_EMPTY__==2);
unsigned char a[] = {
#embed RESOURCE
};
unsigned char b[] = { 42
#embed "empty.bin"
};
#define LIMIT_COUNT (1wb+2uwb)
unsigned char c[] = {
#embed RESOURCE limit(LIMIT_COUNT)
};
unsigned char d[] = {
#embed "oversized.bin" limit(2)
};
#define HEAD 7,
#define TAIL ,8
unsigned char e[] = {
#embed RESOURCE __suffix__(TAIL) __prefix__(HEAD) limit(2) if_empty(99)
};
unsigned char f[] = {
#embed RESOURCE prefix(1,) if_empty(9,10) suffix(,2) limit(0)
};
unsigned char g[] = {
#embed "empty.bin" if_empty((3+4))
};
int main(void) { return sizeof a==4 && a[0]==0 && a[1]==10 && a[2]==42 && a[3]==255 && sizeof b==1 && sizeof c==3 && c[2]==42 && sizeof d==2 && sizeof e==4 && e[0]==7 && e[1]==0 && e[2]==10 && e[3]==8 && sizeof f==2 && f[0]==9 && f[1]==10 && sizeof g==1 && g[0]==7 ? b[0] : 1; }
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    if qbe:
        il, asm, exe = (path / n for n in ('out.ssa', 'out.s', 'out'))
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), '-o', str(exe)], check=True)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
    for operand in ['"missing.bin"', '"oversized.bin"', '"asset.bin" limit(-1)', '"asset.bin" limit(1) limit(2)', '"asset.bin" prefix(1) __prefix__(2)']:
        source.write_text('unsigned char a[] = {\n#embed ' + operand + '\n};\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode != 0 and result.stderr, operand
    source.write_text('#if __has_embed("asset.bin" vendor::unsupported((1,[2]))) != __STDC_EMBED_NOT_FOUND__\n#error unsupported parameter was advertised\n#endif\nint main(void) { return 0; }\n')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    source.write_text('#if __has_embed("asset.bin" prefix([1)))\n#endif\n')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode != 0 and result.stderr, 'malformed embed query must fail'
    source.write_text('#if __has_embed(<special@asset.bin>) != __STDC_EMBED_FOUND__\n#error special asset unavailable\n#endif\nunsigned char a[] = {\n#embed <special@asset.bin>\n};\nint main(void){return a[0];}\n')
    result = subprocess.run([str(compiler), '-I', str(path), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    source.write_text('unsigned char a[] = {\n#embed <asset.bin>\n};\nint main(void){return a[2];}\n')
    result = subprocess.run([str(compiler), '-I', str(path), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
print('bounded embed checks completed')

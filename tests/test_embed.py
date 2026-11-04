""Bounded C23 embed: raw bytes, limits, searches, and rejections."""
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
#if __has_embed("asset.bin" limit(0)) != __STDC_EMBED_EMPTY__ || __has_embed("oversized.bin" limit(2+1)) != __STDC_EMBED_FOUND__
#error limited resource query failed
#endif
static_assert(__STDC_EMBED_NOT_FOUND__==0 && __STDC_EMBED_FOUND__==1 && __STDC_EMBED_EMPTY__==2);
unsigned char a[] = {
#embed RESOURCE
};
unsigned char b[] = { 42
#embed "empty.bin"
};
#define LIMIT_COUNT (1+2)
unsigned char c[] = {
#embed RESOURCE limit(LIMIT_COUNT)
};
unsigned char d[] = {
#embed "oversized.bin" limit(2)
};
int main(void) { return sizeof a==4 && a[0]==0 && a[1]==10 && a[2]==42 && a[3]==255 && sizeof b==1 && sizeof c==3 && c[2]==42 && sizeof d==2 ? b[0] : 1; }
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    if qbe:
        il, asm, exe = (path / n for n in ('out.ssa', 'out.s', 'out'))
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), '-o', str(exe)], check=True)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
    for operand in ['"missing.bin"', '"oversized.bin"', '"asset.bin" limit(-1)', '"asset.bin" limit(1) limit(2)', '"asset.bin" prefix(1)']:
        source.write_text('unsigned char a[] = {\n#embed ' + operand + '\n};\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode != 0 and result.stderr, operand
    source.write_text('#if __has_embed("asset.bin" prefix(1))\n#endif\n')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode != 0 and result.stderr, 'unsupported embed query parameter must fail'
    source.write_text('unsigned char a[] = {\n#embed <asset.bin>\n};\nint main(void){return a[2];}\n')
    result = subprocess.run([str(compiler), '-I', str(path), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
print('bounded embed checks completed')

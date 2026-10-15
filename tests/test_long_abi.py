"""Mixed w/l SysV calls and returns in both directions, including stack args."""
import os
import re
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root/'build'/'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
mask = (1 << 64)-1
signature = 'unsigned long mix(long a,unsigned b,unsigned long c,int d,long e,unsigned f,unsigned long g,int h)'
body = '{ return ((a+b)^(c+d))+((e+f)^(g+h)); }'
vectors = [(-(1 << 40), 0xffffffff, 1 << 63, -7, 1 << 40, 0xffffffff, mask, -1),
           (0, 1, mask, 1, -42, 7, 1 << 40, -19),
           (42, 9, 17, -33, -1, 0xffffffff, mask-1, 1)]
checks = []
for a, b, c, d, e, f, g, h in vectors:
    value = ((((a+b)&mask)^((c+d)&mask))+(((e+f)&mask)^((g+h)&mask)))&mask
    checks.append(f'if(mix({a}L,{b}U,{c}UL,{d},{e}L,{f}U,{g}UL,{h})!={value}UL) return 1;')
main = ('int main(void) {'+''.join(checks)+
        'if(widen_signed(-1)!=-1L) return 2; if(widen_unsigned(0xffffffff)!=4294967295L) return 3; '
        'if(narrow_long(4294967295L)!=-1) return 4; return 42; }')
helpers = (signature+body+'\nlong widen_signed(int x) { return x; }\n'
           'long widen_unsigned(unsigned x) { return x; }\nint narrow_long(long x) { return x; }\n')
prototypes = signature+';\nlong widen_signed(int);\nlong widen_unsigned(unsigned);\nint narrow_long(long);\n'
with tempfile.TemporaryDirectory(prefix='kcc LP64 ABI ') as directory:
    directory = Path(directory)
    kcc_source, host_source, il, assembly, host_object, executable = [directory/name for name in
                                                                  ('k.c', 'h.c', 'k.ssa', 'k.s', 'h.o', 'p')]
    for long_long in (False, True):
        for kcc_text, host_text in [(prototypes+main, helpers), (helpers, prototypes+main)]:
            if long_long:
                kcc_text = re.sub(r'\blong\b', 'long long', kcc_text)
                host_text = re.sub(r'\blong\b', 'long long', host_text)
            kcc_source.write_text(kcc_text)
            host_source.write_text(host_text)
            result = subprocess.run([str(compiler), str(kcc_source)], capture_output=True, text=True, timeout=5)
            assert result.returncode == 0 and not result.stderr, result.stderr
            if qbe:
                il.write_text(result.stdout)
                subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
                subprocess.run([host, '-std=c2x', '-c', str(host_source), '-o', str(host_object)], check=True, timeout=10)
                subprocess.run([host, str(assembly), str(host_object), '-o', str(executable)], check=True, timeout=10)
                assert subprocess.run([str(executable)], timeout=5).returncode == 42
print(f'Long/long-long ABI {"runtime passed both directions" if qbe else "IL checks passed; runtime requires QBE"}; {host}')

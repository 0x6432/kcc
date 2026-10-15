"""Both directions of int/uint SysV calls, high bits and stack arguments."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root/'build'/'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
signature = 'unsigned mix(unsigned a,int b,unsigned c,int d,unsigned e,int f,unsigned g,int h)'
body = '{ return ((a+b)^(c+d))+((e+f)^(g+h)); }'
vectors = [(0xffffffff, -1, 0x80000000, -7, 17, -33, 0x12345678, -1),
           (0, 0, 1, -1, 0xffffffff, 1, 0x80000000, -2147483647),
           (42, 3, 7, 9, 0xfffffffe, -8, 19, 1)]
checks = []
for a, b, c, d, e, f, g, h in vectors:
    value = ((((a+b)&0xffffffff)^((c+d)&0xffffffff))+
             (((e+f)&0xffffffff)^((g+h)&0xffffffff)))&0xffffffff
    checks.append(f'if(mix({a}U,{b},{c}U,{d},{e}U,{f},{g}U,{h})!={value}U) return 1;')
main = ('int main(void) {'+''.join(checks)+
        'if(to_signed(0xffffffff)!=-1) return 2; if(to_unsigned(-1)!=0xffffffff) return 3; return 42; }')
helpers = (signature+body+'\nint to_signed(unsigned x) { return x; }\n'
           'unsigned to_unsigned(int x) { return x; }\n')
prototypes = signature+';\nint to_signed(unsigned);\nunsigned to_unsigned(int);\n'
with tempfile.TemporaryDirectory(prefix='kcc unsigned ABI ') as directory:
    directory = Path(directory)
    kcc_source, host_source, il, assembly, host_object, executable = [directory/name for name in
                                                                  ('k.c', 'h.c', 'k.ssa', 'k.s', 'h.o', 'p')]
    for kcc_text, host_text in [(prototypes+main, helpers), (helpers, prototypes+main)]:
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
print(f'Unsigned ABI {"runtime passed both directions" if qbe else "IL checks passed; runtime requires QBE"}; {host}')

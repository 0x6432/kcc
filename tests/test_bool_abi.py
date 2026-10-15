"""_Bool SysV interoperability and clean low-byte/dirty-upper-bit returns."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root/'build'/'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
helpers = '''_Bool echo(_Bool x) { return x; }
_Bool normalize(long x) { return x; }
long widen(_Bool x) { return x; }
long mixed(_Bool a,unsigned char b,_Bool c,int d,long e,_Bool f,short g,_Bool h)
{ return a+b+c+d+e+f+g+h; }
'''
prototypes = '''_Bool echo(_Bool);
_Bool normalize(long);
long widen(_Bool);
long mixed(_Bool,unsigned char,_Bool,int,long,_Bool,short,_Bool);
'''
main = '''int main(void) {
 if(echo(256)!=1 || echo(0)!=0) return 1;
 if(normalize(1099511627776L)!=1 || normalize(0)!=0) return 2;
 if(widen(256)!=1L || widen(0)!=0L) return 3;
 if(mixed(256,255,0,-7,1099511627776L,2,-32768,-1)!=1099511595259L) return 4;
 return 42;
}
'''
dirty_prototypes = '_Bool dirty_one(void); _Bool dirty_zero(void);\n'
dirty_main = '''int main(void) {
 if(dirty_one()!=1 || dirty_zero()!=0) return 1;
 if((long)dirty_one()!=1L || (long)dirty_zero()!=0L) return 2;
 if(dirty_zero() || !dirty_one()) return 3;
 _Bool b=dirty_zero(); if(b) return 4;
 if((b=dirty_one())!=1) return 5;
 if((_Bool)dirty_zero()!=0 || (_Bool)dirty_one()!=1) return 6;
 return 42;
}
'''
# Low byte is a valid bool representation, upper register bits are unspecified.
dirty_assembly = '''.text
.globl dirty_one
dirty_one:
 movl $0x12340001, %eax
 ret
.globl dirty_zero
dirty_zero:
 movl $0x12340000, %eax
 ret
.section .note.GNU-stack,"",@progbits
'''
with tempfile.TemporaryDirectory(prefix='kcc bool ABI ') as directory:
    directory = Path(directory)
    kcc_source, host_source, il, assembly, host_object, executable, dirty = [directory/name for name in
                                  ('k.c', 'h.c', 'k.ssa', 'k.s', 'h.o', 'p', 'dirty.s')]
    for kcc_text, host_text in [(prototypes+main, helpers), (helpers, prototypes+main),
                                 (dirty_prototypes+dirty_main, '')]:
        kcc_source.write_text(kcc_text)
        host_source.write_text(host_text)
        result = subprocess.run([str(compiler), str(kcc_source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, result.stderr
        assert any(fragment in result.stdout for fragment in ('=ub call', 'function ub')), result.stdout
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
            if host_text:
                subprocess.run([host, '-std=c2x', '-fsigned-char', '-c', str(host_source), '-o', str(host_object)], check=True, timeout=10)
                other = host_object
            else:
                dirty.write_text(dirty_assembly)
                other = dirty
            subprocess.run([host, str(assembly), str(other), '-o', str(executable)], check=True, timeout=10)
            assert subprocess.run([str(executable)], timeout=5).returncode == 42, kcc_text
print(f'Bool ABI {"passed both directions plus dirty upper-return bits" if qbe else "IL checks passed; runtime requires QBE"}; {host}')

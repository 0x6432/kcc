"""Host/kcc byte ABI both directions; mixed stack args and dirty return bits."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root/'build'/'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
helpers = '''signed char signed_echo(signed char x) { return x; }
unsigned char unsigned_echo(unsigned char x) { return x; }
char plain_echo(char x) { return x; }
long signed_widen(signed char x) { return x; }
long unsigned_widen(unsigned char x) { return x; }
unsigned char narrow(long x) { return x; }
long mixed(signed char a,unsigned char b,char c,int d,long e,unsigned char f,signed char g,unsigned char h)
{ return a+b+c+d+e+f+g+h; }
'''
prototypes = '''signed char signed_echo(signed char);
unsigned char unsigned_echo(unsigned char);
char plain_echo(char);
long signed_widen(signed char);
long unsigned_widen(unsigned char);
unsigned char narrow(long);
long mixed(signed char,unsigned char,char,int,long,unsigned char,signed char,unsigned char);
'''
main = '''int main(void) {
 if(signed_echo(-128)!=-128 || signed_echo(127)!=127) return 1;
 if(unsigned_echo(255)!=255 || unsigned_echo(0)!=0) return 2;
 if(plain_echo(-1)!=-1) return 3;
 if(signed_widen(-1)!=-1L || unsigned_widen(255)!=255L) return 4;
 if(narrow(1099511628031L)!=255) return 5;
 if(mixed(-128,255,-1,-7,1099511627776L,255,-128,255)!=1099511628277L) return 6;
 return 42;
}
'''
dirty_prototypes = '''signed char dirty_signed(void);
unsigned char dirty_unsigned(void);
unsigned char dirty_zero(void);
'''
dirty_main = '''int main(void) {
 if(dirty_signed()!=-1 || dirty_unsigned()!=255) return 1;
 if((long)dirty_signed()!=-1L || (long)dirty_unsigned()!=255L) return 2;
 if(dirty_zero() || !dirty_signed() || !dirty_unsigned()) return 3;
 unsigned char x=dirty_zero(); if(x) return 4;
 if((x=dirty_unsigned())!=255) return 5;
 if((signed char)dirty_signed()!=-1) return 6;
 return 42;
}
'''
# ABI permits unspecified upper bits. Handwritten functions expose the contract
# instead of accidentally relying on a host optimizer's extension choices.
dirty_assembly = '''.text
.globl dirty_signed
dirty_signed:
 movl $0x123400ff, %eax
 ret
.globl dirty_unsigned
dirty_unsigned:
 movl $0x123400ff, %eax
 ret
.globl dirty_zero
dirty_zero:
 movl $0x12340000, %eax
 ret
.section .note.GNU-stack,"",@progbits
'''
with tempfile.TemporaryDirectory(prefix='kcc byte ABI ') as directory:
    directory = Path(directory)
    kcc_source, host_source, il, assembly, host_object, executable, dirty = [directory/name for name in
                                  ('k.c', 'h.c', 'k.ssa', 'k.s', 'h.o', 'p', 'dirty.s')]
    for kcc_text, host_text in [(prototypes+main, helpers), (helpers, prototypes+main),
                                 (dirty_prototypes+dirty_main, '')]:
        kcc_source.write_text(kcc_text)
        host_source.write_text(host_text)
        result = subprocess.run([str(compiler), str(kcc_source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, result.stderr
        assert any(fragment in result.stdout for fragment in ('=sb call', 'function sb')), result.stdout
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
            result = subprocess.run([str(executable)], timeout=5)
            assert result.returncode == 42, (kcc_text, result.returncode)
print(f'Char ABI {"passed both directions plus dirty upper-return bits" if qbe else "IL checks passed; runtime requires QBE"}; {host}')

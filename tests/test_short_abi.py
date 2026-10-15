"""Host/kcc halfword ABI, mixed stack arguments and unspecified return bits."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root/'build'/'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
helpers = '''short signed_echo(short x) { return x; }
unsigned short unsigned_echo(unsigned short x) { return x; }
long signed_widen(short x) { return x; }
long unsigned_widen(unsigned short x) { return x; }
unsigned short narrow(long x) { return x; }
long mixed(short a,unsigned short b,signed char c,int d,long e,unsigned short f,short g,unsigned short h)
{ return a+b+c+d+e+f+g+h; }
'''
prototypes = '''short signed_echo(short);
unsigned short unsigned_echo(unsigned short);
long signed_widen(short);
long unsigned_widen(unsigned short);
unsigned short narrow(long);
long mixed(short,unsigned short,signed char,int,long,unsigned short,short,unsigned short);
'''
main = '''int main(void) {
 if(signed_echo(-32768)!=-32768 || signed_echo(32767)!=32767) return 1;
 if(unsigned_echo(65535)!=65535 || unsigned_echo(0)!=0) return 2;
 if(signed_widen(-1)!=-1L || unsigned_widen(65535)!=65535L) return 3;
 if(narrow(1099511693311L)!=65535) return 4;
 if(mixed(-32768,65535,-1,-7,1099511627776L,65535,-32768,65535)!=1099511758837L) return 5;
 return 42;
}
'''
dirty_prototypes = '''short dirty_signed(void);
unsigned short dirty_unsigned(void);
unsigned short dirty_zero(void);
'''
dirty_main = '''int main(void) {
 if(dirty_signed()!=-1 || dirty_unsigned()!=65535) return 1;
 if((long)dirty_signed()!=-1L || (long)dirty_unsigned()!=65535L) return 2;
 if(dirty_zero() || !dirty_signed() || !dirty_unsigned()) return 3;
 unsigned short x=dirty_zero(); if(x) return 4;
 if((x=dirty_unsigned())!=65535) return 5;
 if((short)dirty_signed()!=-1 || (unsigned char)dirty_unsigned()!=255) return 6;
 return 42;
}
'''
# Only the low halfword is part of the ABI value.
dirty_assembly = '''.text
.globl dirty_signed
dirty_signed:
 movl $0xabcdffff, %eax
 ret
.globl dirty_unsigned
dirty_unsigned:
 movl $0xabcdffff, %eax
 ret
.globl dirty_zero
dirty_zero:
 movl $0xabcd0000, %eax
 ret
.section .note.GNU-stack,"",@progbits
'''
with tempfile.TemporaryDirectory(prefix='kcc halfword ABI ') as directory:
    directory = Path(directory)
    kcc_source, host_source, il, assembly, host_object, executable, dirty = [directory/name for name in
                                  ('k.c', 'h.c', 'k.ssa', 'k.s', 'h.o', 'p', 'dirty.s')]
    for kcc_text, host_text in [(prototypes+main, helpers), (helpers, prototypes+main),
                                 (dirty_prototypes+dirty_main, '')]:
        kcc_source.write_text(kcc_text)
        host_source.write_text(host_text)
        result = subprocess.run([str(compiler), str(kcc_source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, result.stderr
        assert any(fragment in result.stdout for fragment in ('=sh call', 'function sh')), result.stdout
        assert any(fragment in result.stdout for fragment in ('=uh call', 'function uh')), result.stdout
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
print(f'Short ABI {"passed both directions plus dirty upper-return bits" if qbe else "IL checks passed; runtime requires QBE"}; {host}')

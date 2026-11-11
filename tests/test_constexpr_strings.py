"""C23 constexpr string character representability on signed-char LP64."""
import os
import subprocess
import tempfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
kcc=Path(os.environ.get('KCC',root/'build/kcc'))
qbe=os.environ.get('QBE')
host=os.environ.get('HOST_CC','cc')
with tempfile.TemporaryDirectory(prefix='kcc constexpr strings ') as tmp:
    d=Path(tmp); source=d/'test.c'; il=d/'test.ssa'; asm=d/'test.s'; exe=d/'test'
    def compile(text,ok):
        source.write_text(text+'\n')
        r=subprocess.run([str(kcc),str(source)],capture_output=True,text=True,timeout=20)
        assert (r.returncode==0)==ok,(text,r.stderr)
        if ok: assert not r.stderr,r.stderr
        else: assert r.stderr and not r.stdout,(text,r.stderr)
        return r.stdout
    def run(output):
        if qbe:
            il.write_text(output)
            subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=20)
            subprocess.run([host,str(asm),'-o',str(exe)],check=True,timeout=20)
            assert subprocess.run([str(exe)],timeout=10).returncode==42
    # All 256 byte patterns, both literal types and every compatible narrow
    # destination. For the mismatched high-bit cases the C23 constraint fails.
    rejected=0
    for start in range(0,256,16):
        lines=['int main(void) {']
        for value in range(start,start+16):
            for prefix in ('','u8'):
                for t in ('char','signed char','unsigned char'):
                    literal=f'{prefix}"\\x{value:02x}"'
                    source_unsigned=prefix=='u8'; dest_unsigned=t=='unsigned char'
                    valid=value<128 or source_unsigned==dest_unsigned
                    if not valid:
                        compile(f'constexpr {t} a[]={literal};',False); rejected+=1
                        continue
                    name=f'a{value}_{len(lines)}'
                    expected=value if dest_unsigned or value<128 else value-256
                    lines.append(f'constexpr {t} {name}[]={literal};')
                    lines.append(f'if(sizeof({name})!=2 || {name}[0]!={expected} || {name}[1]!=0)return 1;')
        lines.append('return 42;}')
        run(compile('\n'.join(lines),True))
    run(compile(r'''
struct S { char a[4]; signed char b[3]; unsigned char c[3]; };
constexpr struct S s={"\xc3\xa9", "\xff\0", u8"\x80\xff"};
constexpr struct S copy=s;
int main(void) {
 constexpr char local[]="\xff";
 static constexpr unsigned char utf[]=u8"\xff";
 return sizeof(s.a)==4 && s.a[0]==-61 && s.a[1]==-87 && s.a[2]==0 &&
  copy.b[0]==-1 && copy.b[1]==0 && copy.c[0]==128 && copy.c[1]==255 &&
  local[0]==-1 && utf[0]==255 && (constexpr char[]){"\xff"}[0]==-1 ? 42:1;
}
''',True))
    for text in (r'struct S{unsigned char a[2];}; constexpr struct S s={"\xff"};',
                 r'struct S{char a[2];}; constexpr struct S s={u8"\xff"};',
                 r'constexpr char a[]=u8"\xff";',
                 r'int f(void){return (constexpr unsigned char[]){"\xff"}[0];}',
                 r'struct S{unsigned char a[2];}; constexpr struct S s={.a="\xff",.a="A"};'):
        compile(text,False)
print(f'constexpr strings: 256 byte values, six source/destination pairs, {rejected} exact-representability refusals, aggregates and compound literals; '+('QBE/runtime passed' if qbe else 'runtime not run'))

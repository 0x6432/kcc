"""C23 universal characters, including basic and control characters in literals."""
import os
import subprocess
import tempfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
kcc=Path(os.environ.get('KCC',root/'build/kcc'))
qbe=os.environ.get('QBE')
host=os.environ.get('HOST_CC','cc')
with tempfile.TemporaryDirectory(prefix='kcc literal ucn ') as tmp:
    d=Path(tmp); source=d/'input.c'; il=d/'output.ssa'; asm=d/'output.s'; exe=d/'test'
    def compile_text(text, ok=True):
        source.write_text(text)
        r=subprocess.run([str(kcc),str(source)],capture_output=True,text=True,timeout=20)
        assert r.returncode==(0 if ok else 1),(text,r.stderr)
        if ok: assert not r.stderr,r.stderr
        else: assert not r.stdout,(text,r.stderr)
        return r.stdout
    for start in range(0,160,16):
        lines=['#define LETTER \'\\u0041\'', '#if LETTER != 65', '#error wrong UCN character', '#endif', 'int main(void){']
        for cp in range(start,start+16):
            ucn='\\u%04X'%cp; encoded=chr(cp).encode('utf-8')
            for prefix,typ,expected in [('', 'char',encoded),('u8','unsigned char',encoded),('u','unsigned short',[cp]),('U','unsigned int',[cp]),('L','int',[cp])]:
                ident=f'x{prefix or "c"}{cp}'
                lines.append(f'{typ} {ident}[]={prefix}"{ucn}";')
                lines.append(f'if(sizeof({ident})!=sizeof({typ})*{len(expected)+1})return 1;')
                for i,value in enumerate(expected):
                    lines.append(f'if((unsigned int)(unsigned {"char" if typ=="char" else "int"}){ident}[{i}]!={value}u)return 2;')
                lines.append(f'if({ident}[{len(expected)}]!=0)return 3;')
            for prefix in (['','u8','u','U','L'] if cp<128 else ['u','U','L']):
                lines.append(f'if({prefix}\'{ucn}\'!={cp})return 4;')
        lines.append('return 42;}')
        output=compile_text('\n'.join(lines)+'\n')
        if qbe:
            il.write_text(output)
            subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=20)
            subprocess.run([host,str(asm),'-o',str(exe)],check=True,timeout=20)
            assert subprocess.run([str(exe)],timeout=10).returncode==42,start
    extra=r"""
#define C '\U00000041'
#if C != 65
#error wrong long UCN character
#endif
static_assert('\u0041\u0042'==0x4142);
static_assert(U'\U0000007F'==127 && u'\u0000'==0);
char text[]="\U00000041\u0022\u005C\u0000Z";
int main(void){return sizeof(text)==6 && text[0]==65 && text[1]==34 &&
 text[2]==92 && text[3]==0 && text[4]==90 && text[5]==0 ? 42 : 1;}
"""
    output=compile_text(extra)
    if qbe:
        il.write_text(output)
        subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=20)
        subprocess.run([host,str(asm),'-o',str(exe)],check=True,timeout=20)
        assert subprocess.run([str(exe)],timeout=10).returncode==42
    for text in [r"int main(void){return '\uD800';}",r"int main(void){return U'\U00110000';}",
                 r'int main(void){u8"\uDFFF";return 0;}',r'int main(void){u"\u123";return 0;}',
                 r"int main(void){return u8'\u0080';}"]:
        compile_text(text,False)
print('C23 UCN literal checks: 160 scalar values across five string encodings and character forms, malformed cases; '+('QBE runtime passed' if qbe else 'QBE runtime not run'))

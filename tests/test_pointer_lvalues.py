"""Address computation is separate from loads; every pointer operand runs once."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root/'build'/'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
types = [('char',8,False,''),('signed char',8,False,''),('unsigned char',8,True,''),
         ('short',16,False,''),('unsigned short',16,True,''),('int',32,False,''),
         ('unsigned',32,True,'U'),('long',64,False,'L'),('unsigned long',64,True,'UL'),
         ('long long',64,False,'LL'),('unsigned long long',64,True,'ULL')]
programs = []
for name,bits,unsigned,suffix in types:
    for value in (0,42,(1 << (bits-1)),(1 << bits)-1):
        expected = value if unsigned or value < (1 << (bits-1)) else value-(1 << bits)
        spelling = (f'(-9223372036854775807{suffix}-1{suffix})'
                    if bits==64 and not unsigned and expected==-(1 << 63) else f'{expected}{suffix}')
        programs.append(f'int main(void) {{ {name} x=0; {name} *p=&x; if((*p={value}ULL)!={spelling}) return 1; '
                        f'if(x!={spelling} || *p!={spelling}) return 2; return 42; }}')
programs += [
    'int main(void) { _Bool b=0; _Bool *p=&b; if((*p=256)!=1 || !b) return 1; *p=0; return !*p+41; }',
    'int main(void) { int x=42; int y=0; int *p=&y; int **q=&p; *q=&x; return **q; }',
    'int main(void) { int x=42; return *&x; }',
    'int main(void) { int x=7; int y=3; int *p=&x; return ((*p&y)==3)+41; }',
    'int main(void) { int x=6; int y=7; int *p=&x; return *p * *&y; }',
    'int f(int *p,int n) { if(n==0) return *p; *p=*p+1; return f(p,n-1); } int main(void) { int x=39; return f(&x,3); }',
    'int *get(int *p,int *n) { *n=*n+1; return p; } int main(void) { int x=0; int n=0; *get(&x,&n)=40; '
    'if(n!=1) return 1; int *q=&*get(&x,&n); if(n!=2) return 2; int y=*get(q,&n); if(n!=3 || y!=40) return 3; return 42; }',
    'int main(void) { int x=0; int *p=&x; 0 && (*p=1); 1 || (*p=2); return x+42; }',
    'int main(void) { int x=0; int *p=&x; *p=1 && 42; return x+41; }',
]
signature = 'int mutate(int *p,char *c,unsigned char *u,short *s,unsigned short *t,long *l,_Bool *b,int **pp)'
body = ' { *p=42; *c=255; *u=255; *s=65535; *t=65535; *l=1L<<40; *b=256; *pp=p; return 0; }\n'
cancel = 'int *cancel(int *p) { return &*p; }\n'
prototypes = signature+';\nint *cancel(int *);\n'
driver = '''int main(void) {
 int x=0; char c=0; unsigned char u=0; short s=0; unsigned short t=0; long l=0; _Bool b=0;
 int y=7; int *p=&y;
 if(mutate(&x,&c,&u,&s,&t,&l,&b,&p)) return 1;
 if(x!=42 || c!=-1 || u!=255 || s!=-1 || t!=65535 || l!=1099511627776L || b!=1 || *p!=42) return 2;
 if(*cancel(&x)!=42) return 3;
 return 42;
}
'''
# Host checks exact address identity and the valid &*null cancellation rule.
host_driver = driver.replace('if(*cancel(&x)!=42)', 'if(p!=&x || cancel(0)!=0 || cancel(&x)!=&x || *cancel(&x)!=42)')
with tempfile.TemporaryDirectory(prefix='kcc pointer lvalues ') as directory:
    directory = Path(directory)
    source,other,il,assembly,obj,executable = [directory/name for name in ('k.c','h.c','p.ssa','p.s','h.o','p')]
    for text in programs:
        source.write_text(text+'\n')
        result = subprocess.run([str(compiler),str(source)],capture_output=True,text=True,timeout=5)
        assert result.returncode==0 and not result.stderr,(text,result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe,'-t','amd64_sysv','-o',str(assembly),str(il)],check=True,timeout=10)
            subprocess.run([host,str(assembly),'-o',str(executable)],check=True,timeout=10)
            assert subprocess.run([str(executable)],timeout=5).returncode==42,text
        subprocess.run([host,'-std=c2x','-fsigned-char',str(source),'-o',str(executable)],capture_output=True,check=True,timeout=10)
        assert subprocess.run([str(executable)],timeout=5).returncode==42,text
    for text,host_text in [(signature+body+cancel,prototypes+host_driver),
                            (prototypes+driver,signature+body+cancel)]:
        source.write_text(text)
        other.write_text(host_text)
        result = subprocess.run([str(compiler),str(source)],capture_output=True,text=True,timeout=5)
        assert result.returncode==0 and not result.stderr,result.stderr
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe,'-t','amd64_sysv','-o',str(assembly),str(il)],check=True,timeout=10)
            subprocess.run([host,'-std=c2x','-fsigned-char','-c',str(other),'-o',str(obj)],capture_output=True,check=True,timeout=10)
            subprocess.run([host,str(assembly),str(obj),'-o',str(executable)],check=True,timeout=10)
            assert subprocess.run([str(executable)],timeout=5).returncode==42
    for depth,valid in [(63,True),(64,False)]:
        stars='*'*depth
        source.write_text(f'int f(int {stars}p) {{ return {stars}p; }}\n')
        result = subprocess.run([str(compiler),str(source)],capture_output=True,text=True,timeout=5)
        assert (result.returncode==0)==valid and bool(result.stdout)==valid,result.stderr
        if not valid:
            assert 'depth' in result.stderr,result.stderr
        elif qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe,'-t','amd64_sysv','-o',str(assembly),str(il)],check=True,timeout=10)
    rejected=[('int main(void) { return *42; }','indirection requires'),
              ('int main(void) { int *p=&42; return 0; }','address-of requires'),
              ('int main(void) { int x=0; int *p=&(x=1); return 0; }','address-of requires'),
              ('int main(void) { int x=0; int *p=&(int)x; return 0; }','address-of requires'),
              ('int main(void) { int x=0; int *p=&x; return p+1; }','pointer binary'),
              ('int main(void) { return *&42; }','address-of requires')]
    for text,message in rejected:
        source.write_text(text+'\n')
        result=subprocess.run([str(compiler),str(source)],capture_output=True,text=True,timeout=5)
        assert result.returncode==1 and not result.stdout and message in result.stderr,(text,result.stderr)
print(f'Pointer lvalues passed ({len(programs)} full-value host/model programs, both-direction eight-arg memory ABI, address identity/null cancellation and depth bounds; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

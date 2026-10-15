"""Compatible pointer equality uses full pointer bits, not integer conversions."""
import os
import subprocess
import tempfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
compiler=root/'build'/'kcc'
host=os.environ.get('HOST_CC','cc')
qbe=os.environ.get('QBE')
names=['_Bool','char','signed char','unsigned char','short','unsigned short',
       'int','unsigned','long','unsigned long','long long','unsigned long long']
programs=[]
for name in names:
    programs.append(f'int main(void) {{ {name} x=0; {name} y=0; {name} *p=&x; {name} *q=&y; '
                    f'if(p==q || !(p!=q) || p!=p) return 1; q=p; if(p!=q || !(p==q)) return 2; '
                    f'if((q=p)!=p || ({name} *)q!=p) return 3; return 42; }}')
programs += [
    'int main(void) { int x=0; int *p=&x; int **q=&p; if(q==&p && *q==&x && &*p==p) return 42; return 1; }',
    'int *get(int *p,int *n) { *n=*n+1; return p; } int main(void) { int x=42; int n=0; '
    'if(get(&x,&n)!=&x || n!=1) return 1; 0 && (get(&x,&n)==&x); 1 || (get(&x,&n)!=&x); return n+41; }',
    'int main(void) { int x=0; int y=0; return (&x==&x)+(&x!=&y)+(&x==&y)+40; }',
]
helpers='int equal(int *p,int *q) { return p==q; } int different(int *p,int *q) { return p!=q; }\n'
prototypes='int equal(int *,int *); int different(int *,int *);\n'
relay='int relay(int *p,int *q) { return equal(p,q)+2*different(p,q); }\n'
main='''int main(void) { int x=0; int y=0;
 if(equal(&x,&x)!=1 || equal(&x,&y)!=0 || different(&x,&y)!=1) return 1;
 if(equal(0,0)!=1 || different(0,0)!=0 || equal(0,&x)!=0 || different(&x,0)!=1) return 2;
 if(relay(&x,&x)!=1 || relay(&x,&y)!=2 || relay(0,0)!=1 || relay(&x,0)!=2) return 3;
 return 42; }
'''
with tempfile.TemporaryDirectory(prefix='kcc pointer equality ') as directory:
    directory=Path(directory)
    source,other,il,assembly,obj,executable=[directory/name for name in ('k.c','h.c','p.ssa','p.s','h.o','p')]
    for text in programs:
        source.write_text(text+'\n')
        result=subprocess.run([str(compiler),str(source)],capture_output=True,text=True,timeout=5)
        assert result.returncode==0 and not result.stderr,(text,result.stderr)
        assert 'ceql' in result.stdout or 'cnel' in result.stdout,result.stdout
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe,'-t','amd64_sysv','-o',str(assembly),str(il)],check=True,timeout=10)
            subprocess.run([host,str(assembly),'-o',str(executable)],check=True,timeout=10)
            assert subprocess.run([str(executable)],timeout=5).returncode==42,text
        subprocess.run([host,'-std=c2x','-fsigned-char',str(source),'-o',str(executable)],capture_output=True,check=True,timeout=10)
        assert subprocess.run([str(executable)],timeout=5).returncode==42,text
    for text,host_text in [(helpers,prototypes+relay.replace('relay(', 'host_relay(')+main.replace('relay(', 'host_relay(')),
                            (prototypes+relay,helpers+'int relay(int *,int *);\n'+main)]:
        # First arrangement exercises host callers; second adds kcc callers of
        # host implementations. Null pointers are created only in host source.
        source.write_text(text)
        other.write_text(host_text)
        result=subprocess.run([str(compiler),str(source)],capture_output=True,text=True,timeout=5)
        assert result.returncode==0 and not result.stderr,result.stderr
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe,'-t','amd64_sysv','-o',str(assembly),str(il)],check=True,timeout=10)
            subprocess.run([host,'-std=c2x','-c',str(other),'-o',str(obj)],check=True,timeout=10)
            subprocess.run([host,str(assembly),str(obj),'-o',str(executable)],check=True,timeout=10)
            assert subprocess.run([str(executable)],timeout=5).returncode==42
    rejected=[('int f(int *p,unsigned *q) { return p==q; }','compatible pointer'),
              ('int f(char *p,signed char *q) { return p!=q; }','compatible pointer'),
              ('int f(int *p) { return p==0; }','null constants'),
              ('int f(int *p) { return 0!=p; }','null constants'),
              ('int f(int *p) { return p/p; }','pointer binary'),
              ('int *f(int *p) { return p*2; }','pointer binary'),
              ('int f(int *p) { return p&p; }','pointer binary')]
    for text,message in rejected:
        source.write_text(text+'\n')
        result=subprocess.run([str(compiler),str(source)],capture_output=True,text=True,timeout=5)
        assert result.returncode==1 and not result.stdout and message in result.stderr,(text,result.stderr)
print(f'Pointer equality passed ({len(programs)} full-value host programs, both-direction live/null ABI, once-only side effects and constraints; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

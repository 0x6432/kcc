"""Sequenced comma values, void effects and assignment-expression separator boundaries."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root / 'build' / 'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
integers = ['_Bool', 'char', 'signed char', 'unsigned char', 'short',
            'unsigned short', 'int', 'unsigned', 'long', 'unsigned long',
            'long long', 'unsigned long long']
programs = []
for name in integers:
    programs.append(f'''int main(void) {{ int n=0; {name} x=7,y=(n=1,x);
 if(n!=1 || y!=({name})7) return 1; return 42; }}''')
programs += [
 'int main(void) { int x=1,y=(x=2,3); if(x!=2) return 1; return y+39; }',
 'int main(void) { int a[2]; a[1]=42; return a[0,1]; }',
 'int main(void) { int x=0; return x=1,x=x+1,x=x+40; }',
 'int main(void) { int x=(1,13),y=(x,x+29); return y; }',
 'int add(int a,int b) { return a+b; } int main(void) { int n=0,x=add((n=1,13),29); if(n!=1) return 1; return x; }',
 'int main(void) { int x=0,y=0; for(x=1,y=0;x<4;x=x+1,y=y+x) ; return y+33; }',
 'int main(void) { int a[3]; int i=0; a[(i=1,i+1)]=42; return a[2]; }',
 'int main(void) { int x=0; if((x=42,x==42)) return x; return 1; }',
 'int main(void) { int x=0; while((x=x+1,x<42)) ; return x; }',
 'int main(void) { int x=0; do ; while((x=x+1,x<42)); return x; }',
 'int main(void) { int x=0; return (0&&(x=1),x+42); }',
 'int main(void) { int x=0; return (1||(x=1),x+42); }',
 'void set(int *p) { *p=42; } int main(void) { int x=0; return (set(&x),x); }',
 'void step(int *p) { *p=*p+1; } int main(void) { int x=40; step(&x),step(&x); return x; }',
 'void step(int *p) { *p=*p+1; } int main(void) { int x=40; (void)(step(&x),step(&x)); return x; }',
 'void step(int *p) { *p=*p+1; } int main(void) { int x=40; (x=x+1,step(&x)); return x; }',
 'int main(void) { int a[2][3]; a[1][2]=42; int (*p)[3]=((void)0,a); return p[1][2]; }',
 'int main(void) { char *p=((void)0,"hi"); if(p[0]!=104 || p[1]!=105 || p[2]!=0) return 1; return 42; }',
 'int id(int x) { return x; } int main(void) { int n=0; int (*p)(int)=(n=1,id); if(n!=1) return 1; return p(42); }',
 'int id(int x) { return x; } int main(void) { int n=0,x=(n=1,id)(42); if(n!=1) return 1; return x; }',
 'int main(void) { int x=42; void *p=((void)0,&x); int *q=((void)1,p); return *q; }',
 'int main(void) { long long x=(1,4611686018427387904LL); if(x!=4611686018427387904LL) return 1; return 42; }',
 '#define PAIR(a,b) ((a),(b))\nint main(void) { int x=0; return PAIR(x=13,x+29); }',
]
with tempfile.TemporaryDirectory(prefix='kcc comma expressions ') as directory:
    directory = Path(directory)
    source, other, il, assembly, obj, executable, dirty = [directory / name for name in
                                                          ('k.c', 'h.c', 'p.ssa', 'p.s', 'h.o', 'p', 'dirty.s')]

    def compile_source(text):
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
        return result.stdout

    def link_and_run(host_text=None, assembly_text=None):
        objects = [str(assembly)]
        if host_text is not None:
            other.write_text(host_text)
            subprocess.run([host, '-std=c2x', '-fsigned-char', '-c', str(other), '-o', str(obj)],
                           capture_output=True, check=True, timeout=10)
            objects.append(str(obj))
        if assembly_text is not None:
            dirty.write_text(assembly_text)
            objects.append(str(dirty))
        subprocess.run([host, *objects, '-o', str(executable)], check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, host_text


    for text in programs:
        compile_source(text)
        if qbe:
            link_and_run()
        result = subprocess.run([host, '-std=c2x', '-fsigned-char', str(source), '-o', str(executable)],
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, (text, result.stderr)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, text

    for name in integers + ['int *', 'void *']:
        identity = f'{name} id({name} x) {{ return ((void)0,x); }}\n'
        relay = f'{name} id({name}); {name} relay({name} x) {{ return ((void)0,id(x)); }}\n'
        prototype = f'{name} id({name}); {name} relay({name});\n'
        if name in ['int *', 'void *']:
            driver = prototype + 'int main(void) { int x=42; if(relay(&x)!=&x) return 1; return 42; }'
        else:
            driver = prototype + f'int main(void) {{ if(relay(7)!=({name})7) return 1; return 42; }}'
        for kcc_text, host_text in [(identity, relay+driver), (relay, identity+driver)]:
            compile_source(kcc_text)
            if qbe:
                link_and_run(host_text)

    compile_source('int test(int *p,void (*step)(int *)) { return (step(p),*p); }')
    if qbe:
        link_and_run('int test(int *,void (*)(int *)); void step(int *p) { *p=*p+1; } int main(void) { int x=41; return test(&x,step); }')

    for terms, valid in [(127, True), (128, False)]:
        source.write_text('int f(int x) { return x,' + '0,' * (terms-2) + '42; }')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'typed expression exceeds depth limit (128)' in result.stderr, result.stderr

    invalid = [
      'int f(void) { return ,1; }', 'int f(void) { return 1,; }',
      'int f(int); int g(void) { return f(1,2); }',
      'int f(int,int); int g(void) { return f((1,2)); }',
      'int f(void) { int x=0,y=1; (x,y)=42; return x; }',
      'int f(void) { int x=0,y=1; return &(x,y)==&x; }',
      'void g(void); int f(void) { return (1,g()); }',
      'void g(void); int f(void) { int x=(1,g()); return x; }',
      'void g(void); int f(void) { if((1,g())) return 1; return 0; }',
      'void g(void); int f(void) { return !(1,g()); }',
      'void g(void); int f(void) { return 1+(1,g()); }',
      'void g(void); int f(int); int h(void) { return f((1,g())); }',
      'void g(void) { return ((void)1,(void)2); }',
      'int f(void) { int x=1,2; return x; }',
      'int f(void) { int x=(1,missing); return x; }',
      'int f(void) { return 1,missing; }',
    ]
    for text in invalid:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and 'error:' in result.stderr, (text, result.stderr)
print(f'Comma expressions passed ({len(programs)} full-value programs, sequenced scalar/void/pointer effects, '
      f'argument/declaration separators, both-direction primitive/pointer ABI, exact typed depth and {len(invalid)} constraints; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

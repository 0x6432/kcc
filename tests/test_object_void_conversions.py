"""Object/void pointer conversions without weakening semantic type compatibility."""
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
    programs.append(f'''void *erase({name} *p) {{ return p; }}
{name} *restore(void *p) {{ return p; }}
int main(void) {{ {name} x=7; {name} *p=&x; void *v=p; {name} *q=v;
 if(v!=p || p!=v || !(v==q) || !(q==v)) return 1;
 v=&x; q=v; if(q!=p || restore(erase(p))!=p || *restore(v)!=({name})7) return 2;
 if((({name} *)(void *)p)!=p) return 3; return 42; }}''')
programs += [
 'int main(void) { int x=42,*p=&x; void *v=&p; int **q=v; if(*q!=p || v!=&p || &p!=v) return 1; return **q; }',
 'int main(void) { int a[2][3]; a[1][2]=42; void *v=a; int (*p)[3]=v; if(v!=a || a!=v) return 1; return p[1][2]; }',
 'int f(void) { return 42; } int main(void) { int (*p)(void)=f; void *v=&p; int (**q)(void)=v; return (*q)(); }',
 'int main(void) { int a[3]; a[2]=42; int (*p)[]= &a; void *v=p; int (*q)[]=v; if(v!=q || q!=v) return 1; return (*q)[2]; }',
 'int main(void) { int x=42; int *p=&x; void *v=&x; if((p=v)!=p || (v=p)!=v) return 1; return *p; }',
 'void *erase(int *p) { return p; } int *restore(void *p) { return p; } '
 'int main(void) { int x=42; void *(*e)(int *)=erase; int *(*r)(void *)=restore; return *r(e(&x)); }',
 'int *get(int *p,int *n) { *n=*n+1; return p; } void *erase(int *p,int *n) { *n=*n+1; return p; } '
 'int main(void) { int x=42,a=0,b=0; if(get(&x,&a)!=erase(&x,&b) || a!=1 || b!=1) return 1; '
 'if(erase(&x,&a)!=get(&x,&b) || a!=2 || b!=2) return 2; return x; }',
 'int main(void) { int a[3]; void *v=&a[1]; if(v==&a[0] || &a[2]==v || !(v!=&a[0]) || !(&a[2]!=v)) return 1; return 42; }',
 'int main(void) { int x=42; void *v=&x; _Bool b=v; if(!b || !(_Bool)v) return 1; return *(int *)v; }',
]
with tempfile.TemporaryDirectory(prefix='kcc object void pointers ') as directory:
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

    for name in integers:
        erase = f'void *erase({name} *p) {{ return p; }}\n'
        restore = f'{name} *restore(void *p) {{ return p; }}\n'
        prototypes = f'void *erase({name} *); {name} *restore(void *);\n'
        driver = prototypes + f'int main(void) {{ {name} x=7; {name} *p=restore(erase(&x)); if(p!=&x || *p!=({name})7) return 1; return 42; }}'
        relay = f'int relay(void *p) {{ {name} *q=p; return erase(q)==p && restore(p)==q; }}\n'
        relay_driver = prototypes + f'int relay(void *); int main(void) {{ {name} x=0; if(!relay(&x)) return 1; return 42; }}'
        for kcc_text, host_text in [(erase+restore, driver), (relay, erase+restore+relay_driver)]:
            compile_source(prototypes + kcc_text)
            if qbe:
                link_and_run(host_text)

    compile_source('void *from_object(int *p) { return p; } int *to_object(void *p) { return p; } '
                   'int check(void *p,int *q) { return p==q && q==p && from_object(q)==p && to_object(p)==q; }')
    if qbe:
        link_and_run('int check(void *,int *); int main(void) { int x=0; if(!check(0,0)||!check(&x,&x)) return 1; return 42; }')

    # Distinct live objects make every register/stack position and tail observable.
    signature = 'void *pick(void *a,void *b,void *c,void *d,void *e,void *f,void *g,long long n)'
    helper = signature + (' { if(*(int *)a==1 && *(int *)b==2 && *(int *)c==3 && *(int *)d==4 && '
                          '*(int *)e==5 && *(int *)f==6 && *(int *)g==7 && n==4611686018427387904LL) '
                          '{ int *p=g; *p=42; } return g; }')
    relay = signature + ('; int relay(void) { int a[7]; a[0]=1; a[1]=2; a[2]=3; a[3]=4; '
                         'a[4]=5; a[5]=6; a[6]=7; int *p=pick(&a[0],&a[1],&a[2],&a[3],&a[4],&a[5],&a[6],'
                         '4611686018427387904LL); if(p!=&a[6]) return 1; return *p; }')
    driver = 'int relay(void); int main(void) { return relay(); }'
    for kcc_text, host_text in [(relay, helper+driver), (helper, relay+driver)]:
        compile_source(kcc_text)
        if qbe:
            link_and_run(host_text)

    # Each inserted conversion counts toward the unchanged typed AST budget.
    for casts, valid in [(125, True), (126, False)]:
        source.write_text('void *f(int *p) { return ' + '(int *)' * casts + 'p; }')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'depth limit (128)' in result.stderr, result.stderr

    invalid = [
      'void *f(int (*p)(void)) { return p; }', 'int (*f(void *p))(void) { return p; }',
      'void *f(int (*p)(void)) { return (void *)p; }', 'int (*f(void *p))(void) { return (int (*)(void))p; }',
      'int f(void *p,int (*q)(void)) { return p==q; }', 'int f(void *p,int (*q)(void)) { return q!=p; }',
      'int **f(void **p) { return p; }', 'void **f(int **p) { return p; }',
      'int f(void **p,int **q) { return p==q; }', 'int f(void **p,int **q) { return p!=q; }',
      'int **f(void **p) { return (int **)p; }', 'void **f(int **p) { return (void **)p; }',
      'int f(void *p,int *q) { return p<q; }', 'int f(void *p,int *q) { return q<=p; }',
      'void *f(void *p) { return p+0; }', 'int f(void *p) { return p[0]; }',
      'long f(void *p) { return p-p; }', 'int f(void *p) { return *p; }',
      'void *f(void); int *f(void);', 'void f(void *); void f(int *);',
      'void *f(void) { return 0; }', 'void *f(void) { return (void *)0; }',
      'int f(void *p) { return p==0; }', 'int f(void *p) { return (int)p; }',
    ]
    for text in invalid:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and 'error:' in result.stderr, (text, result.stderr)
print(f'Object/void conversions passed ({len(programs)} full-value programs, all primitive round trips and both ABI directions, '
      f'mixed stack/null/effect checks, exact conversion depth and {len(invalid)} constraints; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

"""Void syntax, effect-only lowering and host/QBE fixed-call interoperability."""
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
programs = [
 'void set(int *p) { *p=42; return; } int main(void) { int x=0; set(&x); return x; }',
 'void set(int *p) { *p=42; } int main(void) { int x=0; (void)set(&x); return x; }',
 'void set(int *p) { *p=42; } int main(void) { int x=0; void (*p)(int *)=set; p(&x); return x; }',
 'void set(int *p) { *p=42; } void apply(void f(int *),int *p) { f(p); } '
 'int main(void) { int x=0; apply(set,&x); return x; }',
 'void set(int *p) { *p=42; } void (*factory(void))(int *) { return set; } '
 'int main(void) { int x=0; factory()(&x); return x; }',
 'void set(int *p) { if(*p==42) return; *p=42; } int main(void) { int x=42; set(&x); return x; }',
 'int main(void) { int x=0; (void)(x=42); return x; }',
 'int main(void) { int x=0; (void)(void)(void)(x=42); return x; }',
 'int main(void) { int x=42; (void)&x; (void)"abc"; (void)x; return x; }',
 'void step(int *p) { *p=*p+1; } int main(void) { int x=0; for(step(&x);x<42;step(&x)) ; return x; }',
 'void set(int *p) { *p=42; } int main(void) { int x=0; for((void)set(&x);0;(void)set(&x)) ; return x; }',
 'void (set)(int *p) { *p=42; } int main(void) { int x=0; void (*a[2])(int *); '
 'a[0]=set; a[1]=&set; (*a[1])(&x); return x; }',
 'void set(int *p) { *p=42; } void (*pick(int *p))(int *) { *p=*p+1; return set; } '
 'int main(void) { int n=0,x=0; pick(&n)(&x); if(n!=1) return 1; return x; }',
 'void f(void); void f() { return; } int main(void) { f(); return 42; }',
 'void recur(int *p) { if(*p==42) return; *p=*p+1; recur(p); } '
 'int main(void) { int x=0; recur(&x); return x; }',
 'void ignore(int,void (int *)) { return; } void set(int *p) { *p=42; } '
 'int main(void) { int x=41; ignore(x=x+1,set); return x; }',
]
with tempfile.TemporaryDirectory(prefix='kcc void functions ') as directory:
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
        helper = f'void set({name} *p,{name} x) {{ *p=x; }}\n'
        relay = f'void relay(void callback({name} *,{name}),{name} *p,{name} x) {{ callback(p,x); }}\n'
        prototype = f'void set({name} *,{name}); void relay(void (*)({name} *,{name}),{name} *,{name});\n'
        if name in ['int *', 'void *']:
            driver = prototype + f'int main(void) {{ int x=42; {name} p=0; relay(set,&p,&x); if(p!=&x) return 1; return 42; }}'
        else:
            driver = prototype + f'int main(void) {{ {name} x=0; relay(set,&x,7); if(x!=({name})7) return 1; return 42; }}'
        for kcc_text, host_text in [(helper, relay + driver), (relay, helper + driver)]:
            compile_source(kcc_text)
            if qbe:
                link_and_run(host_text)

    signature = 'void mixed(int *p,char a,short b,int c,long d,unsigned e,long long f,long long g)'
    body = ' { if(a+b+c+d+e+f+g==4611686022722355219LL) *p=42; }\n'
    relay = ('void relay(void callback(int *,char,short,int,long,unsigned,long long,long long),int *p) '
             '{ callback(p,1,2,3,4294967296L,5,7,4611686018427387905LL); }\n')
    driver = (signature + '; void relay(void (*)(int *,char,short,int,long,unsigned,long long,long long),int *); '
              'int main(void) { int x=0; relay(mixed,&x); return x; }')
    for kcc_text, host_text in [(relay, signature + body + driver), (signature + body, relay + driver)]:
        compile_source(kcc_text)
        if qbe:
            link_and_run(host_text)

    # No void temporary/ABI result is fabricated, including fallthrough.
    il_text = compile_source('void f(void) {} void g(void) { f(); (void)f(); return; } '
                             'void h(void (*p)(void)) { p(); }')
    assert 'export function $f(' in il_text and 'export function $g(' in il_text, il_text
    assert il_text.count('call $f(') == 2 and '\tcall %t' in il_text, il_text
    assert '=w call' not in il_text and '=l call' not in il_text and 'ret 0' not in il_text, il_text

    compile_source('void *id(void *p) { return &*p; } int check(void *p) { void *q=p; '
                   'q=(void *)q; return id(p)==q; }')
    if qbe:
        link_and_run('int check(void *); int main(void) { int x=0; if(!check(0)||!check(&x)) return 1; return 42; }')
    # Evaluate only the pointer-producing effect; never execute a null indirection.
    compile_source('void *pick(void *p,int *n) { *n=*n+1; return p; } '
                   'void effect(void *p,int *n) { *pick(p,n); (void)*pick(p,n); }')
    if qbe:
        link_and_run('void effect(void *,int *); int main(void) { int x=42,n=0; effect(&x,&n); '
                     'if(n!=2 || x!=42) return 1; return 42; }')

    for casts, valid in [(127, True), (128, False)]:
        source.write_text('void f(void) { ' + '(void)' * casts + '1; }')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'depth limit (128)' in result.stderr, result.stderr

    invalid = [
      'void f(void) { return 1; }', 'void f(void) { return (void)1; }',
      'void g(void); void f(void) { return g(); }', 'int f(void) { return; }',
      'void f(void x);', 'void f(void,int);', 'void f(int,void);', 'void f(void a[3]);',
      'void f(void) { void x; }', 'void f(void) { void x[2]; }',
      'void f(void) { void (*p)[2]; }', 'void main(void) {}',
      'void int f(void);', 'int void f(void);', 'void void f(void);',
      'void f(void); int f(void);', 'void f(void *); void f(int *);',
      'void f(void) { void *p; p=p+0; }', 'void f(void *p) { p[0]; }',
      'long f(void *p) { return p-p; }', 'void f(void *p) { *p=1; }',
      'void f(void); int g(void) { return f(); }',
      'void f(void); int g(void) { int x=f(); return x; }',
      'void f(void); int g(void) { int x=0; x=f(); return x; }',
      'void f(void); int g(void) { return (int)f(); }',
      'void f(void); int g(void) { return (_Bool)f(); }',
      'void f(void); int g(void) { return (int *)f()==(int *)f(); }',
      'void f(void); int g(int); int h(void) { return g(f()); }',
      'void f(void); void g(void) { if(f()) ; }',
      'void f(void); void g(void) { while(f()) ; }',
      'void f(void); void g(void) { do ; while(f()); }',
      'void f(void); void g(void) { for(;f();) ; }',
      'void f(void); void g(void) { &f(); }',
      'void f(void); void g(void) { f()(); }',
      'void f(void); void g(void) { *f(); }',
      'void f(void); void g(void) { void (*p)(void)=1; }',
      'void f(void); void g(void) { int (*p)(void)=f; }',
      'void f(void **p) { int **q=p; }',  # Nested pointer compatibility is not erased.
    ]
    invalid += ['void f(void); void g(void) { ' + expression + '; }' for expression in
                ['!f()', '+f()', '-f()', '~f()', 'f()+1', '1+f()', 'f()==f()', 'f()<f()',
                 'f()&&1', '1||f()', 'f()<<1', '1&f()', 'f()*1', 'f()[0]']]
    for text in invalid:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and 'error:' in result.stderr, (text, result.stderr)
print(f'Void functions passed ({len(programs)} full-value programs, all primitive/pointer callback ABI in both directions, '
      f'mixed stack ABI, no-result IL, cancellation/discard effects, exact depth and {len(invalid)} constraints; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

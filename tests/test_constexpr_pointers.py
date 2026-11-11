"""C23 constexpr null pointers: typed named constants and real storage."""
import os
import subprocess
import tempfile
from pathlib import Path
root = Path(__file__).resolve().parents[1]
kcc = Path(os.environ.get('KCC',root/'build'/'kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC','cc')
programs = [
    '''constexpr int *p=0; constexpr int *q=p; int *r=q;
       int main(void) { int *const *a=&p; return *a==0 && q==nullptr && r==0 ? 42:1; }''',
    '''constexpr void *p={}; constexpr const int *q=p; const int *r=q;
       int main(void) { return p==nullptr && q==0 && r==0?42:1; }''',
    '''constexpr auto p=(int *)0; static constexpr auto q=p;
       int main(void) { static constexpr auto r=q; int *s=r; return s==0?42:1; }''',
    '''typedef typeof(nullptr) nullptr_t; constexpr nullptr_t nil=nullptr;
       constexpr auto other=nil; int *p=other;
       int main(void) { constexpr auto n=nil; return n==nullptr && p==nullptr?42:1; }''',
    '''typedef typeof(nullptr) nullptr_t; constexpr nullptr_t n={};
       int main(void) { return n==nullptr?42:1; }''',
    '''constexpr int *p={{}}; int main(void) { constexpr int z={};
       constexpr int *q={p}; static constexpr int *r={}; return !p && !q && !r && !z ? 42:1; }''',
    '''constexpr int *p=0; int f(void) { static constexpr int *q=p; return q==0; }
       int main(void) { return f() && f()?42:1; }''',
    '''constexpr int (*f)(void)=nullptr; int (*g)(void)=f;
       int main(void){return f==nullptr && g==0?42:1;}''',
    '''constexpr const volatile int *p=0; constexpr const volatile int *q=p;
       int main(void){return q==0?42:1;}''',
    '''constexpr int *p=1 ? (int*)0 : (int*)1;
       int main(void) { constexpr auto q=0 ? (int*)1 : p; return q==0?42:1; }''',
    '''constexpr void *p=nullptr; void *q=p; int main(void){return q==nullptr?42:1;}''',
]
negative = [
    ('int x; constexpr int *p=&x;', 'null constant expression'),
    ('constexpr int *p=(int *)1;', 'null constant expression'),
    ('int x; int f(void){ constexpr int *p=&x; return 0; }', 'null constant expression'),
    ('int x; int f(void){ static constexpr auto p=&x; return 0; }', 'null constant expression'),
    ('int *p; constexpr int *q=p;', 'null constant expression'),
    ('constexpr int *p=p;', 'unavailable in its initializer'),
    ('constexpr int *p=0; int f(void){ constexpr int *p=p; return 0; }', 'unavailable in its initializer'),
    ('constexpr int *volatile p=0;', 'requires a non-atomic'),
    ('constexpr int *restrict p=0;', 'requires a non-atomic'),
    ('int f(void){ constexpr int *p=0; p=0; return 0; }', 'modifiable'),
    ('constexpr int *p=0; constexpr char *q=p;', 'pointer'),
    # A pointer-valued named constant is not a null pointer constant or ICE.
    ('constexpr void *p=0; int n=p;', 'integer'),
    ('constexpr int *p=0; static_assert(p==0);', 'constant'),
    ('constexpr int *p={0,0};', 'one initializer expression'),
]
with tempfile.TemporaryDirectory(prefix='kcc constexpr pointers ') as tmp:
    d=Path(tmp); source=d/'p.c'; il=d/'p.ssa'; asm=d/'p.s'; exe=d/'p'
    def compile_text(text):
        source.write_text(text+'\n')
        return subprocess.run([str(kcc),str(source)],capture_output=True,text=True,timeout=15)
    for text in programs:
        result=compile_text(text)
        assert result.returncode==0 and not result.stderr,(text,result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=15)
            subprocess.run([host,str(asm),'-o',str(exe)],check=True,timeout=15)
            assert subprocess.run([str(exe)],timeout=5).returncode==42,text
    for text, message in negative:
        result=compile_text(text)
        assert result.returncode==1 and not result.stdout and message in result.stderr,(text,message,result.stderr)
    if qbe:
        result=compile_text('constexpr int *p=0; int *const *fetch(void) { static constexpr auto x=p; return &x; }')
        assert result.returncode==0,result.stderr
        il.write_text(result.stdout)
        subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=15)
        native=d/'native.c'; native.write_text('int *const *fetch(void); int main(void) { int *const *p=fetch(); return p==fetch() && !*p ? 42 : 1; }\n')
        subprocess.run([host,str(asm),str(native),'-o',str(exe)],check=True,timeout=15)
        assert subprocess.run([str(exe)],timeout=5).returncode==42
print(f'constexpr pointers: {len(programs)} executable cases, {len(negative)} refusals and native storage interoperability')

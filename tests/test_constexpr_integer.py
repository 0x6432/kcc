"""C23 constexpr integer objects: storage, named ICEs, conversion and refusals."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
kcc = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')

programs = [
    '''constexpr auto a=40; static constexpr auto b=a+2; static_assert(b==42);
       int main(void) { static constexpr auto c=b; static_assert(c==42); const int *p=&c; return *p; }''',
    '''typedef long T; constexpr auto x=(T)42; static_assert(x==42);
       int main(void) { static constexpr auto T=x; const long *p=&T; return *p; }''',
    '''constexpr auto a=(unsigned char)42; int main(void) { static constexpr auto b=a;
       const unsigned char *p=&b; return *p; }''',
    '''constexpr auto x=40; int f(void) { static constexpr auto y=x+2; return y; }
       int main(void) { return f()==42 && f()==42 ? 42 : 1; }''',
    '''constexpr auto zero=0; int *p=zero; int main(void){return p==0?42:1;}''',
    '''constexpr auto x=18446744073709551615ULL; static_assert(x==~0ULL);
       int main(void) { static constexpr auto n=(_BitInt(16))42; return n; }''',
    '''enum E : unsigned short { FIRST=42 }; constexpr auto x=(enum E)FIRST;
       int main(void) { const enum E *p=&x; static_assert(x==42); return *p; }''',
    '''constexpr int a=40; constexpr int b=a+2; static_assert(b==42);
       enum E { ANSWER=b }; int table[b];
       int main(void) { const int *p=&b; return ANSWER==42 && sizeof(table)==168 && *p==42 ? 42 : 1; }''',
    '''constexpr int zero=0; int *p=zero; constexpr int n=42;
       int main(void) { switch (n) { case n: return p==0 ? 42 : 1; default: return 1; } }''',
    '''typedef unsigned short T; constexpr T a=40; constexpr typeof(a) b=a+2;
       static_assert(b==42); int main(void) { const T *p=&b; return *p; }''',
    '''constexpr enum E : unsigned long { E0=1 } a=42;
       static_assert(a==42); int main(void) { const enum E *p=&a; return *p; }''',
    '''int main(void) { constexpr int a=40; constexpr auto b=a+2;
       static constexpr int c={b}; int x[c]; const int *p=&a;
       return sizeof(x)==168 && *p==40 ? c : 1; }''',
    '''int main(void) { constexpr register int a=40; constexpr int b={{a+2}};
       static_assert(b==42); return b; }''',
    '''constexpr unsigned long long top=18446744073709551615ULL;
       constexpr long bottom=(-9223372036854775807L-1);
       static_assert(top>0 && bottom<0); int main(void) { return (top==~0ULL && bottom<0)?42:1; }''',
    '''constexpr _BitInt(8) a=40; constexpr unsigned _BitInt(16) b=42;
       static_assert(a+2==b); int main(void) { return a+2; }''',
    '''constexpr _Bool yes=1; constexpr _Bool no=0;
       int main(void) { return yes && !no ? 42 : 1; }''',
    '''constexpr int x=41; int main(void) { constexpr int x=42; return x; }''',
    '''constexpr int x=42; int main(void) { return _Generic(x, int: x, default: 1); }''',
    '''constexpr int x=40; int f(void) { static constexpr int y=x+2; return y; }
       int main(void) { return f(); }''',
    '''int main(void) { constexpr int n=21; struct S { unsigned x:n; } s={42};
       return s.x; }''',
    '''int main(void) { constexpr int n=42; for (constexpr int i=42; n==i;) return i; return 1; }''',
    '''constexpr int a=0 ? 1/0 : 42; static_assert(a==42); int main(void){return a;}''',
]
for t, v in [('signed char','-128'),('unsigned char','255'),('short','-32768'),
             ('unsigned short','65535'),('int','-2147483647-1'),('unsigned int','4294967295U'),
             ('long','-9223372036854775807L-1'),('unsigned long','18446744073709551615UL')]:
    programs.append(f'constexpr {t} x={v}; static_assert(x==({v})); int main(void) {{ const {t} *p=&x; return *p==({v})?42:1; }}')

negative = [
    ('constexpr auto x=x;', 'unavailable in its initializer'),
    ('constexpr auto x=sizeof(x);', 'unavailable in its initializer'),
    ('int x=1; int f(void){ static constexpr auto x=x; return x; }', 'unavailable in its initializer'),
    ('constexpr auto x={1};', 'requires an assignment initializer'),
    ('int f(void){ static constexpr auto x={1}; return 0; }', 'requires an assignment initializer'),
    ('constexpr auto x=1/0;', 'division by zero'),
    ('constexpr auto x=42,y=1;', 'multiple constexpr declarators'),
    ('constexpr volatile auto x=1;', 'requires a non-atomic'),
    ('int f(void){ static constexpr auto x=1; x=2; return x; }', 'modifiable'),
    ('constexpr int x;', 'requires an initializer'),
    ('int main(void){ constexpr int x; return 0; }', 'requires an initializer'),
    ('constexpr int x=x;', 'unavailable in its initializer'),
    ('constexpr int x=sizeof(x);', 'unavailable in its initializer'),
    ('int x=1; int f(void){ constexpr int x=sizeof(x); return 0; }', 'unavailable in its initializer'),
    ('int f(void){ static constexpr int x=x; return 0; }', 'unavailable in its initializer'),
    ('int f(void){ constexpr auto x=x; return 0; }', 'unavailable in its initializer'),
    ('constexpr unsigned char x=256;', 'not exactly representable'),
    ('constexpr signed char x=128;', 'not exactly representable'),
    ('constexpr unsigned x=-1;', 'not exactly representable'),
    ('constexpr _Bool x=2;', 'not exactly representable'),
    ('int f(void){ constexpr short x=32768; return 0; }', 'not exactly representable'),
    ('int f(void){ static constexpr unsigned char x=256; return 0; }', 'not exactly representable'),
    ('int f(void){ int x=2; constexpr int y=x; return y; }', 'integer constant expression'),
    ('constexpr int x=42; int f(void){ extern const int x; constexpr int y=x; return y; }', 'integer constant expression'),
    ('int f(void){ constexpr int x=1/0; return x; }', 'division by zero'),
    ('int f(void){ constexpr int x=1; x=2; return x; }', 'modifiable'),
    ('constexpr volatile int x=1;', 'requires a non-atomic'),
    ('constexpr _Atomic int x=1;', 'requires a non-atomic'),
    ('extern constexpr int x=1;', 'may combine only'),
    ('constexpr thread_local int x=1;', 'may combine only'),
    ('constexpr typedef int x;', 'may combine only'),
    ('constexpr int x=1,y=2;', 'multiple constexpr declarators'),
    ('int f(void){ constexpr int x=1,y=2; return 0; }', 'multiple constexpr declarators'),
    ('constexpr int f(void);', 'requires an object definition'),
    ('int f(constexpr int x);', 'not permitted'),
    ('int f(void){ constexpr volatile auto x=1; return 0; }', 'requires a non-atomic'),
    ('constexpr int x={1,2};', 'one initializer expression'),
]
with tempfile.TemporaryDirectory(prefix='kcc constexpr ') as tmp:
    d = Path(tmp); source=d/'test.c'; il=d/'test.ssa'; asm=d/'test.s'; exe=d/'test'
    def compile_text(text):
        source.write_text(text+'\n')
        return subprocess.run([str(kcc),str(source)],capture_output=True,text=True,timeout=15)
    for text in programs:
        result=compile_text(text)
        assert result.returncode==0 and not result.stderr, (text,result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=15)
            subprocess.run([host,str(asm),'-o',str(exe)],check=True,timeout=15)
            rc=subprocess.run([str(exe)],timeout=5).returncode
            assert rc==42,(text,rc)
    for text,message in negative:
        result=compile_text(text)
        assert result.returncode==1 and not result.stdout and message in result.stderr,(text,message,result.stderr)
    # Verify the address and value across a separately compiled native TU.
    if qbe:
        result=compile_text('constexpr auto global=42; const int *get(void) { static constexpr auto local=global; return &local; }')
        assert result.returncode==0,result.stderr
        il.write_text(result.stdout)
        subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=15)
        native=d/'native.c'
        native.write_text('const int *get(void); int main(void) { const int *a=get(), *b=get(); return a==b && *a==42 ? 42 : 1; }\n')
        subprocess.run([host,str(asm),str(native),'-o',str(exe)],check=True,timeout=15)
        assert subprocess.run([str(exe)],timeout=5).returncode==42
    # A file-scope constexpr definition must not export its name.
    result=compile_text('constexpr int unique_constexpr_name=42; int f(void){return unique_constexpr_name;}')
    assert result.returncode==0,result.stderr
    if qbe:
        il.write_text(result.stdout)
        subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=15)
        obj=d/'test.o'; subprocess.run([host,'-c',str(asm),'-o',str(obj)],check=True,timeout=15)
        symbols=subprocess.run(['nm','-g',str(obj)],capture_output=True,text=True,check=True).stdout
        assert 'unique_constexpr_name' not in symbols,symbols
print(f'constexpr integer: {len(programs)} executable cases, {len(negative)} refusals, linkage checked')

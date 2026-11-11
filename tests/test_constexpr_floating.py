"""Finite C23 constexpr floating scalars, exact conversions and named ICE casts."""
import os
import subprocess
import tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
kcc=Path(os.environ.get('KCC',root/'build'/'kcc'))
qbe=os.environ.get('QBE')
host=os.environ.get('HOST_CC','cc')
programs=[
    '''constexpr float a=1.5f; constexpr double b=a*2.0;
       constexpr auto c=b+39.0; static_assert((int)c==42); int table[(int)c];
       int main(void) { const double *p=&c; return sizeof(table)==168 && *p==42.0?42:1; }''',
    '''constexpr double a=21; constexpr float b=42.0; static_assert((int)b==42);
       int main(void) { static constexpr auto c=a+b; constexpr float d=(float)c;
       return d==63.0f?42:1; }''',
    '''constexpr float f=16777216; constexpr double d=9007199254740992ULL;
       constexpr double u=18446744073709551615ULL-2047ULL;
       int main(void) { return f==16777216.0f && d==9007199254740992.0 && u==18446744073709549568.0 ? 42:1; }''',
    '''constexpr float f=(float)16777217; constexpr float g=0.1f;
       int main(void){return f==16777216.0f && g>0.0f ? 42:1;}''',
    '''constexpr float f={}; constexpr double d={{}};
       int main(void) { return f==0.0f && d==0.0 ? 42:1; }''',
    '''constexpr auto a=1.0f/2.0f; constexpr double b=a; constexpr float c=0.5;
       int main(void) { static constexpr auto d=b+c; return d==1.0?42:1; }''',
    '''constexpr float f=-0.0f; constexpr double d=f; int main(void) {
       return 1.0 / d < 0.0 ? 42 : 1; }''',
    '''constexpr double d=3.75; int a[(int)d];
       int main(void) { constexpr auto e=d+0.25; static_assert((int)e==4); return sizeof(a)==12?42:1; }''',
    '''constexpr double x=42.0; int main(void) { constexpr double y=x; switch(42) {
       case (int)y: return 42; default: return 1; } }''',
    '''constexpr float x=(float)(1.0 / 3.0); constexpr float y=x+x;
       int main(void) { return y>0.66f && y<0.67f?42:1; }''',
    '''constexpr double x=(1.0<2.0)?42.0:0.0; constexpr auto y=x;
       int main(void) { return y==42.0?42:1; }''',
]
negative=[
    ('constexpr float x=0.1;', 'not exactly representable'),
    ('constexpr float x=1.0e100;', 'not exactly representable'),
    ('constexpr float x=0x1p-150;', 'not exactly representable'),
    ('constexpr float x=(float)1.0e100;', 'finite arithmetic constant'),
    ('constexpr float x=16777217;', 'not exactly representable'),
    ('constexpr double x=9007199254740993ULL;', 'not exactly representable'),
    ('constexpr float x=18446744073709551615ULL;', 'not exactly representable'),
    ('constexpr float x=1.0/0.0;', 'finite arithmetic constant'),
    ('double x=1.0; constexpr double y=x;', 'finite arithmetic constant'),
    ('constexpr float x=x;', 'unavailable in its initializer'),
    ('int f(void){ constexpr double x=sizeof(x); return 0; }', 'unavailable in its initializer'),
    ('int f(void){ constexpr float x=1.0f; x=2.0f; return 0; }', 'modifiable'),
    ('constexpr volatile float x=1.0f;', 'requires a non-atomic'),
    ('constexpr float x=0 ? 1.0f : 0.1;', 'not exactly representable'),
    ('constexpr double x=1.0; static_assert(x==1.0);', 'integer constant'),
    ('constexpr double x=2.0; static_assert((int)(x+1.0)==3);', 'integer constant'),
    ('int x; constexpr float f=&x ? 1.0f : 2.0f;', 'finite arithmetic constant'),
]
with tempfile.TemporaryDirectory(prefix='kcc constexpr floating ') as tmp:
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
    for text,message in negative:
        result=compile_text(text)
        assert result.returncode==1 and not result.stdout and message in result.stderr,(text,message,result.stderr)
    if qbe:
        result=compile_text('constexpr auto x=42.0; double get(void){ static constexpr auto y=x; return y; }')
        assert result.returncode==0,result.stderr
        il.write_text(result.stdout)
        subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=15)
        native=d/'native.c'; native.write_text('double get(void); int main(void){return get()==42.0?42:1;}\n')
        subprocess.run([host,str(asm),str(native),'-o',str(exe)],check=True,timeout=15)
        assert subprocess.run([str(exe)],timeout=5).returncode==42
print(f'constexpr floating: {len(programs)} runtime cases, {len(negative)} refusals and native float ABI')

"""C23 function-name static object, scope, identity and initialization."""
import os
import subprocess
import tempfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
compiler=Path(os.environ.get('KCC',root/'build/kcc'))
qbe=os.environ.get('QBE')
host=os.environ.get('HOST_CC','cc')
programs=[r'''
const char *other(void) { return __func__; }
int main(void) {
 const char *p=__func__; const char *q=__func__;
 return p==q && sizeof __func__==5 && p[0]=='m' && p[3]=='n' &&
 p[4]==0 && other()[0]=='o' && p!=other() ? 42 : 1;
}''',r'''
const char *fun(void) { static const char *p=__func__; return p; }
int main(void) { return fun()==fun() && fun()[0]=='f' && fun()[2]=='n' && fun()[3]==0 ? 42 : 1; }
''',r'''
typedef int __func__;
int abc(void) { static_assert(sizeof __func__ == 4); return __func__[0]=='a'; }
int main(void) { return abc() && sizeof __func__==5 ? 42 : 1; }
''',r'''
int __func__=17;
int f(void) { return __func__[0]=='f'; }
int main(void) { return f() && __func__[0]=='m' ? 42 : 1; }
''',r'''
int f(void) {
 const char *outer=__func__;
 { int __func__=4; if(__func__!=4) return 1; }
 { typedef int __func__; __func__ a=7; if(a!=7 || sizeof(__func__)!=4) return 2; }
 { enum { __func__=9 }; if(__func__!=9)return 3; }
 return outer==__func__ && __func__[0]=='f' ? 42 : 4;
}
int main(void){return f();}
''',r'''
#define F __func__
int f(void) { const char (*p)[sizeof F]=&F; return (*p)[0]=='f' && (*p)[1]==0; }
int main(void){return f()?42:1;}
''',r'''
int call(int x) { return x ? call(x-1) : __func__[4]==0; }
int main(void) { return call(10) ? 42 : 1; }
''']
invalid=[
"int f(void) { __func__[0]='x'; return 0; }",
'int f(int __func__){return 0;}',
'int f(void){int __func__=3;return 0;}',
'int f(void){static int __func__;return 0;}',
'int f(void){extern int __func__;return 0;}',
'int f(void){typedef int __func__;return 0;}',
'int f(void){enum {__func__=3};return 0;}',
'int f(void){return sizeof __func__; } int g(void){__func__[0]=0;return 0;}',
]
with tempfile.TemporaryDirectory(prefix='kcc function name ') as tmp:
    d=Path(tmp); source=d/'test.c'; il=d/'test.ssa'; asm=d/'test.s'; exe=d/'test'
    for index,program in enumerate(programs):
        source.write_text(program)
        result=subprocess.run([str(compiler),str(source)],capture_output=True,text=True,timeout=20)
        assert result.returncode==0 and not result.stderr,(index,result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=20)
            subprocess.run([host,str(asm),'-o',str(exe)],check=True,timeout=20)
            assert subprocess.run([str(exe)],timeout=10).returncode==42,index
    for index,program in enumerate(invalid):
        source.write_text(program)
        result=subprocess.run([str(compiler),str(source)],capture_output=True,text=True,timeout=20)
        assert result.returncode!=0 and result.stderr and not result.stdout,(index,result.stderr)
print('function-name binding: static identity, constant initialization, typedef/object/enum shadowing and same-scope conflicts; '+('QBE/runtime passed' if qbe else 'runtime not run'))

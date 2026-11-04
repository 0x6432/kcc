"""Bounded float types, exact literals, scalar ABI and explicit rejections."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
kcc = root / 'build/kcc'
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')

def compile_text(text):
    source.write_text(text)
    return subprocess.run([str(kcc), str(source)], text=True, capture_output=True, timeout=10)

impl = '''
_Static_assert(sizeof(float)==4, "float");
_Static_assert(sizeof(double)==8, "double");
_Static_assert(alignof(float)==4, "float alignment");
_Static_assert(alignof(double)==8, "double alignment");
typedef const float CF;
float add(float a, float b) { CF x = a; return x+b; }
double prod(double a, double b) { return a*b; }
float literal(void) { return 0x1.8p+1f; }
double dlit(void) { return .125e1; }
double f(void) { return (double){1.5}; }
int unequal(double x,double y) { return x!=y; }
float neg(float x) { return -x; }
int truth(double x) { return !x || (x && x==x); }
float choose(int x, float a, float b) { return x ? a : b; }
float pass(float (*fn)(float, float), float x, float y) { return fn(x,y); }
double widen(float x) { return x; }
float narrow(double x) { return x; }
double mixed(float x, int y) { return x+y; }
long to_long(double x) { return (long)x; }
_Bool as_bool(double x) { return x; }
float update(float *p) { float old=(*p)++; *p += 1.5; return old+*p; }
int compound_int(int x) { x += 1.5; return x; }
double stack(int a, double b, int c, double d, int e, double f, int g, double h, int i, double j, double k, double l, double m, double n) { return b+d+f+h+j+k+l+m+n; }
'''
harness = '''
#include <math.h>
float add(float,float); double prod(double,double); float literal(void); double dlit(void);
double f(void); int unequal(double,double); float neg(float); int truth(double); float choose(int,float,float);
float pass(float (*)(float,float),float,float);
double widen(float); float narrow(double); double mixed(float,int); long to_long(double); _Bool as_bool(double);
float update(float *); int compound_int(int);
double stack(int,double,int,double,int,double,int,double,int,double,double,double,double,double);
int main(void) {
 if (add(1.25f,2.5f)!=3.75f || prod(1.5,4.0)!=6.0 || literal()!=3.0f || dlit()!=1.25 || f()!=1.5) return 1;
 if (!signbit(neg(0.0f)) || signbit(neg(-0.0f))) return 2;
 if (!truth(0.0) || !truth(2.0) || truth(NAN) || !unequal(NAN, 1.0)) return 3;
 if (choose(1,3.0f,5.0f)!=3.0f || pass(add,1.0f,2.0f)!=3.0f) return 4;
 if (stack(1,1.0,2,2.0,3,3.0,4,4.0,5,5.0,6.0,7.0,8.0,9.0)!=45.0) return 5;
 if (widen(2.25f)!=2.25 || narrow(2.25)!=2.25f || mixed(1.5f,2)!=3.5) return 6;
 if (to_long(-3.5)!=-3 || as_bool(0.0) || !as_bool(1.0)) return 7;
 { float x=1.0f; if (update(&x)!=4.5f || x!=3.5f || compound_int(1)!=2) return 8; }
 return 0;
}
'''
# Reverse the call direction; kcc uses only the supported same-type subset.
reverse = '''
float hf(float, float); double hd(double, double); float host_zero(void);
int main(void) {
 float x=hf(1.25f,2.0f); double y=hd(1.5,2.0);
 if (x!=3.25f || y!=3.5) return 1;
 if (host_zero()) return 2;
 return 0;
}
'''
hostimpl = 'float hf(float x,float y){return x+y;} double hd(double x,double y){return x+y;} float host_zero(void){return -0.0f;}'
reject = [
 'long double x;', 'unsigned float x;', 'double double x;', 'float long x;',
 'float f(float x){return x%=1;}', 'int f(int x){return x&=1.0;}',
 'float f(void){return 1.0L;}',
 'float f(void){return 1e9999f;}', 'float f(void){return 1e-9999f;}',
 'float f(void){return 1\'2.0f;}', 'double x=1.0;',
 'struct X {double x;}; struct X x={1.0};',
 'int x[1.0];', '#if 1.0\nint x;\n#endif\n',
]
with tempfile.TemporaryDirectory(prefix='kcc-float-') as directory:
    d = Path(directory)
    source = d/'test.c'
    for text, hosttext in [(impl, harness), (reverse, hostimpl)]:
        result = compile_text(text)
        assert result.returncode == 0 and not result.stderr, result.stderr
        if qbe:
            (d/'test.ssa').write_text(result.stdout)
            (d/'host.c').write_text(hosttext)
            subprocess.run([qbe,'-t','amd64_sysv','-o',str(d/'test.s'),str(d/'test.ssa')], check=True, timeout=10)
            subprocess.run([host,'-std=c11',str(d/'test.s'),str(d/'host.c'),'-o',str(d/'test')], check=True, timeout=10)
            subprocess.run([str(d/'test')], check=True, timeout=10)
    for text in reject:
        result = compile_text(text)
        assert result.returncode != 0 and result.stderr, (text, result.stdout, result.stderr)
print('floating foundation: ' + ('ABI runtime passed' if qbe else 'IL and rejection checks passed; QBE runtime unavailable'))

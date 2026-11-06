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
double global_float=1.5;
float global_negzero=-0.0f;
float global_subnormal=0x1p-149f;
double global_subnormal_double=0x1p-1074;
float global_narrow=42.0;
double global_widen=42.0f;
float global_integer=42;
double global_unsigned=18446744073709551615UL;
double global_signed=(-9223372036854775807L-1L);
signed char low_char=-128.5; short low_short=-32768.5; int low_int=-2147483648.5;
float global_arithmetic=1.5f+2.25f;
double global_mixed=2.5*4-1.0;
int static_int=4.75-10.0;
long static_cast=(int)(1.25-4.75);
unsigned long static_unsigned_cast=(int)(1.25-4.75);
unsigned int static_unsigned=-0.75;
_Bool static_bool=-0.0;
struct StaticInts { int a; unsigned int b; _Bool c; };
struct StaticInts static_ints={2.75+3.5, 42.9, 1.5};
struct Holder { double x; float y; };
struct Holder global_holder={-2.5, 3.0f};
float add(float a, float b) { CF x = a; return x+b; }
double prod(double a, double b) { return a*b; }
float literal(void) { return 0x1.8'0p+1f; }
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
extern double global_float; extern float global_negzero;
extern float global_subnormal; extern double global_subnormal_double;
extern float global_narrow, global_integer; extern double global_widen, global_unsigned, global_signed;
extern float global_arithmetic; extern double global_mixed;
extern signed char low_char; extern short low_short; extern int low_int;
extern int static_int; extern unsigned int static_unsigned; extern _Bool static_bool;
extern long static_cast; extern unsigned long static_unsigned_cast;
struct StaticInts { int a; unsigned int b; _Bool c; }; extern struct StaticInts static_ints;
struct Holder { double x; float y; }; extern struct Holder global_holder;
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
 if (low_char!=-128 || low_short!=-32768 || low_int!=(-2147483647-1)) return 15;
 if (global_float!=1.5 || !signbit(global_negzero) || global_holder.x!=-2.5 || global_holder.y!=3.0f) return 9;
 if (global_subnormal!=0x1p-149f || global_subnormal_double!=0x1p-1074) return 13;
 if (global_narrow!=42.0f || global_widen!=42.0 || global_integer!=42.0f ||
     global_unsigned!=(double)18446744073709551615UL || global_signed!=(double)(-9223372036854775807L-1L)) return 10;
 if (global_arithmetic!=3.75f || global_mixed!=9.0) return 11;
 if (static_int!=-5 || static_cast!=-3 || static_unsigned_cast!=(unsigned long)-3 || static_unsigned!=0 || static_bool ||
     static_ints.a!=6 || static_ints.b!=42 || !static_ints.c) return 12;
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
 'signed char too_low=-129.0;', 'short too_low=-32769.0;',
 'float f(void){return 1.0L;}',
 'float f(void){return 1e9999f;}', 'float f(void){return 1e-9999f;}',
 'float f(void){return 1.0e1\'f;}', 'double x=1.0/0.0;',
 'int x[1.0];', '#if 1.0\nint x;\n#endif\n',
 'int x=2147483648.0;', 'unsigned x=-1.0;', 'int x=1.0/0.0;',
 'int x=(int)(1.0/0.0);',
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

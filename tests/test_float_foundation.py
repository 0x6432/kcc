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
float global_tiny=0x1p-150f;
float global_tiny_above=0x1.000002p-150f;
double global_tiny_double=0x1p-1075;
double global_tiny_double_above=0x1.0000000000001p-1075;
double global_subnormal_double=0x1p-1074;
float global_narrow=42.0;
double global_widen=42.0f;
float global_integer=42;
double global_unsigned=18446744073709551615UL;
double global_signed=(-9223372036854775807L-1L);
signed char low_char=-128.5; short low_short=-32768.5; int low_int=-2147483648.5;
float global_arithmetic=1.5f+2.25f;
float global_choice=0 ? 1.5f : 2.25f;
double global_choice_mixed=1 ? 2.5 : 3;
float global_float_condition=-0.0 ? 10.0f : 11.0f;
double global_compare_condition=(1.0f + 2 > 2.5) ? 12.0 : 13.0;
float global_not_condition=!0.0 ? 14.0f : 15.0f;
int global_choice_int=1 ? 42.75 : 3.0;
int global_float_compare=1.0f < 2.0;
int global_comparison_arithmetic=((1.0<2.0)+2)*3;
float global_comparison_arithmetic_float=(1.0<2.0)+2;
int global_conditional_arithmetic=1.0 ? (1.0<2.0)+4 : 1/0;
int global_nested_float_cast=(int)(1.0+2.75)+2;
int global_cast_condition=((int)(1.0+2.0)>2) ? 11 : 12;
int global_cast_short_circuit=((int)(2.0+1.0)) || ((int)(1.0/0.0));
int global_integer_choice=1.0 ? -5 : 6;
int global_nested_choice=(1.0 ? 0 : 1) ? 10 : 11;
int global_nested_logic=!(1.0 ? 0 : 1);
double skipped_float=1 ? 2.0 : 1.0/0.0;
float skipped_nested=1.0 ? -0.0f : (float)(1.0 / 0.0);
int skipped_int=1.0 ? 3 : 1/0;
int skipped_or=1.0 || 1.0/0.0;
int skipped_and=0.0 && 1.0/0.0;
float global_nested_float=(1.0 ? 2 : 3) ? 9.0f : 8.0f;
unsigned long global_unsigned_choice=0.0 ? 5 : -1;
float global_integer_choice_float=(2.0 > 1.0) ? 9 : 4;
int global_float_logic=(1.0 && 2) || !3.0;
float global_float_logic_value=!(0.0 || 0);
double global_float_logic_choice=(0.0 || 3) ? 9.0 : 2.0;
_Bool global_float_not=!0.0;
float global_compare_as_float=1.0 == 1.0;
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
extern float global_subnormal, global_tiny, global_tiny_above; extern double global_subnormal_double, global_tiny_double, global_tiny_double_above;
extern float global_narrow, global_integer; extern double global_widen, global_unsigned, global_signed;
extern int global_nested_choice, global_nested_logic; extern float global_nested_float;
extern double skipped_float; extern float skipped_nested; extern int skipped_int, skipped_or, skipped_and;
extern int global_comparison_arithmetic, global_conditional_arithmetic; extern float global_comparison_arithmetic_float;
extern int global_nested_float_cast, global_cast_condition, global_cast_short_circuit;
extern int global_integer_choice; extern unsigned long global_unsigned_choice; extern float global_integer_choice_float;
extern int global_float_logic; extern float global_float_logic_value; extern double global_float_logic_choice;
extern float global_arithmetic, global_choice, global_float_condition, global_not_condition; extern double global_mixed, global_choice_mixed, global_compare_condition; extern int global_choice_int, global_float_compare; extern _Bool global_float_not; extern float global_compare_as_float;
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
 if (global_tiny!=0.0f || global_tiny_double!=0.0 ||
     global_tiny_above!=0x1p-149f || global_tiny_double_above!=0x1p-1074) return 12;
 if (global_float!=1.5 || !signbit(global_negzero) || global_holder.x!=-2.5 || global_holder.y!=3.0f) return 9;
 if (global_subnormal!=0x1p-149f || global_subnormal_double!=0x1p-1074) return 13;
 if (global_narrow!=42.0f || global_widen!=42.0 || global_integer!=42.0f ||
     global_unsigned!=(double)18446744073709551615UL || global_signed!=(double)(-9223372036854775807L-1L)) return 10;
 if (global_arithmetic!=3.75f || global_mixed!=9.0 || global_choice!=2.25f || global_choice_mixed!=2.5 || global_choice_int!=42 ||
     global_nested_choice!=11 || global_nested_logic!=1 || global_nested_float!=9.0f ||
     global_integer_choice!=-5 || global_unsigned_choice!=(unsigned long)-1 || global_integer_choice_float!=9.0f ||
     global_float_logic!=1 || global_float_logic_value!=1.0f || global_float_logic_choice!=9.0 ||
     global_float_condition!=11.0f || global_compare_condition!=12.0 || global_not_condition!=14.0f || global_float_compare!=1 || !global_float_not ||
     global_compare_as_float!=1.0f) return 11;
 if (global_nested_float_cast!=5 || global_cast_condition!=11 || global_cast_short_circuit!=1) return 18;
 if (global_comparison_arithmetic!=9 || global_comparison_arithmetic_float!=3.0f || global_conditional_arithmetic!=5) return 17;
 if (skipped_float!=2.0 || !signbit(skipped_nested) || skipped_int!=3 || skipped_or!=1 || skipped_and!=0) return 16;
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
 'int n; int x=1.0 ? 1 : n;', 'int x=0.0 ? 1 : 1/0;',
 'static_assert(1.0 ? 1 : 0);',
 'int a=0.0 || (1.0/0.0);', 'int a=1.0 && (1.0/0.0);',
 'int x; int a=1.0 && x;', 'static_assert(1.0 && 1);',
 'int a[(1.0 && 1) ? 1 : 2];',
 'int n; double x=n?1.0:2.0;', 'double x=0?2.0:1.0/0.0;',
 'double z; double x=z?1.0:2.0;', 'double x=(1.0/0.0)?1.0:2.0;',
 'int a[(1.0<2.0)?1:2];', 'int a[1.0<2.0];',
 'double x; int a=x<1.0;', 'int a=(1.0/0.0)<2.0;',
 'int a=(1.0<2.0)+2147483647;', 'int a=(1.0<2.0)/(2.0<1.0);',
 'int x=(int)(2147483648.0+1.0)+1;', 'int x=(int)(1.0/0.0)+1;',
 'int a[(int)(1?2.0:3.0)];',
 'long double x;', 'unsigned float x;', 'double double x;', 'float long x;',
 'float f(float x){return x%=1;}', 'int f(int x){return x&=1.0;}',
 'signed char too_low=-129.0;', 'short too_low=-32769.0;',
 'float f(void){return 1.0L;}',
 'float f(void){return 1e9999f;}',
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

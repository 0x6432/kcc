"""Bounded compiler-provided headers for the amd64 SysV target."""
import os
import subprocess
import tempfile
from pathlib import Path

compiler = Path(__file__).resolve().parents[1] / "build" / "kcc"
qbe = os.environ.get("QBE")
host = os.environ.get("HOST_CC", "cc")

source_text = r"""
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdint.h>
#include <limits.h>
#include <float.h>
#include <stdnoreturn.h>
noreturn void fatal(void) { for(;;) {} }
#if !defined(__DATE__) || !defined(__TIME__)
#error missing translation clock macros
#endif
#if !defined(__has_c_attribute)
#error missing attribute query operator
#endif
#if __has_c_attribute(maybe_unused) || __has_c_attribute(example::unknown)
#error incomplete attributes must not be advertised
#endif
static_assert(sizeof(__DATE__)==12 && sizeof(__TIME__)==9);
static_assert(sizeof(size_t)==8 && sizeof(ptrdiff_t)==8);
static_assert(alignof(max_align_t)==16 && sizeof(max_align_t)==32);
static_assert(sizeof(int8_t)==1 && sizeof(uint16_t)==2);
static_assert(sizeof(int32_t)==4 && sizeof(uint64_t)==8);
static_assert(INT8_MIN == -128 && UINT32_MAX == 4294967295U);
static_assert(CHAR_BIT==8 && CHAR_MIN == -128 && INT_WIDTH==32 && LONG_WIDTH==64);
static_assert(sizeof(int_least16_t)==2 && sizeof(int_fast32_t)==8);
static_assert(INT64_C(42)==42L && UINT32_C(42)==42U && UINT_FAST32_MAX==UINT64_MAX);
static_assert(FLT_RADIX==2 && FLT_MANT_DIG==24 && DBL_MANT_DIG==53);
struct I { char c; int n; }; struct O { char c; struct I a[2]; };
static_assert(offsetof(struct O,a[1].n)==16);
int main(void) {
    nullptr_t n=nullptr;
    bool b=true;
    uint64_t x=42;
    int *p=NULL;
    return b && p==n && x==42 && __bool_true_false_are_defined ? (int)x : 1;
}
"""
with tempfile.TemporaryDirectory(prefix="kcc-headers-") as directory:
    path = Path(directory)
    source = path / "test.c"
    source.write_text(source_text)
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    if qbe:
        il, asm, exe = [path / name for name in ("out.ssa", "out.s", "out")]
        il.write_text(result.stdout)
        subprocess.run([qbe, "-t", "amd64_sysv", "-o", str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), "-o", str(exe)], check=True)
        assert subprocess.run([str(exe)]).returncode == 42
    (path / "present.h").write_text("#define PRESENT 1\n")
    (path / "defined.h").write_text("/* header named like a conditional operator */\n")
    (path / "__VA_ARGS__.h").write_text("/* header named like a variadic token */\n")
    source.write_text(r'''
#define HEADER "present.h"
#define present nonexistent
#if !defined(__has_include)
#error missing query operator
#endif
#if !__has_include("present.h") || !__has_include(HEADER)
#error quoted header query failed
#endif
#if !__has_include(<present.h>) || !__has_include(<stddef.h>) || !__has_include(<defined.h>) || !__has_include(<__VA_ARGS__.h>)
#error angle header query failed
#endif
#if __has_include("missing.h") || __has_include(<missing.h>)
#error nonexistent header was found
#endif
int main(void) { return 0; }
''')
    result = subprocess.run([str(compiler), "-I", str(path), str(source)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    source.write_text('#if __has_include("")\n#endif\n')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True)
    assert result.returncode != 0, "empty header names must be rejected"
    (path / "stdint.h").write_text("#define PROVIDED 42\n")
    source.write_text("#include <stdint.h>\nint main(void){return PROVIDED;}\n")
    result = subprocess.run([str(compiler), "-I", str(path), str(source)], capture_output=True, text=True)
    assert result.returncode == 0 and "copy 42" in result.stdout, result.stderr
    source.write_text(r'''
#include <assert.h>
int main(void) {
  int x=40;
  assert(++x==41);
#define NDEBUG
#include <assert.h>
  assert(++x==0);
#undef NDEBUG
#include <assert.h>
  assert(++x==42);
  return x;
}
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    if qbe:
        il.write_text(result.stdout)
        subprocess.run([qbe, "-t", "amd64_sysv", "-o", str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), "-o", str(exe)], check=True)
        assert subprocess.run([str(exe)]).returncode == 42
    source.write_text(r'''
int main(void) {
  return __DATE__[0]=='J' && __DATE__[4]==' ' && __DATE__[5]=='1' &&
    __DATE__[7]=='1' && __DATE__[8]=='9' && __DATE__[9]=='7' &&
    __DATE__[10]=='0' && __TIME__[0]=='0' && __TIME__[7]=='0' ? 42 : 1;
}
''')
    env = dict(os.environ, SOURCE_DATE_EPOCH='0')
    result = subprocess.run([str(compiler), str(source)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    if qbe:
        il.write_text(result.stdout)
        subprocess.run([qbe, "-t", "amd64_sysv", "-o", str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), "-o", str(exe)], check=True)
        assert subprocess.run([str(exe)]).returncode == 42
    env['SOURCE_DATE_EPOCH'] = 'not-a-timestamp'
    result = subprocess.run([str(compiler), str(source)], env=env, capture_output=True, text=True)
    assert result.returncode != 0 and 'invalid SOURCE_DATE_EPOCH' in result.stderr
    source.write_text(r'''
#include <time.h>
static_assert(sizeof(time_t)==8 && sizeof(struct tm)==56 && sizeof(struct timespec)==16);
int main(void) {
  time_t epoch=0;
  struct tm *p=gmtime(&epoch);
  struct timespec ts;
  return p && p->tm_year==70 && p->tm_mon==0 && p->tm_mday==1 &&
    timespec_get(&ts,TIME_UTC)==TIME_UTC && ts.tv_nsec>=0 && ts.tv_nsec<1000000000L ? 42 : 1;
}
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    if qbe:
        il.write_text(result.stdout)
        subprocess.run([qbe, "-t", "amd64_sysv", "-o", str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), "-o", str(exe)], check=True)
        assert subprocess.run([str(exe)]).returncode == 42
    source.write_text(r'''
#include <math.h>
#include <stdlib.h>
int main(void) {
  double x=strtod("nan",NULL);
  float y=-0.0f;
  return isnan(x) && !isfinite(x) && signbit(y) && sqrt(4.0)==2.0 ? 42 : 1;
}
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    if qbe:
        il.write_text(result.stdout)
        subprocess.run([qbe, "-t", "amd64_sysv", "-o", str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), "-lm", "-o", str(exe)], check=True)
        assert subprocess.run([str(exe)]).returncode == 42
    source.write_text(r'''
#include <tgmath.h>
static_assert(sizeof(sqrt(4.0f))==sizeof(float));
static_assert(sizeof(sqrt(4.0))==sizeof(double));
static_assert(sizeof(sqrt(4))==sizeof(double));
static_assert(sizeof(pow(4.0f,2.0f))==sizeof(float));
static_assert(sizeof(pow(4.0f,2))==sizeof(double));
static_assert(sizeof(pow(4,2.0f))==sizeof(double));
int main(void) {
  int n=4;
  float f=4.0f;
  return sqrt(n++)==2.0 && n==5 && sqrt(f)==2.0f && pow(f,2)==16.0 ? 42 : 1;
}
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    if qbe:
        il.write_text(result.stdout)
        subprocess.run([qbe, "-t", "amd64_sysv", "-o", str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), "-lm", "-o", str(exe)], check=True)
        assert subprocess.run([str(exe)]).returncode == 42
    source.write_text(r'''
#include <stdio.h>
#include <errno.h>
#include <ctype.h>
#include <inttypes.h>
int main(void) {
  char buf[8];
  errno=0;
  int n=snprintf(buf,sizeof buf,"%" PRId64,(int64_t)42);
  return n==2 && isdigit(buf[0]) && buf[1]=='2' && errno==0 ? 42 : 1;
}
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    if qbe:
        il.write_text(result.stdout)
        subprocess.run([qbe, "-t", "amd64_sysv", "-o", str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), "-o", str(exe)], check=True)
        assert subprocess.run([str(exe)]).returncode == 42
    source.write_text(r'''
#include <stdio.h>
#include <inttypes.h>
int main(void) {
  char buf[64]; int8_t a=0; uint16_t b=0; int_fast32_t c=0;
  int n=snprintf(buf,sizeof buf,"%" PRIdLEAST8 " %" PRIuLEAST16 " %" PRIdFAST32,
                 (int_least8_t)-3,(uint_least16_t)21,(int_fast32_t)42);
  int fields=sscanf(buf,"%" SCNd8 " %" SCNu16 " %" SCNdFAST32,&a,&b,&c);
  return n==8 && fields==3 && a==-3 && b==21 && c==42 ? 42 : 1;
}
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    if qbe:
        il.write_text(result.stdout)
        subprocess.run([qbe, "-t", "amd64_sysv", "-o", str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), "-o", str(exe)], check=True)
        assert subprocess.run([str(exe)]).returncode == 42
    source.write_text(r'''
#include <wchar.h>
#include <uchar.h>
static_assert(sizeof(wchar_t)==4 && sizeof(wint_t)==4 && sizeof(mbstate_t)==8);
int main(void) {
  wchar_t a[3]={65,66,0}, b[3]={0}; char out[8]; mbstate_t state={0};
  wchar_t ch=0;
  if (wcslen(a)!=2 || wcscpy(b,a)!=b || wcscmp(a,b)!=0 || wcschr(b,66)!=b+1) return 1;
  if (mbrtowc(&ch,"A",1,&state)!=1 || ch!=65 || wcrtomb(out,ch,&state)!=1 || out[0]!=65) return 2;
  return 42;
}
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    if qbe:
        il.write_text(result.stdout)
        subprocess.run([qbe, "-t", "amd64_sysv", "-o", str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), "-o", str(exe)], check=True)
        assert subprocess.run([str(exe)]).returncode == 42
    source.write_text(r'''
#include <stdatomic.h>
atomic_int x=ATOMIC_VAR_INIT(0);
atomic_flag flag=ATOMIC_FLAG_INIT;
int main(void) {
  atomic_init(&x,40);
  memory_order order=memory_order_relaxed;
  int lock_free=atomic_is_lock_free(&x);
  int prior=atomic_fetch_add_explicit(&x,2,order);
  int old=atomic_exchange(&x,42);
  int expected=42, missing=40;
  _Bool success=atomic_compare_exchange_weak_explicit(&x,&expected,41,memory_order_acq_rel,memory_order_acquire);
  _Bool failure=atomic_compare_exchange_strong(&x,&missing,50);
  atomic_thread_fence(memory_order_seq_cst);
  atomic_signal_fence(memory_order_acquire);
  _Bool first=atomic_flag_test_and_set_explicit(&flag,memory_order_acquire);
  _Bool second=atomic_flag_test_and_set(&flag);
  atomic_flag_clear_explicit(&flag,memory_order_release);
  _Bool third=atomic_flag_test_and_set(&flag);
  atomic_flag_clear(&flag);
  atomic_store_explicit(&x,42,memory_order_release);
  return lock_free && prior==40 && old==42 && success && !failure && missing==41 && !first && second && !third
    ? atomic_load_explicit(&x,memory_order_acquire) : 1;
}
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    if qbe:
        il.write_text(result.stdout)
        subprocess.run([qbe, "-t", "amd64_sysv", "-o", str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), "-latomic", "-o", str(exe)], check=True)
        assert subprocess.run([str(exe)]).returncode == 42
    source.write_text(r'''
#include <stdlib.h>
#include <string.h>
int main(void) {
  char *p=malloc(4);
  if (!p) return EXIT_FAILURE;
  memcpy(p,"42",3);
  int value=atoi(p);
  size_t n=strlen(p);
  free(p);
  return n==2 ? value : 1;
}
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    if qbe:
        il.write_text(result.stdout)
        subprocess.run([qbe, "-t", "amd64_sysv", "-o", str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), "-o", str(exe)], check=True)
        assert subprocess.run([str(exe)]).returncode == 42
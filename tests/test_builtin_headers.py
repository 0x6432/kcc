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
#include <stdatomic.h>
atomic_int x=ATOMIC_VAR_INIT(0);
int main(void) {
  atomic_init(&x,40);
  memory_order order=memory_order_relaxed;
  int prior=atomic_fetch_add_explicit(&x,2,order);
  int old=atomic_exchange(&x,42);
  return prior==40 && old==42 ? atomic_load(&x) : 1;
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
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
static_assert(sizeof(size_t)==8 && sizeof(ptrdiff_t)==8);
static_assert(sizeof(int8_t)==1 && sizeof(uint16_t)==2);
static_assert(sizeof(int32_t)==4 && sizeof(uint64_t)==8);
static_assert(INT8_MIN == -128 && UINT32_MAX == 4294967295U);
static_assert(CHAR_BIT==8 && CHAR_MIN == -128 && INT_WIDTH==32 && LONG_WIDTH==64);
static_assert(sizeof(int_least16_t)==2 && sizeof(int_fast32_t)==8);
static_assert(INT64_C(42)==42L && UINT32_C(42)==42U && UINT_FAST32_MAX==UINT64_MAX);
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
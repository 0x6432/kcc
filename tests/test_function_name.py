"""Function-name identifier: one static const array per function."""
import os
import subprocess
import tempfile
from pathlib import Path

compiler = Path(__file__).resolve().parents[1] / "build" / "kcc"
qbe = os.environ.get("QBE")
host = os.environ.get("HOST_CC", "cc")
program = r'''
const char *other(void) { return __func__; }
int main(void) {
  const char *p=__func__;
  const char *q=__func__;
  return p==q && sizeof __func__==5 && p[0]=='m' && p[3]=='n' &&
         p[4]==0 && other()[0]=='o' && p!=other() ? 42 : 1;
}
'''
with tempfile.TemporaryDirectory(prefix="kcc-func-") as directory:
    base = Path(directory)
    source = base / "test.c"
    source.write_text(program)
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    if qbe:
        il, asm, exe = [base / name for name in ("out.ssa", "out.s", "out")]
        il.write_text(result.stdout)
        subprocess.run([qbe, "-t", "amd64_sysv", "-o", str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), "-o", str(exe)], check=True)
        assert subprocess.run([str(exe)]).returncode == 42
    source.write_text("int f(void) { __func__[0]='x'; return 0; }\n")
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True)
    assert result.returncode != 0 and not result.stdout
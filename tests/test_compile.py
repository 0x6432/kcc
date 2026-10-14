"""Curated compiler rejection, IL and optional QBE/runtime tests."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root / "build" / "kcc"
qbe = os.environ.get("QBE")

with tempfile.TemporaryDirectory(prefix="kcc-test-") as directory:
    directory = Path(directory)
    source = directory / "input with spaces.c"
    for value in (0, 42, 255, 2147483647):
        source.write_text(f"int main(void) {{ return {value}; }}\n")
        result = subprocess.run([str(compiler), str(source)],
                                capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, result.stderr
        assert "export function w $main()" in result.stdout
        assert f"ret {value}" in result.stdout
        if qbe:
            il = directory / "program.ssa"
            assembly = directory / "program.s"
            executable = directory / "program"
            il.write_text(result.stdout)
            subprocess.run([qbe, "-t", "amd64_sysv", "-o", str(assembly), str(il)],
                           check=True, timeout=10)
            subprocess.run([os.environ.get("HOST_CC", "cc"), str(assembly),
                            "-o", str(executable)], check=True, timeout=10)
            result = subprocess.run([str(executable)], timeout=5)
            assert result.returncode == value % 256

    invalid = [
        "", "int main(void) { return; }", "int main(void) { return 0 }",
        "int main(void) { return 2147483648; }",
        "int main(void) { return 0x10; }", "int main(void) { return 0; } int x;",
        "int other(void) { return 0; }", "int main() { return 0; }",
        "int main(void) { return 1 + 2; }", "#define X 0\n",
        "int main(void) { return 0; }\0",
    ]
    for text in invalid:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)],
                                capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and "error:" in result.stderr, text
        assert not result.stdout, (text, result.stdout)
print("Compiler IL and rejection tests passed" + ("; QBE/runtime passed" if qbe else ""))

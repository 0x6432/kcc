"""Curated compiler rejection, IL and optional QBE/runtime tests."""
import os
import random
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root / "build" / "kcc"
qbe = os.environ.get("QBE")

with tempfile.TemporaryDirectory(prefix="kcc-test-") as directory:
    directory = Path(directory)
    source = directory / "input with spaces.c"
    cases = [(str(value), value) for value in (0, 42, 255, 2147483647)]
    cases += [
        ("2 + 3 * 4", 14), ("(2 + 3) * 4", 20), ("20 - 3 - 2", 15),
        ("24 / 3 / 2", 4), ("20 % 6", 2), ("-7 / 3", -2),
        ("-7 % 3", -1), ("+ + 7", 7), ("- - 7", 7),
        ("-(2 + 3) * 4", -20), ("2 * -3 + 10", 4), ("-2147483647 - 1", -2147483648),
    ]
    random_source = random.Random(42)
    for _ in range(16):
        a, b, c = [random_source.randrange(100) for _ in range(3)]
        cases.append((f"({a} - {b}) * {c}", (a - b) * c))
    for expression, value in cases:
        source.write_text(f"int main(void) {{ return {expression}; }}\n")
        result = subprocess.run([str(compiler), str(source)],
                                capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, result.stderr
        assert "export function w $main()" in result.stdout
        assert "ret %t" in result.stdout
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
            reference = directory / "reference"
            subprocess.run([os.environ.get("HOST_CC", "cc"), "-std=c2x",
                            str(source), "-o", str(reference)],
                           check=True, timeout=10)
            reference_result = subprocess.run([str(reference)], timeout=5)
            assert result.returncode == reference_result.returncode

    invalid = [
        "", "int main(void) { return; }", "int main(void) { return 0 }",
        "int main(void) { return 2147483648; }",
        "int main(void) { return 0x10; }", "int main(void) { return 0; } int x;",
        "int other(void) { return 0; }", "int main() { return 0; }",
        "int main(void) { return 1 + ; }",
        "int main(void) { return ++1; }", "int main(void) { return (1; }",
        "int main(void) { return 1 / ; }", "#define X 0\n",
        "int main(void) { return 0; }\0",
    ]
    invalid += [
        "int main(void) { return " + "(" * 512 + "1" + ")" * 512 + "; }",
        "int main(void) { return " + "1+" * 512 + "1; }",
        "int main(void) { return " + "- " * 512 + "1; }",
    ]
    for text in invalid:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)],
                                capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and "error:" in result.stderr, text
        assert not result.stdout, (text, result.stdout)
    source.write_text("int main(void) { return 42; }\n")
    with open("/dev/full", "w") as full:
        result = subprocess.run([str(compiler), str(source)], stdout=full,
                                stderr=subprocess.PIPE, text=True, timeout=5)
        assert result.returncode == 1 and "cannot write QBE output" in result.stderr
print("Compiler IL and rejection tests passed" + ("; QBE/runtime passed" if qbe else ""))

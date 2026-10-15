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
    programs = [(f"int main(void) {{ return {expression}; }}\n", value)
                for expression, value in cases]
    programs += [
        ("int main(void) { int x=3; int y=x*4; return y+2; }", 14),
        ("int main(void) { int x; x=42; return x; }", 42),
        ("int main(void) { int a; int b; a=b=7; return a+b; }", 14),
        ("int main(void) { int x=1; x=x+4; return x; }", 5),
        ("int main(void) { int x=0; return x=12; }", 12),
        ("int main(void) { int x=1; int y=x=5; return y+x; }", 10),
        ("int main(void) { int x=0; (x)=9; return x; }", 9),
        ("int main(void) { int x=(x=7); return x; }", 7),
        ("int main(void) { int main=21; return main; }", 21),
        ("int main(void) { int x=5; ; x; 17+2; return x; }", 5),
        ("int main(void) { return 7; int x=2; x=4; return x; }", 7),
        ("int main(void) { int x=1; x=2; }", 0),
        ("int main(void) { ; }", 0),
        ("int main(void) { }", 0),
        ("int main(void) { int x=1; return " + "("*127 + "x" + ")"*127 + "; }", 1),
        ("int main(void) { return " + "0+"*127 + "0; }", 0),
        ("int main(void) {" + ";"*4096 + "}", 0),
        ("int main(void) {" + "".join(f"int x{i}={i};" for i in range(256))
         + "return x255; }", 255),
    ]
    for text, value in programs:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)],
                                capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, result.stderr
        assert "export function w $main()" in result.stdout
        assert "ret " in result.stdout
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
    invalid += [
        "int main(void) { return x; }",
        "int main(void) { x=1; int x; return 0; }",
        "int main(void) { int a=b; int b=2; return a; }",
        "int main(void) { int x; int x; return 0; }",
        "int main(void) { int x=0; 1=x; return x; }",
        "int main(void) { int x=0; (x+1)=2; return x; }",
        "int main(void) { int x=0; +x=2; return x; }",
        "int main(void) { int x=0; (x=1)=2; return x; }",
        "int main(void) { int x=0; x+=1; return x; }",
        "int main(void) { int x=0; x==1; return x; }",
        "int main(void) { int x, y; return 0; }",
        "int main(void) { int x=; return 0; }",
        "int main(void) { int x=1 x=2; return x; }",
        "int main(void) { int x=1; { int x=2; } return x; }",
        "int main(void) { return 0; return missing; }",
        "int main(void) { return 0; int x; int x; }",
        "int main(void) {" + ";"*4097 + "}",
        "int main(void) {" + "".join(f"int x{i};" for i in range(257)) + "}",
        "int main(void) { int x=0; return " + "x+" + "0+"*126 + "0; }",
        "int main(void) { int a; a=" + "a="*128 + "1; }",
    ]
    for keyword in ("if", "while", "bool", "true", "nullptr", "static", "struct"):
        invalid.append(f"int main(void) {{ int {keyword}; return 0; }}")
    for text in invalid:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)],
                                capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and "error:" in result.stderr, text
        assert not result.stdout, (text, result.stdout)
    diagnostic_cases = [
        ("int main(void) { return missing; }", "use of undeclared identifier"),
        ("int main(void) { int x; int x; }", "redeclaration of local"),
        ("int main(void) { 1=2; }", "modifiable lvalue"),
        ("int main(void) { int x=0; return x+" + "0+"*126 + "0; }",
         "typed expression exceeds depth limit"),
        ("int main(void) {" + ";"*4097 + "}", "item limit (4096)"),
        ("int main(void) {" + "".join(f"int x{i};" for i in range(257)) + "}",
         "local limit (256)"),
        ("int main(void)\n{\n\treturn missing;\n}\n", ":3:16: error:"),
    ]
    for text, message in diagnostic_cases:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)],
                                capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and message in result.stderr, result.stderr
        assert not result.stdout
    source.write_text("int main(void) { return 42; }\n")
    with open("/dev/full", "w") as full:
        result = subprocess.run([str(compiler), str(source)], stdout=full,
                                stderr=subprocess.PIPE, text=True, timeout=5)
        assert result.returncode == 1 and "cannot write QBE output" in result.stderr
print("Compiler IL and rejection tests passed" + ("; QBE/runtime passed" if qbe else ""))

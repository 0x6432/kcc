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
    programs += [
        ("int main(void) { int x=1; { int x=2; x=3; } return x; }", 1),
        ("int main(void) { int x=1; { x=4; } return x; }", 4),
        ("int main(void) { int r=0; { int x=2; r=x; } { int x=3; r=r+x; } return r; }", 5),
        ("int main(void) { int x=5; { int y=x; int x=2; return y+x; } }", 7),
        ("int main(void) { { return 9; } return 3; }", 9),
        ("int main(void) { {} }", 0),
        ("int main(void) {" + "{"*127 + "}"*127 + "}", 0),
    ]
    programs += [
        ("int main(void) { if (1) return 7; else return 9; }", 7),
        ("int main(void) { if (0) return 7; else return 9; }", 9),
        ("int main(void) { if (-4) return 8; return 3; }", 8),
        ("int main(void) { if (0) return 8; return 3; }", 3),
        ("int main(void) { int x=0; if (1) x=2; else x=3; return x; }", 2),
        ("int main(void) { int x=0; if (0) x=2; else x=3; return x; }", 3),
        ("int main(void) { if (1) if (0) return 1; else return 2; return 3; }", 2),
        ("int main(void) { if (0) if (0) return 1; else return 2; return 3; }", 3),
        ("int main(void) { if (0) return 1; else if (1) return 2; else return 3; }", 2),
        ("int main(void) { if (0) ; else ; }", 0),
        ("int main(void) { int x=1; if (1) { int x=2; } else { int x=3; } return x; }", 1),
        ("int main(void) { int x=1; if (x=0) return 1; return x; }", 0),
        ("int main(void) { int x=0; if (x=5) return x; else return 3; }", 5),
        ("int main(void) { if (1) { if (0) return 1; else return 2; } else return 3; }", 2),
        ("int main(void) { if (1) { return 2; } else { return 3; } return 9; }", 2),
        ("int main(void) {" + "if(1) "*127 + "return 1;}", 1),
    ]
    for expression, value in [
        ("2 < 3", 1), ("2 > 3", 0), ("2 <= 2", 1), ("2 >= 3", 0),
        ("2 == 2", 1), ("2 != 2", 0), ("-7 < 0", 1), ("-1 > 1", 0),
        ("2147483647 > -1", 1), ("-2147483647 - 1 < 0", 1),
        ("2 < 3 < 2", 1), ("1 == 2 < 3", 1), ("2 + 1 == 3", 1),
    ]:
        programs.append((f"int main(void) {{ return {expression}; }}", value))
    programs += [
        ("int main(void) { int x=0; 0 && (x=3); return x; }", 0),
        ("int main(void) { int x=0; 1 && (x=3); return x; }", 3),
        ("int main(void) { int x=0; 1 || (x=3); return x; }", 0),
        ("int main(void) { int x=0; 0 || (x=3); return x; }", 3),
        ("int main(void) { int x=0; int y=(x=1) && (x=2); return x*10+y; }", 21),
        ("int main(void) { int x=0; (x=1) || (x=2); return x; }", 1),
        ("int main(void) { int x=0; int y=(x=0) || ((x=1) && (x=2)); return x*10+y; }", 21),
        ("int main(void) { int x=0; if ((x=2) && ((x=3) || (x=4))) return x; return 9; }", 3),
        ("int main(void) { int x=0; return x && (1/x); }", 0),
        ("int main(void) { int x=0; return 1 || (1/x); }", 1),
        ("int main(void) { int x=0; if (x) return 1/x; return 4; }", 4),
        ("int main(void) { int x=0; return ! (x=3); }", 0),
        ("int main(void) { int x=0; if (x || (x=2)) { return x; } else return 8; }", 2),
    ]
    for expression, value in [
        ("!0", 1), ("!-3", 0), ("!!7", 1), ("!2 + 3", 3),
        ("-2 && -3", 1), ("0 || -3", 1), ("0 && 4", 0), ("3 || 0", 1),
        ("1 || 0 && 0", 1), ("(1 || 0) && 0", 0), ("2 < 3 && 4 >= 4", 1),
        ("(0 || 1) && (0 || 5)", 1), ("(1 && 2) || (0 && 3)", 1),
        ("(0 || 1) + (1 && 3)", 2), ("! (0 || 2)", 0),
        ("0 || 0 || 8", 1), ("1 && 2 && 0", 0),
    ]:
        programs.append((f"int main(void) {{ return {expression}; }}", value))
    # Assignment has lower precedence than ||, &&, and comparisons.
    programs.append(("int main(void) { int x=0; x=0 || 4 && 3; return x; }", 1))
    def truth_expression(depth):
        if depth == 0:
            value = random_source.randrange(-3, 4)
            return str(value), value
        operation = random_source.choice(["&&", "||", "<", ">=", "==", "!=", "!"])
        left, left_value = truth_expression(depth - 1)
        if operation == "!":
            return f"!({left})", int(not left_value)
        right, right_value = truth_expression(depth - 1)
        if operation == "&&":
            value = int(bool(left_value) and bool(right_value))
        elif operation == "||":
            value = int(bool(left_value) or bool(right_value))
        elif operation == "<":
            value = int(left_value < right_value)
        elif operation == ">=":
            value = int(left_value >= right_value)
        elif operation == "==":
            value = int(left_value == right_value)
        else:
            value = int(left_value != right_value)
        return f"({left}) {operation} ({right})", value

    for _ in range(24):
        expression, value = truth_expression(3)
        programs.append((f"int main(void) {{ return {expression}; }}", value))
    programs += [
        ("int main(void) { int i=0; int s=0; while(i<5) { s=s+i; i=i+1; } return s; }", 10),
        ("int main(void) { int x=7; while(0) x=9; return x; }", 7),
        ("int main(void) { int i=0; while(i<4) i=i+1; return i; }", 4),
        ("int main(void) { int i=0; int s=0; while(i<5) { i=i+1; if(i==2) continue; s=s+i; } return s; }", 13),
        ("int main(void) { int x=0; while(1) { x=x+1; if(x==3) break; } return x; }", 3),
        ("int main(void) { while(1) return 7; return 2; }", 7),
        ("int main(void) { while(1) { if(1) break; else continue; } return 8; }", 8),
        ("int main(void) { int i=0; int s=0; while(i<3) { i=i+1; while(1) { s=s+1; break; } } return s; }", 3),
        ("int main(void) { int i=0; int s=0; while(i<3) { i=i+1; int j=0; while(j<3) { j=j+1; if(j==2) continue; s=s+1; } } return s; }", 6),
        ("int main(void) { int i=0; while(i<5 && (i=i+1)) { if(i<5) continue; } return i; }", 5),
        ("int main(void) { int x=2; while(x>0) { int x=3; x=4; break; } return x; }", 2),
        ("int main(void) { while(0) ; }", 0),
        ("int main(void) {" + "while(0) "*127 + "; return 4;}", 4),
    ]
    programs += [
        ("int main(void) { int i=0; do i=i+1; while(0); return i; }", 1),
        ("int main(void) { int i=0; do { i=i+1; continue; i=100; } while(i<3); return i; }", 3),
        ("int main(void) { int x=0; do { break; } while(x=x+1); return x; }", 0),
        ("int main(void) { int x=0; do return 7; while(1/x); return 0; }", 7),
        ("int main(void) { int x=0; do break; while(1/x); return 9; }", 9),
        ("int main(void) { int x=0; do if(1) x=x+1; else x=100; while(x<3); return x; }", 3),
        ("int main(void) { int x=0; do { int x=1; } while(x); return x; }", 0),
        ("int main(void) { int i=0; int c=0; do { i=i+1; continue; } while(i<3 && (c=c+1)); return i*10+c; }", 32),
        ("int main(void) { int i=0; do ; while((i=i+1)<3); return i; }", 3),
        ("int main(void) { int x; do x=2; while(0); return x; }", 2),
        ("int main(void) { int i=0; int s=0; while(i<3) { i=i+1; do { s=s+1; break; } while(1); if(i<3) continue; s=s+10; } return s; }", 13),
        ("int main(void) { do { if(1) break; else continue; } while(1); return 5; }", 5),
        ("int main(void) {" + "do "*127 + ";" + "while(0);"*127 + "return 3;}", 3),
    ]
    programs += [
        ("int main(void) { int s=0; for(int i=0; i<5; i=i+1) s=s+i; return s; }", 10),
        ("int main(void) { int i; for(i=0; i<4; i=i+1) ; return i; }", 4),
        ("int main(void) { int s=0; for(int i=0; i<5; i=i+1) { if(i==2) continue; s=s+i; } return s; }", 8),
        ("int main(void) { int x=0; for(;;) { x=x+1; if(x==3) break; } return x; }", 3),
        ("int main(void) { int i=0; for(; i<3;) i=i+1; return i; }", 3),
        ("int main(void) { int i=0; for(;;i=i+1) { if(i==2) break; continue; } return i; }", 2),
        ("int main(void) { int i=7; int s=0; for(int i=0; i<3; i=i+1) s=s+i; return i+s; }", 10),
        ("int main(void) { int s=0; for(int i=0; i<2; i=i+1) { int i=7; s=s+i; } return s; }", 14),
        ("int main(void) { for(int i=0; i<2; i=i+1) ; int i=9; return i; }", 9),
        ("int main(void) { int s=0; for(int i=0; i<2; i=i+1) { for(int i=0; i<3; i=i+1) s=s+1; } return s; }", 6),
        ("int main(void) { int s=0; for(int i=0; i<2; i=i+1) { for(int j=0; j<4; j=j+1) { if(j==1) continue; if(j==3) break; s=s+1; } } return s; }", 4),
        ("int main(void) { int i=0; for(; i<3; i=(i+1 || 0)+i) continue; return i; }", 3),
        ("int main(void) { int i=0; int c=0; for(;i<3 && (c=c+1);i=i+1) continue; return i*10+c; }", 33),
        ("int main(void) { int x=0; for(;1;x=x+1) break; return x; }", 0),
        ("int main(void) { int x=0; for(;1;1/x) return 7; return 0; }", 7),
        ("int main(void) { for(int i=(i=0); i<2; i=i+1) ; return 4; }", 4),
        ("int main(void) { int x=0; for(x=5;0;x=9) x=8; return x; }", 5),
        ("int main(void) { int x=0; for(int i=0;i<3;i=i+1) { int y=i+1; x=x+y; } return x; }", 6),
        ("int main(void) { int i=0; for(;i<3;i=i+1) { while(1) break; if(i<2) continue; } return i; }", 3),
        ("int main(void) {" + "for(;0;) "*127 + "; return 2;}", 2),
    ]
    for _ in range(12):
        limit = random_source.randrange(1, 8)
        skipped = random_source.randrange(limit)
        expected = sum(i for i in range(limit) if i != skipped)
        text = (f"int main(void) {{ int s=0; for(int i=0;i<{limit};i=i+1) "
                f"{{ if(i=={skipped}) continue; s=s+i; }} return s; }}")
        programs.append((text, expected))
    programs += [
        ("int f(void) { return 7; } int main(void) { return f(); }", 7),
        ("int f(void); int main(void) { return f(); } int f(void) { return 19; }", 19),
        ("int f(void); int f(void); int f(void) { return 3; } int f(void); "
         "int main(void) { return (f)() + f()*2; }", 9),
        ("int f(void) { int x=6; return x; } int g(void) { int x=8; return x; } "
         "int main(void) { int x=2; return f()+g()+x; }", 16),
        ("int f(void) { return 1; } int main(void) { int x=0; "
         "for(int i=0;i<3;i=i+1) x=x+f(); return x; }", 3),
        ("int f(void) { return 9; } int main(void) { return 0 && f(); }", 0),
        ("int f(void) { return 0; } int main(void) { return f() || (f() || 7); }", 1),
        ("int f(void) { } int main(void) { f(); return 0; }", 0),
        ("int f(void) { return 4; } int main(void) { { int f=9; f=f+1; } return f(); }", 4),
        ("int f(void) { int x=0; while(x<2) x=x+1; return x; } "
         "int main(void) { while(0) break; return f(); }", 2),
    ]
    for text in ("int f(void);", "int library(void) { return 5; }"):
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)],
                                capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, result.stderr
        assert ("export function" in result.stdout) == ("{" in text)

    programs += [
        ("int main() { return 3; }", 3),
        ("int f(); int f(void) { return 4; } int main() { return f(); }", 4),
        ("int id(int x) { return x; } int main(void) { return id(42); }", 42),
        ("int sub(int a, int b) { return a-b; } int main(void) { return sub(3,9); }", -6),
        ("int sum(int, int); int main(void) { return sum(5,8); } "
         "int sum(int a,int b) { return a+b; }", 13),
        ("int f(int a); int f(int b); int f(int c) { return c; } int f(int d); "
         "int main(void) { return f(6); }", 6),
        ("int f(int x) { x=x+5; return x; } int main(void) { int x=7; "
         "int y=f(x); return x+y; }", 19),
        ("int f(int x) { { int x=2; x=9; } return x; } "
         "int main(void) { return f(7); }", 7),
        ("int f(int x) { int y=x*2; return y; } int main(void) { return f(f(3)); }", 12),
        ("int f(int x) { return x; } int main(void) { return (f)(1+f(2)*3); }", 7),
        ("int sum(int a,int b) { return a+b; } int main(void) { int x; int y; "
         "int z=sum(x=3,y=4); return z+x+y; }", 14),
        ("int sum(int a,int b) { return a+b; } int main(void) { "
         "return sum(0 || (1 && 2), (0 || 3) && (1 || 0)); }", 2),
        ("int f(int a,int b) { return a*10+b; } int main(void) { int x=5; "
         "return f(x, x+2); }", 57),
        ("int f(int x) { for(int i=0;i<3;i=i+1) x=x+i; return x; } "
         "int main(void) { return f(4); }", 7),
    ]
    parameter_names = [f"a{i}" for i in range(128)]
    parameters = ",".join(f"int {name}" for name in parameter_names)
    arguments = ",".join(str(i) for i in range(128))
    programs.append((f"int f({parameters}) {{ return a0+a6+a127; }} "
                     f"int main(void) {{ return f({arguments}); }}", 133))
    programs.append((f"int f({parameters}) {{ " +
                     "".join(f"int x{i}=a{i};" for i in range(128)) +
                     "return x127; } int main(void) { return f(" + arguments + "); }", 127))
    for _ in range(12):
        values = [random_source.randrange(-12, 13) for _ in range(4)]
        argument_text = ",".join(str(value) for value in values)
        expected = values[0]*3 + values[1]*5 - values[2]*7 + values[3]
        programs.append(("int mix(int a,int b,int c,int d) { return a*3+b*5-c*7+d; } "
                         f"int main(void) {{ return mix({argument_text}); }}", expected))

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
            reference_build = subprocess.run(
                [os.environ.get("HOST_CC", "cc"), "-std=c2x", str(source),
                 "-o", str(reference)], capture_output=True, text=True, timeout=10)
            assert reference_build.returncode == 0, reference_build.stderr
            reference_result = subprocess.run([str(reference)], timeout=5)
            assert result.returncode == reference_result.returncode

    invalid = [
        "", "int main(void) { return; }", "int main(void) { return 0 }",
        "int main(void) { return 2147483648; }",
        "int main(void) { return 0x10; }", "int main(void) { return 0; } int x;",
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

        "int main(void) { int x, y; return 0; }",
        "int main(void) { int x=; return 0; }",
        "int main(void) { int x=1 x=2; return x; }",

        "int main(void) { return 0; return missing; }",
        "int main(void) { return 0; int x; int x; }",
        "int main(void) {" + ";"*4097 + "}",
        "int main(void) {" + "".join(f"int x{i};" for i in range(257)) + "}",
        "int main(void) { int x=0; return " + "x+" + "0+"*126 + "0; }",
        "int main(void) { int a; a=" + "a="*128 + "1; }",
    ]
    invalid += [
        "int main(void) { { int x=1; } return x; }",
        "int main(void) { int x=1; { int x=2; int x=3; } return x; }",
        "int main(void) {" + "{"*128 + "}"*128 + "}",
        "int main(void) {" + "{;"*2049 + "}"*2049 + "}",
        "int main(void) {" + "{;};"*1366 + "}",
    ]
    invalid += [
        "int main(void) { if () return 1; }",
        "int main(void) { if 1 return 1; }",
        "int main(void) { if (1) }",
        "int main(void) { else return 1; }",
        "int main(void) { if (1) return 1; else }",
        "int main(void) { if (1) int x; }",
        "int main(void) { if (0) return missing; return 0; }",
        "int main(void) { if (1) { int x=1; } return x; }",
        "int main(void) { if (1) { int x=1; } else return x; }",
        "int main(void) { if (1) return 1; else return 2; return missing; }",
        "int main(void) { return 1 << 2; }",
        "int main(void) {" + "if(1) "*128 + "return 1;}",
    ]
    invalid += [
        "int main(void) { return 0 && missing; }",
        "int main(void) { return 1 || missing; }",
        "int main(void) { int x=0; !x=2; }",
        "int main(void) { int x=0; (x && 1)=2; }",
        "int main(void) { return 1 & 2; }",
        "int main(void) { return 1 | 2; }",
        "int main(void) { return 1 && ; }",
        "int main(void) { return !; }",
        "int main(void) { return " + "1&&"*128 + "1; }",
    ]
    invalid += [
        "int main(void) { break; }",
        "int main(void) { continue; }",
        "int main(void) { if(0) break; }",
        "int main(void) { return 0; continue; }",
        "int main(void) { while() ; }",
        "int main(void) { while(1) }",
        "int main(void) { while(1) break }",
        "int main(void) { while(0) return missing; }",
        "int main(void) { while(1) { int x=1; break; } return x; }",
        "int main(void) { while(0) ; continue; }",
        "int main(void) {" + "while(0) "*128 + ";}",
    ]
    invalid += [
        "int main(void) { do ; while(0) }",
        "int main(void) { do ; while(); }",
        "int main(void) { do ; }",
        "int main(void) { do break; while(missing); }",
        "int main(void) { do { int x=0; } while(x); }",
        "int main(void) { do ; while(0); continue; }",
        "int main(void) {" + "do "*128 + ";" + "while(0);"*128 + "}",
    ]
    invalid += [
        "int main(void) { for() ; }",
        "int main(void) { for(;0) ; }",
        "int main(void) { for(int i=0 i<2;i=i+1) ; }",
        "int main(void) { for(int i=0; i<2; i=i+1) ; return i; }",
        "int main(void) { for(int i=0; i<2; j=j+1) { int j=0; } }",
        "int main(void) { for(;missing;) ; }",
        "int main(void) { for(;0;missing) ; }",
        "int main(void) { for(int i=0,j=0;0;) ; }",
        "int main(void) { for(int i=0;i<2;i++) ; }",
        "int main(void) { for(;0;) ; break; }",
        "int main(void) {" + "for(;0;) "*128 + ";}",
    ]
    invalid += [
        "int main(void) { return later(); } int later(void) { return 1; }",
        "int main(void) { return missing(); }",
        "int f(void) { return 1; } int f(void) { return 2; }",
        "int f(void); int main(void) { int f=3; return f(); }",
        "int f(void); int main(void) { int f=f(); return 0; }",
        "int f(void); int main(void) { return f; }",
        "int f(void); int main(void) { f=3; return 0; }",
        "int f(void); int main(void) { return f()(); }",
        "int f(void); int main(void) { return (1+2)(); }",
        "int main(void) { while(0) break; } int f(void) { break; }",
        "int a(void) { int x=1; return x; } int b(void) { return x; }",
        "int f(void);"*513,
        "".join(f"int f{i}(void);" for i in range(257)),
        "int f(void); int main(void) { return f" + "()"*128 + "; }",
    ]
    invalid += [
        "int f(int x) { int x; return 0; }",
        "int f(int x,int x) { return x; }",
        "int f(int x,int x);",
        "int f(int); int f(void);",
        "int f(); int f(int x) { return x; }",
        "int f(int,int); int f(int x) { return x; }",
        "int f(int); int main(void) { return f(); }",
        "int f(void); int main(void) { return f(1); }",
        "int f(int); int main(void) { return f(1,2); }",
        "int f(int); int main(void) { return f(missing); }",
        "int f(int); int main(void) { return f(1,); }",
        "int f(int); int main(void) { return f(,1); }",
        "int f(int); int main(void) { return f(1 2); }",
        "int f(void,int x);", "int f(int x,void);", "int f(int x,);",
        "int f(int x int y);", "int f(int x=1);", "int f(int,...) ;",
        "int f(int) { return 0; }",
        "int main(int x) { return x; }",
        "int f(int f) { return f(0); }",
        "int f(int x) { return x; } int main(void) { return x; }",
        "int f(int x) { return x; } int main(void) { return f((1,2)); }",
        "int f(" + ",".join("int a"+str(i) for i in range(129)) + ");",
        "int f(void); int main(void) { return f(" + ",".join("0" for _ in range(129)) + "); }",
        "int f(" + parameters + ") { " + "".join(f"int x{i};" for i in range(129)) + "}",
    ]
    for keyword in ("if", "while", "do", "for", "break", "continue", "bool", "true", "nullptr", "static", "struct"):
        invalid.append(f"int main(void) {{ int {keyword}; return 0; }}")
    for text in invalid:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)],
                                capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and "error:" in result.stderr, text
        assert not result.stdout, (text, result.stdout)
    diagnostic_cases = [
        ("int f(int); int f(void);", "incompatible function declaration"),
        ("int f(int x,int x);", "duplicate parameter name"),
        ("int f(int x) { int x; }", "redeclaration of local"),
        ("int f(int); int main(void) { return f(); }", "argument count"),
        ("int f(int) { return 0; }", "unnamed definition parameters"),
        ("int main(void) { return f(); }", "call to undeclared function"),
        ("int f(void); int main(void) { int f; f(); }", "not a function"),
        ("int f(void) {} int f(void) {}", "redefinition of function"),
        ("int f(void);"*513, "declaration limit (512)"),
        ("".join(f"int f{i}(void);" for i in range(257)), "function limit (256)"),
        ("int main(void) { break; }", "break is only supported inside a loop"),
        ("int main(void) { continue; }", "continue requires an enclosing loop"),
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
    source.write_text("int main(void) { if (1) return 2; else return 3; return 9; }")
    result = subprocess.run([str(compiler), str(source)],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0 and result.stdout.count("\tret ") == 2
    assert "\tjmp " not in result.stdout  # both paths terminate; no merge jump
    source.write_text("int main(void) { return (0 || 1) && (0 || 5); }")
    result = subprocess.run([str(compiler), str(source)],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0 and result.stdout.count(" =w phi ") == 3
    assert result.stdout.count("\tjnz ") == 3
    source.write_text("int main(void) { return 42; }\n")
    with open("/dev/full", "w") as full:
        result = subprocess.run([str(compiler), str(source)], stdout=full,
                                stderr=subprocess.PIPE, text=True, timeout=5)
        assert result.returncode == 1 and "cannot write QBE output" in result.stderr
print("Compiler IL and rejection tests passed" + ("; QBE/runtime passed" if qbe else ""))

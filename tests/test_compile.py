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
        # Former initialized-global rejection: definitions after a function
        # are now supported, including uses through a prior extern declaration.
        ("int main(void) { return 0; } int x=42;", 0),
        ("extern int x; int main(void) { return x; } int x=42;", 42),
        ("int f(int) { return 42; } int main(void) { return f(7); }", 42),
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

    programs += [
        ("int fact(int n) { if(n<2) return 1; return n*fact(n-1); } "
         "int main(void) { return fact(5); }", 120),
        ("int fib(int n) { if(n<2) return n; return fib(n-1)+fib(n-2); } "
         "int main(void) { return fib(10); }", 55),
        ("int odd(int); int even(int n) { if(n==0) return 1; return odd(n-1); } "
         "int odd(int n) { if(n==0) return 0; return even(n-1); } "
         "int main(void) { return even(20)*10+odd(19); }", 11),
        ("int sum(int n,int acc) { if(n==0) return acc; return sum(n-1,acc+n); } "
         "int main(void) { return sum(20,0); }", 210),
        ("int f(int n) { int saved=n*3; if(n==0) return 0; "
         "int child=f(n-1); return saved+child; } "
         "int main(void) { return f(8); }", 108),
        ("int f(int n) { if(n==0) return 0; return (n>0 && f(n-1)) || n==3; } "
         "int main(void) { return f(5); }", 1),
    ]
    # Accept the exact external/function resource bounds, not just their failures.
    for text in ("int f(void);"*512,
                 "".join(f"int f{i}(void);" for i in range(256))):
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)],
                                capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stdout and not result.stderr

    phase_programs = [
        ("in\\\nt ma\\\nin(vo\\\nid) { ret\\\nurn 4\\\n2; }\n", 42),
        ("int fo\\\no(int); int main(void) { return foo(7); } "
         "int foo(int x) { return x+1; }\n", 8),
        ("int main(void) { int lo\\\ncal=8; return local; }\n", 8),
        ("int f(int na\\\nme) { return name; } int main(void) { return f(9); }\n", 9),
        ("int main(void) { return 3 >\\\n= 2 &\\\n& 1 =\\\n= 1; }\n", 1),
        ("int main(void) { // ignored\\\nreturn 99;\nreturn 7; }\n", 7),
        ("int main(void) { /\\\n* hidden */ return 3; }\n", 3),
        ("int main(void) { /* hidden *\\\n/ return 4; }\n", 4),
        ("int main(void) { /\\\n/ hidden\nreturn 5; }\n", 5),
        ("int main(void) { return 1/**/+2; }\n", 3),
        ("int main(void) { int x=4; return x/\\\n* separator *\\\n/+1; }\n", 5),
    ]
    for text, value in phase_programs:
        for line_ending in ("\n", "\r\n", "\r"):
            programs.append((text.replace("\n", line_ending), value))

    programs += [
        ("int main(void) <% return 7; %>\n", 7),
        ("int f(int x) <% if(x) <% return x; %> return 3; %> "
         "int main(void) <% return f(4); %>\n", 4),
    ]
    directive_programs = [
        ("#\nint main(void) { return 7; }\n#\n", 7),
        ("# /*leading*/\n%: /*other*/\nint main(void) { return 8; }\n", 8),
        ("\v\f#\nint main(void) { return 9; }\n", 9),
        ("int main(void)\n{\n#\nint x=2;\n%:\nreturn x+3;\n}\n", 5),
        ("int main(void) { return 2\n#\n+3; }\n", 5),
        ("int add\n#\n(int a,\n%:\nint b)\n{\n#\nreturn a+b;\n}\n"
         "int main(void) { return add(4,7); }\n", 11),
        ("# // continued\\\nnot C tokens\nint main(void) { return 12; }\n", 12),
        ("#/* block\n across */\nint main(void) { return 13; }\n", 13),
        ("%\\\n:\nint main(void) { return 14; }\n", 14),
        ("/* leading\n */ # /*\v\f*/\nint main(void) { return 15; }\n", 15),
    ]
    directive_programs += [
        ("#define VALUE 6\n#define DOUBLE VALUE+VALUE\n"
         "int main(void) { return 3*DOUBLE; }\n", 24),
        ("#define TYPE int\n#define START main\n#define RET return\n"
         "TYPE START(void) { RET 42; }\n", 42),
        ("#define NAME plus\n#define PARAM value\n#define N 4\n"
         "int NAME(int PARAM) { return PARAM+N; }\n"
         "int main(void) { return NAME(7); }\n", 11),
        ("#define X 1\nint first(void) { return X; }\n#undef X\n#define X 3\n"
         "int main(void) { return first()+X; }\n", 4),
        ("#define EMPTY\n#define VALUE ALIAS\n#define ALIAS 8\n"
         "int main(void) { EMPTY return VALUE; }\n", 8),
        ("#define SELF SELF\n#define A B\n#define B A\n"
         "int main(void) { int SELF=3; int A=4; return SELF+A; }\n", 7),
        ("#define CALL add\nint add(int x);\n"
         "int main(void) { return CALL(6); }\nint CALL(int x) { return x+2; }\n", 8),
        ("%:define X 3\nint main(void) { return X; }\n", 3),
        ("#define UNUSED 12u .5 \"unused\"\nint main(void) { return 7; }\n", 7),
        ("int main(void) { return 7; }\n#define X 1\n", 7),
    ]
    directive_programs += [
        ("#define VALUE() 42\nint main(void) { return VALUE(); }\n", 42),
        ("#define TYPE() int\n#define NAME() main\n#define RET() return\n"
         "TYPE() NAME()(void) { RET() 7; }\n", 7),
        ("#define VALUE() 7\n#define ALIAS VALUE\n"
         "int main(void) { return ALIAS(/**/); }\n", 7),
        ("#define F() 42\nint main(void) { int F=3; return F+F(); }\n", 45),
        ("#define E()\n#define VALUE() 8\n"
         "int main(void) { E() return VALUE\n(\n); }\n", 8),
        ("#define int() 42\nint main(void) { return int(); }\n", 42),
        ("#define F() 7\nint first(void) { return F(); }\n#undef F\n#define F 3\n"
         "int main(void) { return first()+F; }\n", 10),
        ("#define F() 1\n#define G() F() + F()\n#define H() G()+G()\n"
         "int main(void) { return H(); }\n", 4),
        ("#define F() call\nint call(void) { return 9; }\n"
         "int main(void) { return F()(); }\n", 9),
        ("#define PREFIX F(\n#define F() 7\n"
         "int main(void) { return PREFIX ); }\n", 7),
        ("int f(void) { return 7; }\n#define f() f()\n"
         "int main(void) { return f(); }\n", 7),
        ("int f(void) { return 9; }\n#define f() g()\n#define g() f()\n"
         "int main(void) { return f(); }\n", 9),
        ("int main(void) { return 7; }\n#define UNUSED() 12u \"unused\"\n", 7),
    ]
    directive_programs += [
        ("#define ADD(a,b) ((a)+(b))\n#define ID(x) x\n"
         "int main(void) { return ADD(ID(ID(20)),22); }\n", 42),
        ("#define ID(x) x\nID(int) ID(main)(void) { return ID(7); }\n", 7),
        ("#define CALL(f,x) f(x)\nint add(int x) { return x+1; }\n"
         "int main(void) { return CALL(add,7); }\n", 8),
        ("#define ID(x) x\n#define VALUE() 7\n"
         "int main(void) { return ID(VALUE)(); }\n", 7),
        ("#define ID(x) x\n#define F(x) x\n"
         "int main(void) { return ID(F)(7); }\n", 7),
        ("#define DROP(x) 7\n#define BAD(a,b) a+b\n"
         "int main(void) { return DROP(BAD(1)); }\n", 7),
        ("#define DROP(x) 7\n#define OUT(x) DROP(x)\n"
         "int main(void) { return OUT(12u); }\n", 7),
        ("#define DROP(a,b) 7\nint main(void) { return DROP({1,2}); }\n", 7),
        ("#define EMPTY(x)\n#define KEEP(a,b) a b\n"
         "int main(void) { EMPTY() return KEEP(,7); }\n", 7),
        ("#define COMMA 3,4\n#define ADD(a,b) ((a)+(b))\n#define CALL(x) ADD(x)\n"
         "int main(void) { return CALL(COMMA); }\n", 7),
        ("int f(int x) { return x+2; }\n#define f(x) f(x)\n"
         "int main(void) { return f(5); }\n", 7),
        ("#define DECL(type,name,value) type name=value\n"
         "int main(void) { DECL(int,x,7); return x; }\n", 7),
        ("#define BOTH(x) ((x)&&(x))\nint main(void) { int x=0; BOTH(x=x+1); return x; }\n", 2),
    ]
    directive_programs += [
        ("#define V(...) __VA_ARGS__\nint main(void) { return V(42); }\n", 42),
        ("#define V(x,...) x __VA_OPT__(+ __VA_ARGS__)\n"
         "int main(void) { return V(42); }\n", 42),
        ("#define V(x,...) x __VA_OPT__(+ __VA_ARGS__)\n"
         "int main(void) { return V(42,); }\n", 42),
        ("#define V(x,...) x __VA_OPT__(+ __VA_ARGS__)\n#define E\n"
         "int main(void) { return V(42,E); }\n", 42),
        ("#define V(x,...) x __VA_OPT__(+ __VA_ARGS__)\n"
         "int main(void) { return V(20,22); }\n", 42),
        ("#define CALL(f,...) f(__VA_ARGS__)\n"
         "int add(int x,int y) { return x+y; }\n"
         "int main(void) { return CALL(add,20,22); }\n", 42),
        ("#define CALL(f,...) f(__VA_ARGS__)\nint value(void) { return 42; }\n"
         "int main(void) { return CALL(value); }\n", 42),
        ("#define CALL(...) add(20 __VA_OPT__(,) __VA_ARGS__)\n"
         "int add(int x,int y) { return x+y; }\n"
         "int main(void) { return CALL(22); }\n", 42),
        ("#define V(...) __VA_OPT__(int x=__VA_ARGS__;)\n"
         "int main(void) { V(42) return x; }\n", 42),
        ("#define V(...) __VA_OPT__(int x=__VA_ARGS__;)\n#define E\n"
         "int main(void) { V(E) return 42; }\n", 42),
        ("#define V(...) __VA_OPT__(__VA_ARGS__)\n"
         "int main(void) { return V(V(42)); }\n", 42),
        ("#define DROP(...) 42\n#define BAD(x,y) x+y\n"
         "int main(void) { return DROP(BAD(1),12u); }\n", 42),
        ("#define LP() (\n#define G(x) 42\n"
         "#define V(r,x,...) __VA_OPT__(G r x) )\n"
         "int main(void) { return V(LP(),0,1); }\n", 42),
        ("#define V(...) __VA_OPT__(G)\n#define G(x) x\n"
         "int main(void) { return V(1)(42); }\n", 42),
        ("int f(int x) { return x; }\n#define f(...) f(__VA_ARGS__)\n"
         "int main(void) { return f(42); }\n", 42),
        ("#define BOTH(...) ((__VA_ARGS__) && (__VA_ARGS__))\n"
         "int main(void) { int x=0; BOTH(x=x+1); return x; }\n", 2),
    ]
    directive_programs += [
        ("#define DROP(x) 42\n#define OUT(x) DROP(#x)\n"
         "int main(void) { return OUT(a + b); }\n", 42),
        ("#define DROP(x) 42\n#define OUT(x) DROP(%: x)\n"
         "int main(void) { return OUT(12u); }\n", 42),
        ("#define DROP(x) 42\n#define OUT(...) DROP(#__VA_ARGS__)\n"
         "int main(void) { return OUT(a,b,c); }\n", 42),
        ("#define DROP(x) 42\n#define OUT(...) DROP(#__VA_ARGS__)\n"
         "int main(void) { return OUT(); }\n", 42),
        ("#define DROP(x) 42\n#define OUT(x,...) DROP(__VA_OPT__(#x))\n"
         "int main(void) { return OUT(a,1); }\n", 42),
        ("#define DROP(x) 42\n#define OUT(x,...) DROP(__VA_OPT__(#x))\n"
         "int main(void) { return OUT(a); }\n", 42),
        ("#define DROP(x) 40\n#define OUT(x) DROP(#x)+x\n"
         "int main(void) { return OUT(2); }\n", 42),
        ("#define DROP(x) 42\n#define OUT(x) DROP(#x)\n#define BAD(a,b) a+b\n"
         "int main(void) { return OUT(BAD(1)); }\n", 42),
    ]
    directive_programs += [
        ("#define DROP(x) 42\n#define V(x,...) DROP(#__VA_OPT__(x))\n"
         "int main(void) { return V(7,1); }\n", 42),
        ("#define DROP(x) 42\n#define V(x,...) DROP(#__VA_OPT__(x))\n"
         "int main(void) { return V(7); }\n", 42),
        ("#define DROP(x) 42\n#define V(x,...) DROP(#__VA_OPT__(x))\n#define E\n"
         "int main(void) { return V(7,E); }\n", 42),
        ("#define DROP(x) 42\n#define V(x,...) DROP(%: __VA_OPT__(#x))\n"
         "int main(void) { return V(12u,1); }\n", 42),
        ("#define DROP(x) 42\n#define V(...) DROP(#__VA_OPT__(__VA_ARGS__))\n"
         "int main(void) { return V(1,2); }\n", 42),
        ("#define DROP(x) 42\n#define V(...) DROP(#__VA_OPT__(# __VA_ARGS__))\n"
         "int main(void) { return V(a,b); }\n", 42),
        ("#define DROP(x) 42\n#define BAD(a,b) a+b\n"
         "#define V(x,...) DROP(#__VA_OPT__(BAD(x)))\n"
         "int main(void) { return V(7,1); }\n", 42),
        ("#define DROP(x) 40\n#define A 7\n#define V(x,...) DROP(#__VA_OPT__(x A))+x\n"
         "int main(void) { return V(2,1); }\n", 42),
    ]
    directive_programs += [
        ("#define C(a,b) a##b\nC(in,t) C(ma,in)(C(vo,id)) { C(ret,urn) C(4,2); }\n", 42),
        ("#define C(a,b) a##b\nint main(void) { int C(va,r)=42; return C(va,r); }\n", 42),
        ("#define C(a,b) a##b\nint C(ad,d)(int x) { return x+2; }\n"
         "int main(void) { return C(ad,d)(40); }\n", 42),
        ("#define C(a,b) a %:%: b\n#define forty_two 42\n"
         "int main(void) { return C(forty_,two); }\n", 42),
        ("#define C(a,b,c) a##b##c\nint main(void) { return C(4,,2); }\n", 42),
        ("#define C(a,b) a##b\nint main(void) { return C(,42); }\n", 42),
        ("#define V(...) 4 ## __VA_OPT__(2)\nint main(void) { return V(1); }\n", 42),
        ("#define V(...) __VA_OPT__(4) ## 2\nint main(void) { return V(1); }\n", 42),
        ("#define DROP(x) 42\n#define V(x,...) DROP(#__VA_OPT__(x##x x##x))\n"
         "int main(void) { return V(,1); }\n", 42),
        ("#define C(a,b) a##b\n#define RAW42() 42\n"
         "int main(void) { return C(RAW,42)(); }\n", 42),
    ]
    for text, value in directive_programs:
        for ending in ("\n", "\r\n", "\r"):
            programs.append((text.replace("\n", ending), value))

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
        "int main(void) { return 9223372036854775808; }",
        "int main(void) { return 0xg; }", "int main(void) { return 0; } int *x=0;",
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
        "int main(void) { int x=0; x+=p; return x; }",

        "int main(void) { int x, int y; return 0; }",
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
        "int main(void) { return 1 <<= 2; }",
        "int main(void) {" + "if(1) "*128 + "return 1;}",
    ]
    invalid += [
        "int main(void) { return 0 && missing; }",
        "int main(void) { return 1 || missing; }",
        "int main(void) { int x=0; !x=2; }",
        "int main(void) { int x=0; (x && 1)=2; }",
        "int main(void) { return 1 &= 2; }",
        "int main(void) { return 1 |= 2; }",
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
        "int main(void) { for(int i=0,j[];0;) ; }",
        "int main(void) { for(int i=0;i<2;j++) ; }",
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
        "int f(int [2][]) { return 0; }",
        "int main(int x) { return x; }",
        "int f(int f) { return f(0); }",
        "int f(int x) { return x; } int main(void) { return x; }",
        "int f(int x,int y) { return x+y; } int main(void) { return f((1,2)); }",
        "int f(" + ",".join("int a"+str(i) for i in range(129)) + ");",
        "int f(void); int main(void) { return f(" + ",".join("0" for _ in range(129)) + "); }",
        "int f(" + parameters + ") { " + "".join(f"int x{i};" for i in range(129)) + "}",
    ]
    invalid += [
        "int ma/**/in(void) { return 0; }\n",
        "int main(void) { return 1/**/2; }\n",
        "int main(void) { return 1\\ \n+2; }\n",
        "int main(void) { return 1\\\t\n+2; }\n",
        "int main(void) { return " + "\\"*2 + "\n\n42; }\n",
        "int main(void) { return 1??/\n+2; }\n",
    ]
    invalid += [
        "int main(void) { return 1e+2; }", "int main(void) { return 0x1p-1; }",
        "int main(void) { return .5; }", "int main(void) { return 1'g; }",
        "int main(void) { return 'xy'; }", "int main(void) { return u8'x'; }",
        'int main(void) { return "x"; }', 'int main(void) { return L"x"; }',
        "%:define X(x) 3\nint main(void) { return X; }",
    ]
    invalid += [
        "#42\nint main(void) { return 0; }",
        "#unknown 12u\nint main(void) { return 0; }",
        "#\v\nint main(void) { return 0; }", "#\f",
        "%:\v\nint main(void) { return 0; }",
        "int main(void) { #\nreturn 0; }",
        "int/*\n*/#\nmain(void) { return 0; }",
        "#/*\n*/int main(void) { return 0; }",
        "int main(void) { return 0; }\n#define X(...,x) 1\n",
        "#\n", "# // comment\n", "%:%:\nint main(void) { return 0; }",
        "#unknown \0\nint main(void) { return 0; }",
    ]
    for name in ("include", "embed", "line", "error", "pragma",
                 "if", "ifdef", "ifndef", "elif", "elifdef", "elifndef", "else", "endif"):
        invalid.append(f"#{name} x\nint main(void) {{ return 0; }}")
    for keyword in ("if", "while", "do", "for", "break", "continue", "bool", "true", "nullptr", "static", "struct"):
        invalid.append(f"int main(void) {{ int {keyword}; return 0; }}")
    for text in invalid:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)],
                                capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and "error:" in result.stderr, text
        assert not result.stdout, (text, result.stdout)
    diagnostic_cases = [
        ("#define C(a,b) a##b\nint main(void) { return C(x,+); }", ":2:25: error: token pasting must produce exactly one preprocessing token"),
        ("#define C(a,b) a##b\nint main(void) { return C(1,.5); }", ":2:25: error: unsupported numeric"),
        ("#define C(a,b) a##b\nint main(void) { return C(miss,ing); }", ":2:25: error:"),
        ("#define V(x,...) #__VA_OPT__(x)\nint main(void) { return V(7,1); }", ":2:25: error: unsupported pointer conversion"),
        ("#define OUT(x,...) V(x,__VA_ARGS__)\n#define V(x,...) #__VA_OPT__(x)\nint main(void) { return OUT(7,1); }", ":3:25: error: unsupported pointer conversion"),
        ("#define BAD(a,b) a+b\n#define V(x,...) #__VA_OPT__(x)\nint main(void) { return V(BAD(1),1); }", ":3:25: error: macro argument count"),
        ("#define S(x) #x\nint main(void) { return S(a); }", ":2:25: error: unsupported pointer conversion"),
        ("#define OUT(x) INNER(x)\n#define INNER(x) #x\nint main(void) { return OUT(a); }", ":3:25: error: unsupported pointer conversion"),
        ("#define S(x) #1\nint main(void) { return 0; }", "expected a macro parameter after stringizing"),
        ("#define S(...) #__VA_OPT__(#1)\nint main(void) { return 0; }", "expected a macro parameter after stringizing"),
        ("#define V(...) __VA_ARGS__\nint main(void) { return V(missing); }", ":2:25: error:"),
        ("#define V(...) __VA_OPT__(missing)\nint main(void) { return V(1); }", ":2:25: error:"),
        ("#define V(...) __VA_ARGS__\nint main(void) { return V(12.5); }", ":2:25: error: unsupported numeric"),
        ("#define V(x,y,...) x\nint main(void) { return V(); }", "macro argument count"),
        ("#define V(...) __VA_OPT__(__VA_OPT__(1))\nint main(void) { return 0; }", "nested __VA_OPT__"),
        ("#define V(...) __VA_OPT__ 1\nint main(void) { return 0; }", "expected '(' after __VA_OPT__"),
        ("#define ID(x) x\nint main(void) { return ID(missing); }", ":2:25: error:"),
        ("#define ID(x) x\nint main(void) { return ID(12.5); }", ":2:25: error: unsupported numeric"),
        ("#define F(a,b) a+b\nint main(void) { return F(1); }", "macro argument count"),
        ("#define F(x,x) x\nint main(void) { return 0; }", "duplicate macro parameter"),

        ("#define F() 12.5\nint main(void) { return F(); }", ":2:25: error: unsupported numeric"),
        ("#define NAME() main\nint NAME()(int x) { return x; }", ":2:5: error:"),
        ("#define F() 7\nint main(void) { return F(1); }", "requires no arguments"),
        ("#define F() 7\nint main(void) { return F(", "unterminated function-like"),
        ("#define F() 7\nint main(void) { return F(\n#undef F\n); }", "directives during macro invocation"),

        ("#define VALUE 12.5\nint main(void) { return VALUE; }", ":2:25: error: unsupported numeric"),
        ("#define A B\n#define B missing\nint main(void) { return A; }", ":3:25: error:"),
        ("#define NAME main\nint NAME(int x) { return x; }", ":2:5: error:"),
        ("#define X(...,x) 1\nint main(void) { return 0; }", "expected ')' after variadic ellipsis"),
        ("#define X 1\n#define X 2\nint main(void) { return X; }", "incompatible macro redefinition"),
        ("#define X 1 ##\nint main(void) { return 0; }", "token pasting requires an operand"),

        ("#include X 12.5\nint main(void) { return 0; }", "quoted name"),
        ("#unknown 12.5\nint main(void) { return 0; }", "unknown preprocessing directive"),
        ("#42\nint main(void) { return 0; }", "expected a directive name"),
        ("#\v\nint main(void) { return 0; }", "only space and tab"),
        ("int main(void) { #\nreturn 0; }", "misplaced '#'"),
        ("#\\\r\nunknown\nint main(void) { return 0; }", ":2:1: error:"),
        ("int main(void)\n{\n\tret\\\nurn missing;\n}\n", ":4:5: error:"),
        ("int main(void) {\nreturn mis\\\nsing;\n}\n", ":2:8: error:"),
        ("int main(void) {\r\n\treturn 0;\\\r\n\tmissing;\r\n}\r\n", ":3:9: error:"),
        ("int main(void) {\n/\\\n* unterminated", ":2:1: error:"),
        ("int f(int); int f(void);", "incompatible function declaration"),
        ("int f(int x,int x);", "duplicate parameter name"),
        ("int f(int x) { int x; }", "redeclaration of local"),
        ("int f(int); int main(void) { return f(); }", "argument count"),
        ("int f(int [2][]) { return 0; }", "array element type must be complete"),
        ("int main(void) { return f(); }", "call to undeclared function"),
        ("int f(void); int main(void) { int f; f(); }", "not a function"),
        ("int f(void) {} int f(void) {}", "redefinition of function"),
        ("int f(void);"*513, "declaration limit (512)"),
        ("".join(f"int f{i}(void);" for i in range(257)), "function limit (256)"),
        ("int main(void) { break; }", "break requires an enclosing loop or switch"),
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
    # Keep the third return in a predecessor-free block: later syntax may contain
    # a goto target. Both if branches still terminate without a false merge edge.
    assert result.returncode == 0 and result.stdout.count("\tret ") == 3
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

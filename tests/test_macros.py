"""Compare supported macro token kinds AND spellings with the host preprocessor."""
import os
import random
import shlex
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
driver = root / "build" / "pp_oracle"
host = shlex.split(os.environ.get("HOST_CC", "cc"))
examples = [
    "#define X 42\nX X\n#undef X\nX\n#define X 7\nX\n",
    "#define A B\n#define B A\nA B A B\n",
    "#define A 1 B\n#define B 2 A\nA B\n",
    "#define A B C\n#define B A\n#define C A\nA B C\n",
    "#define A A A\nA A\n",
    "#define A B B\n#define B C C\n#define C B A\nA\n",
    "#define E\n#define A E\n#define B A A\nE A B 1\n",
    "#define X int\n#define int 9\nX\n#undef int\nX\n",
    "#define int value\n#define return 42\nint return\n",
    "#define X (1 +2)\n#define X /* comment */ (1\t+2)\nX\n",
    "%:define X 3\nX\n%:undef X\nX\n",
    "#define X ret\\\nurn\n#define VALUE 4\\\n2\nX VALUE\n",
    "#define A B\nA\n#define B 3\nA\n#undef B\nA\n",
    "#define A B\n#define B A\nA\n#undef A\n#define A 5\nB\n",
    "#define X/* across\nlines */(7)\nX\n",
    "#define ONE 1\n#define PLUS +\nONE 2 PLUS+\n",
    "#define X (\nX 1 )\n",
]
examples += [
    "#define F() 7\nF F() F (\n)\n",
    "#define F()\nF() F() F\n",
    "#define F()7\n#define F( /**/ ) 7\nF()\n",
    "#define F() 7\n#define A F\nA()\n",
    "#define F() 7\n#define A F(\nA )\n",
    "#define F() 7\n#define LP (\nF LP )\n",
    "#define F() 7\n#define E\nF E ()\n",
    "#define F() F()\nF() F()\n",
    "#define F() G()\n#define G() F()\nF() G()\n",
    "#define A F()\n#define F() A\nA F()\n",
    "#define A F\n#define F() A\nA() A()() A()()()\n",
    "#define F() G\n#define G() F\nF()() F()()() F()()()()\n",
    "#define F() 7\n#define A F() F\nA()\n",
    "#define F() G\n#define G() 7\nF()()\n",
    "#define F() G\n#define G() 7\n#define X F()()\nX\n",
    "#define F() 7\nF/**/(/**/) F\\\n()\n",
    "#define F() 7\nF()\n#undef F\n#define F 9\nF\n",
    "#define F 7\nF\n#undef F\n#define F() 9\nF()\n",
    "#define int() 7\nint int() int\n",
    "#define F() 12u \"unused\"\nF\n",
]
# Deterministic cyclic graphs exercise disabled ancestors and repeated rescans.
random_source = random.Random(42)
for _ in range(80):
    lines = []
    names = [f"M{i}" for i in range(8)]
    words = names + ["1", "2", "value", "+", "int"]
    for name in names:
        body = " ".join(random_source.choice(words)
                        for _ in range(random_source.randrange(3)))
        lines.append(f"#define {name} {body}\n")
    lines.append(" ".join(names) + "\n")
    examples.append("".join(lines))

# Zero-parameter calls form cyclic graphs; object aliases cross source frames.
for _ in range(80):
    lines = []
    names = [f"F{i}" for i in range(8)]
    for name in names:
        body = " ".join(random_source.choice(names) + "()"
                        for _ in range(random_source.randrange(3)))
        lines.append(f"#define {name}() {body}\n")
    lines.append("#define ALIAS F0\nALIAS() " + " ".join(name + "()" for name in names) + "\n")
    examples.append("".join(lines))

# A long chain consumes source delimiters while completed frames disappear.
lines = [f"#define F{i}() F{i+1}\n" for i in range(200)]
lines.append("#define F200() 1\nF0" + "()" * 201 + "\n")
examples.append("".join(lines))

with tempfile.TemporaryDirectory(prefix="kcc-macro-oracle-") as directory:
    source = Path(directory) / "input.c"
    expanded = Path(directory) / "expanded.c"
    for text in examples:
        source.write_text(text)
        reference = subprocess.run(host + ["-std=c2x", "-E", "-P", str(source)],
                                   capture_output=True, text=True, timeout=5)
        assert reference.returncode == 0, (text, reference.stderr)
        expanded.write_text(reference.stdout)
        actual = subprocess.run([str(driver), str(source)],
                                capture_output=True, text=True, timeout=5)
        expected = subprocess.run([str(driver), str(expanded)],
                                  capture_output=True, text=True, timeout=5)
        assert actual.returncode == expected.returncode == 0, (text, actual.stderr, expected.stderr)
        assert actual.stdout == expected.stdout, (text, actual.stdout, expected.stdout)
print(f"Macro token/spelling oracle passed ({len(examples)} cases; {host[0]})")

"""Exercise the driver contract, including bounded randomized arguments."""
import random
import subprocess
import tempfile
from pathlib import Path

compiler = Path(__file__).resolve().parents[1] / "build" / "kcc"

def run(arguments):
    return subprocess.run([str(compiler), *arguments], capture_output=True,
                          text=True, timeout=5)

result = run(["--help"])
assert result.returncode == 0 and "Usage:" in result.stdout
assert not result.stderr
result = run(["--version"])
assert result.returncode == 0 and "kcc milestone" in result.stdout
assert not result.stderr
for arguments in ([], ["input.c"], ["--unknown"], ["--help", "input.c"]):
    result = run(arguments)
    assert result.returncode == 1 and "error:" in result.stderr
    assert not result.stdout

random_source = random.Random(42)
for _ in range(40):
    arguments = ["x" + "".join(random_source.choices("abc-012", k=32))
                 for _ in range(random_source.randrange(5))]
    result = run(arguments)
    assert result.returncode == 1 and "error:" in result.stderr
result = run(["--tokens", "tests/corpus/lex/basic.c"])
assert result.returncode == 0 and "0:int\n" in result.stdout
assert result.stdout.endswith("29:eof\n") and not result.stderr
result = run(["--tokens", "build/nonexistent.c"])
assert result.returncode == 1 and result.stderr and not result.stdout
with tempfile.TemporaryDirectory(prefix="kcc-cli-phase-") as temporary:
    source = Path(temporary) / "spliced.c"
    text = b"in\\\nt ma\\\nin(vo\\\nid) { ret\\\nurn 4\\\n2; }\n"
    source.write_bytes(text)
    result = run(["--tokens", str(source)])
    expected = [(0, "int"), (text.index(b"ma"), "identifier"),
                (text.index(b"("), "("), (text.index(b"vo"), "void"),
                (text.index(b")"), ")"), (text.index(b"{"), "{"),
                (text.index(b"ret"), "return"), (text.index(b"4"), "integer"),
                (text.index(b";"), ";"), (text.index(b"}"), "}"), (len(text), "eof")]
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert result.stdout == "".join(f"{offset}:{kind}\n" for offset, kind in expected)
with tempfile.TemporaryDirectory(prefix="kcc-raw-cli-") as temporary:
    source = Path(temporary) / "raw.c"
    source.write_bytes(b"#define X 1e+2\nint\vX")
    result = run(["--pp-tokens", str(source)])
    expected = ("0:punctuator:1:0:1:0\n1:identifier:6:0:0:0\n"
                "8:identifier:1:1:0:0\n10:pp-number:4:1:0:0\n"
                "14:newline:1:0:0:0\n15:identifier:3:0:1:0\n"
                "19:identifier:1:1:0:1\n20:eof:0:0:0:0\n")
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert result.stdout == expected, result.stdout
    # Raw scanning neither dispatches a directive nor converts its number.
    result = run(["--tokens", str(source)])
    assert result.returncode == 1 and "unsupported numeric literal" in result.stderr
    source.write_bytes(b"in\\\nt ma\\\nin")
    result = run(["--pp-tokens", str(source)])
    assert result.returncode == 0 and not result.stderr
    assert result.stdout == ("0:identifier:3:0:1:0\n6:identifier:4:1:0:0\n"
                             "12:eof:0:0:0:0\n")
    source.write_bytes(b"\"unterminated\n")
    result = run(["--pp-tokens", str(source)])
    assert result.returncode == 1 and result.stderr.count("error:") == 1
    source.write_bytes(b"int main(void) { return 0; }\n")
    with open("/dev/full", "w") as full:
        result = subprocess.run([str(compiler), "--pp-tokens", str(source)],
                                stdout=full, stderr=subprocess.PIPE, timeout=5)
        assert result.returncode == 1
result = run(["--pp-tokens", "build/nonexistent.c"])
assert result.returncode == 1 and result.stderr and not result.stdout
with tempfile.TemporaryDirectory(prefix="kcc-directive-cli-") as temporary:
    source = Path(temporary) / "directives.c"
    text = b"#\nint main(void) { return 0; }\n%:"
    source.write_bytes(text)
    result = run(["--tokens", str(source)])
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert result.stdout.startswith("2:int\n") and "invalid" not in result.stdout
    assert result.stdout.endswith(f"{len(text)}:eof\n")
    result = run(["--pp-tokens", str(source)])
    assert result.returncode == 0 and result.stdout.startswith("0:punctuator:")
    source.write_bytes(b"#\n%:")
    result = run(["--tokens", str(source)])
    assert result.returncode == 0 and result.stdout == "4:eof\n" and not result.stderr
    result = run([str(source)])
    assert result.returncode == 1 and "error:" in result.stderr and not result.stdout
    source.write_bytes(b'#include X 12u .5 "txt"\nint')
    result = run(["--tokens", str(source)])
    assert result.returncode == 1 and result.stderr.count("error:") == 1
    assert result.stdout.startswith("0:invalid\n") and ":int\n" in result.stdout
    source.write_bytes(b"#\f")
    result = run(["--tokens", str(source)])
    assert result.returncode == 1 and result.stdout == "0:invalid\n2:eof\n"
    assert result.stderr.count("error:") == 1
with tempfile.TemporaryDirectory(prefix="kcc-function-macro-cli-") as temporary:
    source = Path(temporary) / "function-macro.c"
    text = b"#define F() 7\nF ( ) F\n"
    source.write_bytes(text)
    result = run(["--tokens", str(source)])
    call = text.index(b"F", text.index(b"\n"))
    bare = text.rindex(b"F")
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert result.stdout == f"{call}:integer\n{bare}:identifier\n{len(text)}:eof\n"
    source.write_bytes(b"#define F() 7\nF(1) int")
    result = run(["--tokens", str(source)])
    assert result.returncode == 1 and result.stderr.count("error:") == 1
    assert result.stdout.endswith("eof\n") and ":int\n" not in result.stdout
print("CLI tests passed (including 40 deterministic randomized cases)")

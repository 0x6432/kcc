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
print("CLI tests passed (including 40 deterministic randomized cases)")

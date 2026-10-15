"""Link separately compiled host/kcc objects to check the integer SysV ABI."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root / "build" / "kcc"
qbe = os.environ.get("QBE")
host_cc = os.environ.get("HOST_CC", "cc")


def run_checked(arguments):
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, (arguments, result.stdout, result.stderr)
    return result


def compile_kcc(directory, text):
    source = directory / "kcc input.c"
    il = directory / "kcc output.ssa"
    assembly = directory / "kcc output.s"
    object_file = directory / "kcc output.o"
    source.write_text(text)
    result = run_checked([str(compiler), str(source)])
    assert not result.stderr, result.stderr
    il.write_text(result.stdout)
    run_checked([qbe, "-t", "amd64_sysv", "-o", str(assembly), str(il)])
    run_checked([host_cc, "-c", str(assembly), "-o", str(object_file)])
    return object_file


def link_and_run(directory, kcc_text, host_text):
    kcc_object = compile_kcc(directory, kcc_text)
    host_source = directory / "host input.c"
    host_object = directory / "host output.o"
    executable = directory / "linked program"
    host_source.write_text(host_text)
    # Keep objects separate so the host cannot inline kcc functions or vice versa.
    run_checked([host_cc, "-std=c2x", "-O2", "-Wall", "-Wextra", "-Werror",
                 "-c", str(host_source), "-o", str(host_object)])
    run_checked([host_cc, str(kcc_object), str(host_object), "-o", str(executable)])
    run_checked([str(executable)])


def balanced_sum(terms):
    # A 128-term left-deep sum would exceed the compiler's expression bound.
    if not terms:
        return "37"
    if len(terms) == 1:
        return terms[0]
    middle = len(terms) // 2
    return f"({balanced_sum(terms[:middle])}+{balanced_sum(terms[middle:])})"


def check_argument_count(directory, count):
    parameters = ",".join(f"int a{i}" for i in range(count)) or "void"
    values = [((i * 7) % 31) - 15 for i in range(count)]
    other_values = [((i * 11) % 23) - 6 for i in range(count)]
    arguments = ",".join(str(value) for value in values)
    other_arguments = ",".join(str(value) for value in other_values)
    expression = balanced_sum([f"a{i}*{i+1}" for i in range(count)])
    expected = sum(value * (i + 1) for i, value in enumerate(values)) if count else 37
    other_expected = sum(value * (i + 1) for i, value in enumerate(other_values)) if count else 37
    definition = f"int mix({parameters}) {{ return {expression}; }}"
    declaration = f"int mix({parameters});"
    caller = ("int main(void) { int guard=913; "
              f"int first=mix({arguments}); int second=mix({other_arguments}); "
              f"return first!=({expected}) || second!=({other_expected}) || guard!=913; }}")
    link_and_run(directory, definition, declaration + caller)
    link_and_run(directory, declaration + caller, definition)


def check_signed_values(directory):
    definition = "int identity(int x) { return x; }"
    caller = ("int identity(int); int main(void) { "
              "if(identity(-2147483647-1)!=(-2147483647-1)) return 1; "
              "if(identity(2147483647)!=2147483647) return 2; "
              "if(identity(-1)!=-1) return 3; return 0; }")
    link_and_run(directory, definition, caller)
    link_and_run(directory, caller, definition)


def check_cross_compiler_recursion(directory):
    kcc_text = ("int host_odd(int); int kcc_even(int n) { "
                "if(n==0) return 1; return host_odd(n-1); }")
    host_text = ("int kcc_even(int); int host_odd(int n) { "
                 "if(n==0) return 0; return kcc_even(n-1); } "
                 "int main(void) { return kcc_even(18)!=1 || kcc_even(19)!=0 "
                 "|| host_odd(19)!=1; }")
    link_and_run(directory, kcc_text, host_text)


def check_unresolved_symbol(directory):
    object_file = compile_kcc(directory,
                              "int missing(int); int main(void) { return missing(1); }")
    result = subprocess.run([host_cc, str(object_file), "-o", str(directory / "unresolved")],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode != 0 and "missing" in result.stderr, result.stderr


if qbe:
    with tempfile.TemporaryDirectory(prefix="kcc-abi-") as temporary:
        directory = Path(temporary)
        for count in (0, 1, 2, 6, 7, 8, 12, 128):
            check_argument_count(directory, count)
        check_signed_values(directory)
        check_cross_compiler_recursion(directory)
        check_unresolved_symbol(directory)
    print(f"Separate-object integer ABI tests passed with {host_cc}")
else:
    print("Separate-object ABI tests skipped (set QBE to enable)")

"""Opt-in GCC 12+ zero-width separator ABI; cross-calls only on matching hosts."""
from pathlib import Path
import re
import subprocess
import tempfile
from unittest.mock import patch
from test_bit_fields import ROOT, HOST, KCC
from test_zero_width_legacy_float_abi import run_suite


def gcc12_or_newer():
    # cc may hide GCC in --version; Clang may mention a GCC installation.
    version = subprocess.run([HOST, '-v'], text=True, capture_output=True, timeout=10)
    match = re.search(r'^gcc version (\d+)(?:\.|\s)', version.stdout + version.stderr, re.MULTILINE)
    return version.returncode == 0 and bool(match) and int(match.group(1)) >= 12


def check_host_detection():
    cases = [(0, 'gcc version 11.5.0 (GCC)\n', False),
             (0, 'gcc version 12.1.0 (GCC)\n', True),
             (0, 'gcc version 14.2.1 (GCC)\n', True),
             (0, 'clang version 18.1.8\nSelected GCC installation: /usr/lib/gcc\n', False),
             (1, 'gcc version 14.2.1 (GCC)\n', False)]
    for code, stderr, expected in cases:
        result = subprocess.CompletedProcess([], code, stdout='', stderr=stderr)
        with patch('subprocess.run', return_value=result):
            assert gcc12_or_newer() == expected, (stderr, expected)


def main():
    check_host_detection()
    compare_host = gcc12_or_newer()
    options = ('--gcc12-zero-width-abi',)
    run_suite(options, compare_host)
    with tempfile.TemporaryDirectory(prefix='gcc12-mode-', dir=ROOT/'build') as tmp:
        source = Path(tmp)/'source.c'
        source.write_text('struct S {float a; unsigned :0; float b;}; struct S f(struct S s){return s;}\n')
        result = subprocess.run([str(KCC), str(source)], capture_output=True, text=True, timeout=15)
        assert result.returncode == 1 and not result.stdout and 'aggregate ABI unsupported' in result.stderr, result.stderr
        result = subprocess.run([str(KCC), *options, str(source)], capture_output=True, text=True, timeout=15)
        assert result.returncode == 0 and result.stdout, result.stderr
        for flags in (('--legacy-clang-abi', *options), (*options, '--legacy-clang-abi'),
                      (*options, '--tokens'), (*options, '--pp-tokens')):
            result = subprocess.run([str(KCC), *flags, str(source)], capture_output=True, text=True, timeout=15)
            assert result.returncode != 0 and not result.stdout, (flags, result.stdout, result.stderr)
        # Warning and GCC 12 mode are compatible; warning must not change IL.
        source.write_text('struct S { float a; unsigned :0; unsigned :1; float b; }; struct S f(struct S s){return s;}\n')
        plain = subprocess.run([str(KCC), *options, str(source)], capture_output=True, text=True, timeout=15)
        warned = subprocess.run([str(KCC), *options, '--warn-legacy-clang-abi', str(source)], capture_output=True, text=True, timeout=15)
        assert plain.returncode == warned.returncode == 0 and plain.stdout == warned.stdout and plain.stdout
        assert not plain.stderr and 'warning: aggregate with unnamed bit-field may be incompatible' in warned.stderr
    print(f'GCC 12+ zero-width ABI: 216 layouts, 119 unnamed-field layouts, 480 nested layouts (240 named-field), pressure/variadic and CLI boundaries passed; host cross-calls: {"GCC 12+" if compare_host else "not run (self-calls only)"}')


if __name__ == '__main__':
    main()

"""Adversarial controls for the CI duplicate-test coverage check."""
import importlib.util
from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ci_coverage', root / 'scripts/check_ci_test_coverage.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original = (root / 'Makefile').read_text()
assert module.check(original) > 0

mutations = (
    'ifeq (1,1)\n' + original + '\nendif\n',
    'include arbitrary.mk\n' + original,
    '$(eval hidden)\n' + original,
    'test test-codegen: unexpected-prerequisite\n' + original,
    '.ONESHELL:\n' + original,
    # Removing or changing even one command must fail.
    original.replace('\tpython3 tests/test_compile.py\n\tQBE="$(QBE)" python3 tests/test_abi.py\n',
                     '\tpython3 tests/test_compile.py\n', 1),
    original.replace('\tpython3 tests/test_compile.py\n', '\tpython3 tests/test_compile.py --different\n', 1),
    # Duplicate codegen work must not be hidden by set comparison.
    original.replace('\tQBE="$(QBE)" python3 tests/test_abi.py\n',
                     '\tQBE="$(QBE)" python3 tests/test_abi.py\n\tQBE="$(QBE)" python3 tests/test_abi.py\n', 1),
    original.replace('\tpython3 tests/test_compile.py\n', '\tpython3 tests/test_compile.py\nifeq (1,1)\n', 1),
    original.replace('test: export KCC_SOURCE := $(CURDIR)', 'test: export KCC_SOURCE := wrong', 1),
    original.replace('test: export QBE := $(QBE)', 'test: export QBE := wrong', 1),
    original.replace('test: build/test_bitint build/pp_oracle build/kcc',
                     'test: build/test_bitint build/pp_oracle', 1),
    original.replace('test: build/test_bitint', 'test: extra-dependency \\\n build/test_bitint', 1),
    original.replace('\tpython3 tests/test_compile.py\n', '\tpython3 tests/test_compile.py \\\n', 1),
)
for i, mutant in enumerate(mutations):
    try:
        module.check(mutant)
    except module.CoverageError:
        continue
    raise AssertionError(f'coverage mutant {i} was accepted')
print(f'CI coverage guard: {len(mutations)} missing/changed/duplicate/environment/shape mutants rejected')

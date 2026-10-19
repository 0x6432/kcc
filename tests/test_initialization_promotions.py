"""M17 exact legacy refusals promoted to mandatory acceptance/backend evidence.

KCC=... HOST_CC=... CLANG_CC=... QBE=... python3 tests/test_initialization_promotions.py
Default mode REQUIRES QBE: each unchanged per-origin original must compile with
KCC and produce fresh QBE assembly and real ELF. Defined original main executes
unchanged at its original exit value. --native-only never claims KCC coverage.
No keyword rewriting, synthesized main, native UB execution or permissive stderr.
Legacy GCC's exact per-source C23 empty-brace gaps are counted NOT agreements.
"""
import argparse
import ast
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from test_integer_initializers import (
    producer, invoke, elf_objects, native_diagnostics, clang_style,
    harness_self_test as producer_self_test,
)
from test_null_initializers import native_compilers, compiler_selection_self_test
from test_address_offsets import OffsetRelocations, OffsetReference

ROOT = Path(__file__).resolve().parents[1]
KCC = Path(os.environ.get('KCC', ROOT / 'build' / 'kcc'))
HOST = os.environ.get('HOST_CC', 'cc')
QBE = os.environ.get('QBE') or shutil.which('qbe')
# Exact origin/text mapping is committed, not loaded from a development audit.
# objects: name -> [byte width, alignment, external binding, initial bytes hex].
CASES = json.loads(r'''
[
  {
    "origin": "test_address_offsets.py",
    "baseline_line": 343,
    "text": "extern int target[3]; int *cell=1?target+1:target;",
    "exit": null,
    "objects": {
      "cell": [
        8,
        8,
        true,
        "0000000000000000"
      ]
    },
    "relocations": {
      "cell": [
        "target",
        4
      ]
    }
  },
  {
    "origin": "test_direct_address_initializers.py",
    "baseline_line": 309,
    "text": "int target; int *cell=1?&target:&target;",
    "exit": null,
    "objects": {
      "target": [
        4,
        4,
        true,
        "00000000"
      ],
      "cell": [
        8,
        8,
        true,
        "0000000000000000"
      ]
    },
    "relocations": {
      "cell": [
        "target",
        0
      ]
    }
  },
  {
    "origin": "test_direct_address_initializers.py",
    "baseline_line": 315,
    "text": "int target; _Bool cell=&target;",
    "exit": null,
    "objects": {
      "target": [
        4,
        4,
        true,
        "00000000"
      ],
      "cell": [
        1,
        1,
        true,
        "01"
      ]
    },
    "pointer_bool_warning": true
  },
  {
    "origin": "test_extern_arrays.py",
    "baseline_line": 236,
    "text": "static int a[2]={40,2};",
    "exit": null,
    "objects": {
      "a": [
        8,
        4,
        false,
        "2800000002000000"
      ]
    }
  },
  {
    "origin": "test_extern_arrays.py",
    "baseline_line": 237,
    "text": "int a[2]={40,2};",
    "exit": null,
    "objects": {
      "a": [
        8,
        4,
        true,
        "2800000002000000"
      ]
    }
  },
  {
    "origin": "test_extern_arrays.py",
    "baseline_line": 238,
    "text": "extern int a[2]={40,2};",
    "exit": null,
    "objects": {
      "a": [
        8,
        4,
        true,
        "2800000002000000"
      ]
    },
    "extern_warning": "a"
  },
  {
    "origin": "test_extern_arrays.py",
    "baseline_line": 239,
    "text": "extern int a[]={40,2};",
    "exit": null,
    "objects": {
      "a": [
        8,
        4,
        true,
        "2800000002000000"
      ]
    },
    "extern_warning": "a"
  },
  {
    "origin": "test_extern_arrays.py",
    "baseline_line": 240,
    "text": "typedef int Row[2]; extern Row a={40,2};",
    "exit": null,
    "objects": {
      "a": [
        8,
        4,
        true,
        "2800000002000000"
      ]
    },
    "extern_warning": "a"
  },
  {
    "origin": "test_integer_initializers.py",
    "baseline_line": 237,
    "text": "int cell[2]={1,2};",
    "exit": null,
    "objects": {
      "cell": [
        8,
        4,
        true,
        "0100000002000000"
      ]
    }
  },
  {
    "origin": "test_integer_initializers.py",
    "baseline_line": 238,
    "text": "int cell[]={1,2};",
    "exit": null,
    "objects": {
      "cell": [
        8,
        4,
        true,
        "0100000002000000"
      ]
    }
  },
  {
    "origin": "test_integer_initializers.py",
    "baseline_line": 238,
    "text": "int cell={42};",
    "exit": null,
    "objects": {
      "cell": [
        4,
        4,
        true,
        "2a000000"
      ]
    }
  },
  {
    "origin": "test_integer_initializers.py",
    "baseline_line": 238,
    "text": "int cell={};",
    "exit": null,
    "objects": {
      "cell": [
        4,
        4,
        true,
        "00000000"
      ]
    },
    "gcc_empty_gap": [
      [
        "error",
        "ISO C forbids empty initializer braces [-Wpedantic]"
      ],
      [
        "error",
        "empty scalar initializer"
      ],
      [
        "note",
        "(near initialization for 'cell')"
      ]
    ]
  },
  {
    "origin": "test_null_initializers.py",
    "baseline_line": 183,
    "text": "int *cell=(1?(int *)0:(int *)0);",
    "exit": null,
    "objects": {
      "cell": [
        8,
        8,
        true,
        "0000000000000000"
      ]
    }
  },
  {
    "origin": "test_null_initializers.py",
    "baseline_line": 198,
    "text": "_Bool cell=(int *)0;",
    "exit": null,
    "objects": {
      "cell": [
        1,
        1,
        true,
        "00"
      ]
    }
  },
  {
    "origin": "test_record_layout.py",
    "baseline_line": 97,
    "text": "struct R { int x; }; struct R cell={42};",
    "exit": null,
    "objects": {
      "cell": [
        4,
        4,
        true,
        "2a000000"
      ]
    }
  },
  {
    "origin": "test_record_runtime.py",
    "baseline_line": 358,
    "text": "struct S { int x; }; struct S s={1};",
    "exit": null,
    "objects": {
      "s": [
        4,
        4,
        true,
        "01000000"
      ]
    }
  },
  {
    "origin": "test_static_arrays.py",
    "baseline_line": 102,
    "text": "static int items[3]={1,2,3};",
    "exit": null,
    "objects": {
      "items": [
        12,
        4,
        false,
        "010000000200000003000000"
      ]
    }
  },
  {
    "origin": "test_static_arrays.py",
    "baseline_line": 103,
    "text": "static int items[3]={};",
    "exit": null,
    "objects": {
      "items": [
        12,
        4,
        false,
        "000000000000000000000000"
      ]
    },
    "gcc_empty_gap": [
      [
        "error",
        "ISO C forbids empty initializer braces [-Wpedantic]"
      ]
    ]
  },
  {
    "origin": "test_static_objects.py",
    "baseline_line": 141,
    "text": "static int cell={};",
    "exit": null,
    "objects": {
      "cell": [
        4,
        4,
        false,
        "00000000"
      ]
    },
    "gcc_empty_gap": [
      [
        "error",
        "ISO C forbids empty initializer braces [-Wpedantic]"
      ],
      [
        "error",
        "empty scalar initializer"
      ],
      [
        "note",
        "(near initialization for 'cell')"
      ]
    ]
  },
  {
    "origin": "test_string_literals.py",
    "baseline_line": 146,
    "text": "int main(void) { char a[2]=\"x\"; return 0; }",
    "exit": 0,
    "objects": {}
  },
  {
    "origin": "test_tentative_arrays.py",
    "baseline_line": 258,
    "text": "int items[3]={0,0,0};",
    "exit": null,
    "objects": {
      "items": [
        12,
        4,
        true,
        "000000000000000000000000"
      ]
    }
  },
  {
    "origin": "test_tentative_arrays.py",
    "baseline_line": 259,
    "text": "int items[]={40,2};",
    "exit": null,
    "objects": {
      "items": [
        8,
        4,
        true,
        "2800000002000000"
      ]
    }
  },
  {
    "origin": "test_tentative_arrays.py",
    "baseline_line": 260,
    "text": "extern int items[3]={0,0,0};",
    "exit": null,
    "objects": {
      "items": [
        12,
        4,
        true,
        "000000000000000000000000"
      ]
    },
    "extern_warning": "items"
  },
  {
    "origin": "test_tentative_arrays.py",
    "baseline_line": 261,
    "text": "typedef int Row[3]; Row items={0,0,0};",
    "exit": null,
    "objects": {
      "items": [
        12,
        4,
        true,
        "000000000000000000000000"
      ]
    }
  }
]
''' )


NATIVE_GAPS = {(c['origin'], c['text']): tuple(tuple(pair) for pair in c['gcc_empty_gap'])
               for c in CASES if 'gcc_empty_gap' in c}


def verify_mapping():
    assert len(CASES) == 24
    assert len({(c['origin'], c['text']) for c in CASES}) == len(CASES)
    assert len({c['origin'] for c in CASES}) == 11
    for case in CASES:
        assert case['origin'] != 'test_boolean_keywords.py'
        assert case['exit'] == (0 if re.search(r'\bint main\(void\)', case['text']) else None)
        # A mapped source cannot quietly remain a refusal in its origin suite.
        tree = ast.parse((ROOT / 'tests' / case['origin']).read_text())
        assert not any(isinstance(n, ast.Constant) and n.value == case['text']
                       for n in ast.walk(tree)), case


def native_warnings(case, clang):
    if clang and case.get('pointer_bool_warning'):
        return (('warning', "address of 'target' will always evaluate to 'true' [-Wpointer-bool-conversion]"),)
    name = case.get('extern_warning')
    if not name:
        return ()
    return (('warning', "'extern' variable has an initializer [-Wextern-initializer]"
             if clang else f"'{name}' initialized and declared 'extern'"),)


def exact_native_gap(case, result, source, output, clang):
    expected = NATIVE_GAPS.get((case.get('origin'), case.get('text')))
    return (not clang and expected is not None and result.returncode == 1
            and not result.stdout and not output.exists()
            and source.read_text() == case['text'] + '\n'
            and native_diagnostics(result.stderr, source, case['text'], False)
            == expected)


def il_layout(text, case):
    """Prove named QBE label extents before supplying widths to ELF readers.

    Accept equivalent scalar/byte/zero encodings, NOT arbitrary initializer IL.
    Relocation identity/addends are independently checked in the actual ELF.
    """
    declarations = list(re.finditer(
        r'^(export )?data \$([A-Za-z_.][A-Za-z_0-9.]*) = align ([0-9]+) \{([^{}]*)\}',
        text, re.M))
    names = [m[2] for m in declarations]
    assert len(names) == len(set(names)), (case, names)
    expected_names = set(case['objects'])
    assert set(names) - expected_names <= {n for n in names if n.startswith('.Lkcc.string.')}, (case, names)
    for name, (width, alignment, public, contents) in case['objects'].items():
        found = [m for m in declarations if m[2] == name]
        assert len(found) == 1, (case, name, text)
        item = found[0]
        assert bool(item[1]) == public and int(item[3]) == alignment, (case, item[0])
        data, relocations = bytearray(), []
        for fragment in item[4].split(','):
            fragment = fragment.strip()
            if not fragment:
                continue
            field = re.fullmatch(r'([bhwlz])\s+(.+)', fragment)
            assert field, (case, fragment)
            encoding, value = field.groups()
            if encoding == 'z':
                assert value.isdecimal() and 0 < int(value) <= width, (case, fragment)
                data.extend(bytes(int(value)))
                continue
            size = {'b': 1, 'h': 2, 'w': 4, 'l': 8}[encoding]
            symbol = re.fullmatch(r'\$([A-Za-z_][A-Za-z_0-9.]*)(?:\s*\+\s*([0-9]+))?', value)
            if symbol:
                assert size == 8, (case, fragment)
                relocations.append((len(data), symbol[1], int(symbol[2] or 0)))
                data.extend(bytes(size))
            else:
                assert re.fullmatch(r'-?[0-9]+', value), (case, fragment)
                data.extend((int(value) % (1 << (8 * size))).to_bytes(size, 'little'))
        assert len(data) == width and data.hex() == contents, (case, name, data, contents)
        target = case.get('relocations', {}).get(name)
        assert relocations == ([(0, target[0], target[1])] if target else []), (case, relocations)


def check_kcc_elf(path, case):
    widths = {n: spec[0] for n, spec in case['objects'].items()}
    records = elf_objects(path, widths)
    relocations = OffsetRelocations(path)  # Also validates ELF headers/sections/symbol tables.
    for name, (width, alignment, public, contents) in case['objects'].items():
        found = records.get(name, [])
        assert len(found) == 1, (case, name, found)
        binding, size, actual_alignment, offset, data = found[0]
        assert (binding, size, data.hex()) == (int(public), width, contents), (case, name, found)
        assert actual_alignment >= alignment and offset % alignment == 0, (case, name, found)
        if name not in case.get('relocations', {}):
            symbol = relocations.symbol(name)
            assert not any(r['section'] == symbol['section']
                           and symbol['value'] <= r['offset'] < symbol['value'] + width
                           for r in relocations.relocations), (case, name, 'unexpected relocation')
    references = {name: OffsetReference('object', target, byte_addend=addend)
                  for name, (target, addend) in case.get('relocations', {}).items()}
    relocations.check(references)


def run_original(linker, obj, executable, expected):
    producer([linker, obj, '-o', executable], executable)
    result = invoke([executable])
    assert (result.returncode, result.stdout, result.stderr) == (expected, '', ''), result


def controls(directory):
    """Reject wrong-origin gaps, polluted diagnostics and stale/missing artifacts."""
    compiler_selection_self_test(directory)
    producer_self_test(directory)
    source, output = directory / 'gap.c', directory / 'gap.o'
    cases = [c for c in CASES if 'gcc_empty_gap' in c]
    assert len(cases) == 3
    for case in cases:
        source.write_text(case['text'] + '\n')
        output.unlink(missing_ok=True)
        stderr = ''.join(f'{source}:1:1: {kind}: {message}\n'
                         for kind, message in case['gcc_empty_gap'])
        good = subprocess.CompletedProcess([], 1, '', stderr)
        assert exact_native_gap(case, good, source, output, False)
        for status in (0, 2, 127, -6, -9, -11):
            assert not exact_native_gap(case, subprocess.CompletedProcess([], status, '', stderr), source, output, False)
        for extra in ('UNRELATED STDERR\n', f'{source}:1:1: error: unrelated\n',
                      f'{source}:1:1: warning: unrelated\n', f'{source}:1:1: note: unrelated\n',
                      'internal compiler error: broken\n', '1 error generated.\n'):
            bad = subprocess.CompletedProcess([], 1, '', stderr + extra)
            assert not exact_native_gap(case, bad, source, output, False)
        for out, err in [('unexpected stdout', stderr), ('', ''), ('', stderr.replace('error:', 'fatal error:', 1))]:
            assert not exact_native_gap(case, subprocess.CompletedProcess([], 1, out, err), source, output, False)
        assert not exact_native_gap(case, good, source, output, True)
        assert not exact_native_gap(dict(case, origin='test_unrelated.py'), good, source, output, False)
        unrelated = dict(case, text='int unrelated;', gcc_empty_gap=case['gcc_empty_gap'])
        assert not exact_native_gap(unrelated, good, source, output, False)
        source.write_text('int unrelated;\n')
        assert not exact_native_gap(case, good, source, output, False)
        source.write_text(case['text'] + '\n')
        output.write_bytes(b'stale')
        assert not exact_native_gap(case, good, source, output, False)
        output.unlink()
    # A mutant wrong byte, extent, linkage or relocation can never pass IL proof.
    case = next(c for c in CASES if c['text'] == 'int cell={42};')
    valid = 'export data $cell = align 4 { w 42 }\n'
    il_layout(valid, case)
    for bad in (valid.replace('42', '41'), valid.replace('w 42', 'b 42'),
                valid.replace('align 4', 'align 8'), valid.replace('export ', ''),
                valid + valid, valid.replace('w 42', 'l $wrong')):
        try:
            il_layout(bad, case)
        except AssertionError:
            pass
        else:
            raise AssertionError(('bad IL accepted', bad))
    print('Promotion harness controls passed: exact complete diagnostics, freshness, mapping and IL evidence')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-only', action='store_true')
    parser.add_argument('--harness-self-test', action='store_true')
    options = parser.parse_args()
    verify_mapping()
    with tempfile.TemporaryDirectory(prefix='kcc initialization promotions ') as tmp:
        directory = Path(tmp)
        controls(directory)
        if options.harness_self_test:
            return
        additional = os.environ.get('CLANG_CC') or shutil.which('clang')
        compilers = native_compilers(HOST, additional)
        if not options.native_only:
            assert QBE and shutil.which(str(QBE)), 'QBE is mandatory for promotion coverage; set QBE or use --native-only'
        print('Native tools:', ', '.join(compilers))
        if not additional and not clang_style(HOST):
            print('Additional Clang unavailable: NOT counted as a comparison')
        files = [directory / name for name in ('original.c', 'k.ssa', 'k.s', 'k.o', 'native.o', 'program')]
        source, il, assembly, obj, native_obj, executable = files
        kcc_acceptances = qbe_objects = original_runs = 0
        native_counts = {cc: {'agreements': 0, 'empty_brace_gaps': 0, 'runs': 0} for cc in compilers}
        for case in CASES:
            source.write_text(case['text'] + '\n')
            if not options.native_only:
                result = invoke([KCC, source])
                assert result.returncode == 0 and not result.stderr and result.stdout, (case, result)
                assert source.read_text() == case['text'] + '\n'
                kcc_acceptances += 1
                il_layout(result.stdout, case)
                il.write_text(result.stdout)
                producer([QBE, '-t', 'amd64_sysv', '-o', assembly, il], assembly)
                producer([HOST, '-c', assembly, '-o', obj], obj)
                check_kcc_elf(obj, case)
                qbe_objects += 1
                if case['exit'] is not None:
                    run_original(HOST, obj, executable, case['exit'])
                    original_runs += 1
            for cc in compilers:
                native_obj.unlink(missing_ok=True)
                command = [cc, '-std=c2x', '-pedantic-errors', '-fno-common', '-O0', '-c', source, '-o', native_obj]
                result = invoke(command)
                if result.returncode:
                    assert exact_native_gap(case, result, source, native_obj, clang_style(cc)), (cc, case, result)
                    native_counts[cc]['empty_brace_gaps'] += 1
                    continue
                # Reuse hardened complete-stream validation, but do not invoke
                # the producer again and silently replace the checked result.
                assert not result.stdout and native_obj.is_file() and native_obj.stat().st_size > 0, (cc, case, result)
                actual = native_diagnostics(result.stderr, source, case['text'], clang_style(cc))
                assert actual == native_warnings(case, clang_style(cc)), (cc, case, result.stderr)
                OffsetRelocations(native_obj)  # Fresh actual ELF, never syntax-only acceptance.
                native_counts[cc]['agreements'] += 1
                if case['exit'] is not None:
                    run_original(cc, native_obj, executable, case['exit'])
                    native_counts[cc]['runs'] += 1
        print(f'Initialization legacy promotions: {len(CASES)} exact originals across 11 origins; '
              f'KCC acceptances {kcc_acceptances}; mandatory fresh QBE/ELF {qbe_objects}; '
              f'unchanged defined original runtimes {original_runs}')
        if options.native_only:
            print('Native-only lane: NO KCC/backend coverage claimed')
        else:
            assert kcc_acceptances == qbe_objects == len(CASES)
            assert original_runs == sum(c['exit'] is not None for c in CASES)
        for cc, counts in native_counts.items():
            assert counts['agreements'] + counts['empty_brace_gaps'] == len(CASES)
            print(f"{cc}: unchanged native ELF agreements {counts['agreements']}; "
                  f"exact C23 empty-brace gaps {counts['empty_brace_gaps']} (NOT agreements); "
                  f"unchanged original runtimes {counts['runs']}")


if __name__ == '__main__':
    main()

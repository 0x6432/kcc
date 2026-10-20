"""M17 exact legacy refusals promoted to mandatory acceptance/backend evidence.

KCC=... HOST_CC=... CLANG_CC=... QBE=... python3 tests/test_initialization_promotions.py
Default mode REQUIRES QBE: each byte-unchanged per-origin original must compile with
KCC and produce fresh QBE assembly and real ELF. The original main executes in KCC unchanged at its original exit value;
its missing-final-LF source form is a documented extension, NOT a strict-C23 runtime agreement. --native-only never claims KCC coverage.
Actual baseline writer bytes are pinned, including whether a final LF exists.
No keyword rewriting, synthesized main, native UB execution or permissive stderr.
Legacy GCC's exact per-source C23 empty-brace gaps are counted NOT agreements.
The exact observed Clang18.1.3 no-final-LF source protocol is NOT an agreement.
"""
import argparse
import ast
import copy
import hashlib
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
    },
    "source_final_newline": true,
    "source_sha256": "6acde69214f4b1b6e586d2c70409c4ae3a8d424a1d7d81e0f239302d86fc9215"
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
    },
    "source_final_newline": true,
    "source_sha256": "9543ebf12737ea2c15cd5ec89cfe24745d6262871c0797f428e0fa261d73e620"
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
    "pointer_bool_warning": true,
    "source_final_newline": true,
    "source_sha256": "65ab569496974e44b7c2ef215a0b9d1da66faa7c081b209f6d188fb718ffe05b"
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
    },
    "source_final_newline": true,
    "source_sha256": "bdcbd5943254d60e1cb65155e078f7e8ae39ef7dc111ea86409c687849be5ff1"
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
    },
    "source_final_newline": true,
    "source_sha256": "de619388ced0999b1f7ccdf6b305ee183a62474d8d8a990c2a6b7a4c34e41af8"
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
    "extern_warning": "a",
    "source_final_newline": true,
    "source_sha256": "2ce516dab9e3bc176dc733b995d3642323d28a6120c57ca79c5298afe317f897"
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
    "extern_warning": "a",
    "source_final_newline": true,
    "source_sha256": "910127a540674236f6f32857e2eb124574e3ed07d2be0e506982e11eac0744c9"
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
    "extern_warning": "a",
    "source_final_newline": true,
    "source_sha256": "03a06f602e556252e18344352498979b23d73e22a5b6962084750ae7af1784db"
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
    },
    "source_final_newline": true,
    "source_sha256": "b0ce9a7d4df71e85c720e86c908c7de9d7488273b2008d1834e8fb68b6255dff"
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
    },
    "source_final_newline": true,
    "source_sha256": "38e917ba58c315824ba12e65834612ea8f65ff767073b4e8785c9f20bdbbcef2"
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
    },
    "source_final_newline": true,
    "source_sha256": "bdf92d7c2f7723df6ddf1ba3b6a8e0e27830d3b8a2bd711dd30a4d503183ede3"
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
    ],
    "source_final_newline": true,
    "source_sha256": "6a5eb6ba5b8724f0e2d4cb90e5dc83e886949563379d7320bbfb8d445b0a4dbd"
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
    },
    "source_final_newline": true,
    "source_sha256": "a6818b6d364f9d4157fbf36ad4a301e79d793de56c76cbdff7eb00ab32f1e471"
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
    },
    "source_final_newline": true,
    "source_sha256": "27fa672d714b70810a1db895256ce3e856245c28741377290d0d98edfbe5aae3"
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
    },
    "source_final_newline": true,
    "source_sha256": "97944980aca1afdadea6603ee4abab4a6a2a170640250f8dd4b466b850ca4b2b"
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
    },
    "source_final_newline": true,
    "source_sha256": "965c76f4f9d78b32fc61d24217bcf9c68f0f7f76200c4dac0b19977bbeebe531"
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
    },
    "source_final_newline": true,
    "source_sha256": "a8c4a93e9cccfdb0d78314ff4ced3e6918f415efd0d90eac5e86b29ec666b8c9"
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
    ],
    "source_final_newline": true,
    "source_sha256": "440f11c503c5981174a43a4eddeec907beaab363b7c9b9fe1a39d2a958603500"
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
    ],
    "source_final_newline": true,
    "source_sha256": "7cf7de06bfe48c9eb230a0d4ec147bec7ac4d9e4354627539b49a6dea7648b73"
  },
  {
    "origin": "test_string_literals.py",
    "baseline_line": 146,
    "text": "int main(void) { char a[2]=\"x\"; return 0; }",
    "exit": 0,
    "objects": {},
    "source_final_newline": false,
    "source_sha256": "d6295d673cb96b73394d774899fb0f717572e4f8fecf12a0478efe04056aa0ac"
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
    },
    "source_final_newline": true,
    "source_sha256": "28d33ebdfb8cab8245c02b66230e73d30c04fe57c7f84f7dfd70dc961cb81f95"
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
    },
    "source_final_newline": true,
    "source_sha256": "3bcd9b0dab532174ada19d6fb0d8ae2c9ae4b29813ac064124165c77a2ad7f4e"
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
    "extern_warning": "items",
    "source_final_newline": true,
    "source_sha256": "ef7320ca007dcfd65f743c14e0ac3b1d68338ffe64c0b76b765dc46620e97e09"
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
    },
    "source_final_newline": true,
    "source_sha256": "bee81fe5e07a028e3233545fc49d88f6c5dac41bde9dac1a1421a8ff17a0bbc5"
  },
  {
    "origin": "test_block_storage.py",
    "baseline_line": 407,
    "text": "int f(void) { static int cells[2]={1,2}; return cells[0]; }",
    "exit": null,
    "objects": {
      ".Lkcc.static.0": [
        8,
        4,
        false,
        "0100000002000000"
      ]
    },
    "private_function": "f",
    "source_final_newline": true,
    "source_sha256": "2f4573b3f645231fd58eab94b4cf5332012ab1c2c8f30bdf56c1d9c635fbcf36"
  },
  {
    "origin": "test_block_storage.py",
    "baseline_line": 408,
    "text": "int f(void) { static int cell={42}; return cell; }",
    "exit": null,
    "objects": {
      ".Lkcc.static.0": [
        4,
        4,
        false,
        "2a000000"
      ]
    },
    "private_function": "f",
    "source_final_newline": true,
    "source_sha256": "fab078657b78a51c2133fb840d894948267998dffc9f0c405c68688380925c83"
  }
]
''' )


# Captured actual baseline writer rules and exact file bytes, not normalized text.
# test_string_literals.py writes text verbatim; the other 25 append one LF.
ORIGINAL_FILES = {(c['origin'], c['text']): (c['source_final_newline'], c['source_sha256'])
                  for c in CASES}


def original_source_bytes(case):
    key = (case.get('origin'), case.get('text'))
    assert key in ORIGINAL_FILES, ('unmapped original source', key)
    newline, expected_hash = ORIGINAL_FILES[key]
    assert type(newline) is bool
    assert (case.get('source_final_newline'), case.get('source_sha256')) == (newline, expected_hash), ('changed writer binding', key)
    raw = (case['text'] + ('\n' if newline else '')).encode('utf-8')
    assert hashlib.sha256(raw).hexdigest() == expected_hash, ('original byte hash', key)
    return raw


def check_original_source(source, case):
    assert source.read_bytes() == original_source_bytes(case), ('changed original file bytes', case['origin'])


def original_source_controls(directory):
    source = directory / 'original-bytes.c'
    for case in CASES:
        raw = original_source_bytes(case)
        source.write_bytes(raw)
        check_original_source(source, case)
        mutations = [raw + b'\n', raw + b' ', b'\xef\xbb\xbf' + raw,
                     raw[:-1] if raw.endswith(b'\n') else raw + b'\r\n',
                     raw.replace(b';', b'; ', 1)]
        for bad in mutations:
            assert bad != raw
            source.write_bytes(bad)
            try:
                check_original_source(source, case)
            except AssertionError:
                pass
            else:
                raise AssertionError(('changed original bytes accepted', case['origin']))
        source.write_bytes(raw)
        for mutation in ('writer', 'hash', 'origin', 'text', 'writer-and-hash'):
            bad = dict(case)
            if mutation in ('writer', 'writer-and-hash'):
                bad['source_final_newline'] = not bad['source_final_newline']
            if mutation == 'hash': bad['source_sha256'] = '0' * 64
            if mutation == 'origin': bad['origin'] = 'test_unrelated.py'
            if mutation == 'text': bad['text'] += ' '
            if mutation == 'writer-and-hash':
                changed = (bad['text'] + ('\n' if bad['source_final_newline'] else '')).encode('utf-8')
                bad['source_sha256'] = hashlib.sha256(changed).hexdigest()
            try:
                original_source_bytes(bad)
            except AssertionError:
                pass
            else:
                raise AssertionError(('changed original mapping accepted', mutation))
    print('Original file-byte controls passed: 26 writer/hash bindings; added/removed LF and byte/mapping poisons')


NATIVE_GAPS = {(c['origin'], c['text']): tuple(tuple(pair) for pair in c['gcc_empty_gap'])
               for c in CASES if 'gcc_empty_gap' in c}


def verify_mapping():
    assert len(CASES) == 26
    assert len({(c['origin'], c['text']) for c in CASES}) == len(CASES)
    assert len({c['origin'] for c in CASES}) == 12
    for case in CASES:
        original_source_bytes(case)
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
            and source.read_bytes() == original_source_bytes(case)
            and native_diagnostics(result.stderr, source, case['text'], False)
            == expected)


EOF_ORIGINAL = ('test_string_literals.py', 'int main(void) { char a[2]="x"; return 0; }')


def eof_diagnostic(source, case):
    text = case['text']
    return (f'{source}:1:{len(text)+1}: error: no newline at end of file [-Werror,-Wnewline-eof]\n'
            f'    1 | {text}\n      | {" " * len(text)}^\n1 error generated.\n')


def exact_native_eof_gap(case, result, source, output, banner, version):
    # Actual observed source-format rejection, not a language/runtime agreement.
    return ((case.get('origin'), case.get('text')) == EOF_ORIGINAL
            and not case['source_final_newline']
            and source.read_bytes() == original_source_bytes(case)
            and (version.returncode, version.stdout, version.stderr) == (0, '18.1.3\n', '')
            and banner.returncode == 0 and not banner.stderr and banner.stdout.endswith('\n')
            and banner.stdout.splitlines()[0] == 'Ubuntu clang version 18.1.3 (1ubuntu1)'
            and result.returncode == 1 and not result.stdout and not output.exists()
            and result.stderr == eof_diagnostic(source, case))


def eof_gap_controls(directory):
    # Synthetic poison controls only; real observations are separate evidence.
    source, output = directory / 'eof-original.c', directory / 'eof-original.o'
    case = next(c for c in CASES if (c['origin'], c['text']) == EOF_ORIGINAL)
    source.write_bytes(original_source_bytes(case)); output.unlink(missing_ok=True)
    banner = subprocess.CompletedProcess([], 0, 'Ubuntu clang version 18.1.3 (1ubuntu1)\n', '')
    version = subprocess.CompletedProcess([], 0, '18.1.3\n', '')
    good = subprocess.CompletedProcess([], 1, '', eof_diagnostic(source, case))
    assert exact_native_eof_gap(case, good, source, output, banner, version)
    for status in (0, 2, 127, -6, -9, -11):
        assert not exact_native_eof_gap(case, subprocess.CompletedProcess([], status, '', good.stderr), source, output, banner, version)
    for out, err in [('noise', good.stderr), ('', ''), ('', good.stderr+'noise\n'),
                     ('', good.stderr.replace('1:44:', '1:43:')), ('', good.stderr.replace('^', '~')),
                     ('', good.stderr.replace('1 error generated.', '2 errors generated.'))]:
        assert not exact_native_eof_gap(case, subprocess.CompletedProcess([], 1, out, err), source, output, banner, version)
    for text in ('18', '18.1', '18.1.2', '18.1.4', '18.1.3junk', '18.1.3-lookalike', '18.1.3+lookalike', '018.1.3', '18.1.3\n\n'):
        assert not exact_native_eof_gap(case, good, source, output, banner, subprocess.CompletedProcess([], 0, text+'\n', ''))
    for text in ('clang version 18.1.3', 'gcc (GCC) 18.1.3', 'Ubuntu clang version 18.1.3 (1ubuntu1)-lookalike', 'Ubuntu clang version 18.1.3 (1ubuntu1)+lookalike', ''):
        assert not exact_native_eof_gap(case, good, source, output, subprocess.CompletedProcess([], 0, text+'\n', ''), version)
    for b, v in ((subprocess.CompletedProcess([], 1, banner.stdout, ''), version),
                 (subprocess.CompletedProcess([], 0, banner.stdout, 'noise'), version),
                 (banner, subprocess.CompletedProcess([], 1, version.stdout, '')),
                 (banner, subprocess.CompletedProcess([], 0, version.stdout, 'noise'))):
        assert not exact_native_eof_gap(case, good, source, output, b, v)
    for raw in (original_source_bytes(case)+b'\n', original_source_bytes(case)+b' ', b'int unrelated;'):
        source.write_bytes(raw)
        assert not exact_native_eof_gap(case, good, source, output, banner, version)
    source.write_bytes(original_source_bytes(case)); output.write_bytes(b'stale')
    assert not exact_native_eof_gap(case, good, source, output, banner, version)
    output.unlink()
    assert not exact_native_eof_gap(dict(case, origin='test_unrelated.py'), good, source, output, banner, version)
    print('Exact Clang18.1.3 EOF source protocol poisons passed (NOT agreement)')


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
    if case.get('private_function'):
        check_private_reference(relocations, case)


def check_private_reference(elf, case):
    """Require the exact retained canonical symbol, not any local at its address.

    GAS may express PC-relative relocation through a genuine section symbol.
    The x86-64 PC32 encoding addend is -4 for a reference to the object's start;
    this representation correction is not a permitted logical interior offset.
    """
    name = '.Lkcc.static.0'
    width = case['objects'][name][0]
    target, function = elf.symbol(name), elf.symbol(case['private_function'])
    assert [s['name'] for s in elf.symbols if s['name'].startswith('.Lkcc.static.')] == [name]
    assert target['binding'] == 0 and target['kind'] == 0 and target['size'] == 0
    assert 0 < target['section'] < len(elf.sections)
    section = elf.sections[target['section']]
    assert section[1] == 1 and section[2] & 3 == 3 and not section[2] & 4
    assert section[5] == width and target['value'] == 0, ('exact private extent', target, section)
    assert [s for s in elf.symbols if s['section'] == target['section'] and s['kind'] != 3] == [target]
    assert function['kind'] == 2 and function['binding'] == 1 and function['size'] > 0
    assert 0 < function['section'] < len(elf.sections)
    assert elf.sections[function['section']][2] & 4
    refs = [r for r in elf.relocations if r['section'] == function['section']]
    assert len(refs) == 1, ('one canonical function-address relocation', refs)
    ref = refs[0]
    assert function['value'] <= ref['offset'] and ref['offset'] + 4 <= function['value'] + function['size']
    assert ref['kind'] == 2, ('R_X86_64_PC32', ref)
    base = ref['symbol']
    if base['name'] == name:
        assert base == target and ref['addend'] == -4
    else:
        assert base['kind'] == 3 and base['binding'] == 0 and base['section'] == target['section']
        assert base['value'] + ref['addend'] + 4 == target['value']


def private_reference_controls(elf, case):
    """Poison actual freshly produced ELF metadata; no permissive local fallback."""
    check_private_reference(elf, case)
    for mutation in ('unrelated-base', 'wrong-addend', 'wrong-kind', 'wrong-offset',
                     'duplicate-relocation', 'missing-canonical', 'extra-owner', 'wrong-extent'):
        bad = copy.deepcopy(elf)
        ref = next(r for r in bad.relocations if r['section'] == bad.symbol('f')['section'])
        if mutation == 'unrelated-base':
            ref['symbol'] = dict(bad.symbol('.Lkcc.static.0'), name='unrelated.private', value=16)
            ref['addend'] = -20  # Same final address is NOT the same canonical base.
        elif mutation == 'wrong-addend':
            ref['addend'] += 4
        elif mutation == 'wrong-kind':
            ref['kind'] = 1
        elif mutation == 'wrong-offset':
            ref['offset'] = bad.symbol('f')['value'] + bad.symbol('f')['size']
        elif mutation == 'duplicate-relocation':
            bad.relocations.append(copy.deepcopy(ref))
        elif mutation == 'missing-canonical':
            bad.symbol('.Lkcc.static.0')['name'] = 'unrelated.private'
        elif mutation == 'extra-owner':
            bad.symbols.append(dict(bad.symbol('.Lkcc.static.0'), name='unrelated.private.owner'))
        else:
            index = bad.symbol('.Lkcc.static.0')['section']
            row = list(bad.sections[index]); row[5] += 4; bad.sections[index] = tuple(row)
        try:
            check_private_reference(bad, case)
        except AssertionError:
            pass
        else:
            raise AssertionError(('private ELF mutant accepted', mutation))


def run_original(linker, obj, executable, expected):
    producer([linker, obj, '-o', executable], executable)
    result = invoke([executable])
    assert (result.returncode, result.stdout, result.stderr) == (expected, '', ''), result


def controls(directory):
    """Reject wrong-origin gaps, polluted diagnostics and stale/missing artifacts."""
    compiler_selection_self_test(directory)
    producer_self_test(directory)
    original_source_controls(directory)
    eof_gap_controls(directory)
    source, output = directory / 'gap.c', directory / 'gap.o'
    cases = [c for c in CASES if 'gcc_empty_gap' in c]
    assert len(cases) == 3
    for case in cases:
        source.write_bytes(original_source_bytes(case))
        output.unlink(missing_ok=True)
        stderr = ''.join(f'{source}:1:1: {kind}: {message}\n'
                         for kind, message in case['gcc_empty_gap'])
        good = subprocess.CompletedProcess([], 1, '', stderr)
        assert exact_native_gap(case, good, source, output, False)
        for bad in (original_source_bytes(case)[:-1], original_source_bytes(case) + b'\n'):
            source.write_bytes(bad)
            assert not exact_native_gap(case, good, source, output, False)
        source.write_bytes(original_source_bytes(case))
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
        source.write_bytes(original_source_bytes(case))
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
        kcc_acceptances = qbe_objects = original_runs = source_form_runs = 0
        native_counts = {cc: {'agreements': 0, 'empty_brace_gaps': 0, 'source_eof_gaps': 0, 'source_form_acceptances': 0, 'runs': 0} for cc in compilers}
        for case in CASES:
            source.write_bytes(original_source_bytes(case))
            if not options.native_only:
                result = invoke([KCC, source])
                assert result.returncode == 0 and not result.stderr and result.stdout, (case, result)
                assert source.read_bytes() == original_source_bytes(case)
                kcc_acceptances += 1
                il_layout(result.stdout, case)
                il.write_text(result.stdout)
                producer([QBE, '-t', 'amd64_sysv', '-o', assembly, il], assembly)
                producer([HOST, '-Wa,-L', '-c', assembly, '-o', obj], obj)
                check_kcc_elf(obj, case)
                if case.get('private_function'):
                    private_reference_controls(OffsetRelocations(obj), case)
                qbe_objects += 1
                if case['exit'] is not None:
                    run_original(HOST, obj, executable, case['exit'])
                    original_runs += 1
                    source_form_runs += int(not case['source_final_newline'])
            for cc in compilers:
                check_original_source(source, case)
                native_obj.unlink(missing_ok=True)
                command = [cc, '-std=c2x', '-pedantic-errors', '-fno-common', '-O0', '-c', source, '-o', native_obj]
                result = invoke(command)
                if result.returncode:
                    if clang_style(cc) and (case['origin'], case['text']) == EOF_ORIGINAL:
                        assert exact_native_eof_gap(case, result, source, native_obj, invoke([cc, '--version']), invoke([cc, '-dumpfullversion', '-dumpversion'])), (cc, case, result)
                        native_counts[cc]['source_eof_gaps'] += 1
                    else:
                        assert exact_native_gap(case, result, source, native_obj, clang_style(cc)), (cc, case, result)
                        native_counts[cc]['empty_brace_gaps'] += 1
                    continue
                # Reuse hardened complete-stream validation, but do not invoke
                # the producer again and silently replace the checked result.
                assert not result.stdout and native_obj.is_file() and native_obj.stat().st_size > 0, (cc, case, result)
                actual = native_diagnostics(result.stderr, source, case['text'], clang_style(cc))
                assert actual == native_warnings(case, clang_style(cc)), (cc, case, result.stderr)
                OffsetRelocations(native_obj)  # Fresh actual ELF, never syntax-only acceptance.
                if not case['source_final_newline']:
                    # Acceptance of a non-strict source form is NOT semantic agreement.
                    native_counts[cc]['source_form_acceptances'] += 1
                    continue
                native_counts[cc]['agreements'] += 1
                if case['exit'] is not None:
                    run_original(cc, native_obj, executable, case['exit'])
                    native_counts[cc]['runs'] += 1
        print(f'Initialization legacy promotions: {len(CASES)} byte-exact originals across 12 origins; '
              f'KCC acceptances {kcc_acceptances}; mandatory fresh QBE/ELF {qbe_objects}; '
              f'unchanged original main runs {original_runs} (strict-defined {original_runs-source_form_runs}; source-form extension {source_form_runs})')
        if options.native_only:
            print('Native-only lane: NO KCC/backend coverage claimed')
        else:
            assert kcc_acceptances == qbe_objects == len(CASES)
            assert original_runs == sum(c['exit'] is not None for c in CASES)
        for cc, counts in native_counts.items():
            assert counts['agreements'] + counts['empty_brace_gaps'] + counts['source_eof_gaps'] + counts['source_form_acceptances'] == len(CASES)
            print(f"{cc}: unchanged native ELF agreements {counts['agreements']}; "
                  f"exact C23 empty-brace gaps {counts['empty_brace_gaps']} (NOT agreements); "
                  f"exact source EOF gaps {counts['source_eof_gaps']} (NOT agreements); "
                  f"source-form acceptances {counts['source_form_acceptances']} (NOT semantic agreements); "
                  f"unchanged original runtimes {counts['runs']}")


if __name__ == '__main__':
    main()

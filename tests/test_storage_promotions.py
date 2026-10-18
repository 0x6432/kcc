"""Exact originals promoted by M15 storage support; no legacy case is deleted.

Each origin/source pair was previously a subset refusal. All are now mandatory
KCC acceptance and, with QBE set, real backend/ELF object production. Defined
originals containing main execute unchanged at their original return value.
Native originals compile unchanged, with narrow per-source known keyword gaps
or documented register-query/void divergences, never counted as agreements.
Run: [KCC=...] [HOST_CC=...] [QBE=...] python3 tests/test_storage_promotions.py
"""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root/'build'/'kcc'))
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
# Machine-readable origin mapping is part of the regression, not a side file.
CASES = json.loads(r'''
[
  {
    "origin": "test_static_arrays.py",
    "text": "int main(void) { static int items[3]; return 0; }",
    "exit": 0
  },
  {
    "origin": "test_function_declarators.py",
    "text": "int f(void) { int g(int); return 0; }",
    "exit": null
  },
  {
    "origin": "test_typeof_expressions.py",
    "text": "int f(void); int g(void) { typeof(f) h; return 0; }",
    "exit": null,
    "native_exceptions": {
      "gcc": {
        "category": "keyword gap",
        "records": [
          [
            "error",
            "implicit declaration of function 'typeof' [-Wimplicit-function-declaration]"
          ],
          [
            "error",
            "expected ';' before 'h'"
          ]
        ]
      }
    }
  },
  {
    "origin": "test_queried_function_declarations.py",
    "text": "int f(void) { typeof(int(void)) g; return 0; }",
    "exit": null,
    "native_exceptions": {
      "gcc": {
        "category": "keyword gap",
        "records": [
          [
            "error",
            "implicit declaration of function 'typeof' [-Wimplicit-function-declaration]"
          ],
          [
            "error",
            "expected expression before 'int'"
          ],
          [
            "error",
            "expected ';' before 'g'"
          ]
        ]
      }
    }
  },
  {
    "origin": "test_typedef_foundation.py",
    "text": "typedef int F(void); int main(void) { F f; return 42; }",
    "exit": 42
  },
  {
    "origin": "test_function_declaration_lists.py",
    "text": "int main(void) { extern int f(void),g(void); return 0; }",
    "exit": 0
  },
  {
    "origin": "test_extern_functions.py",
    "text": "int main(void) { extern int f(void); return 0; }",
    "exit": 0
  },
  {
    "origin": "test_extern_functions.py",
    "text": "typedef int F(int); int main(void) { F extern f; return 0; }",
    "exit": 0
  },
  {
    "origin": "test_extern_functions.py",
    "text": "extern inline int f(void) { return 42; }",
    "exit": null
  },
  {
    "origin": "test_static_functions.py",
    "text": "int main(void) { static int x; return 0; }",
    "exit": 0
  },
  {
    "origin": "test_static_functions.py",
    "text": "thread_local int x;",
    "exit": null,
    "native_exceptions": {
      "gcc": {
        "category": "keyword gap",
        "records": [
          [
            "error",
            "expected ';' before 'int'"
          ]
        ]
      }
    }
  },
  {
    "origin": "test_static_functions.py",
    "text": "static inline int f(void) { return 42; }",
    "exit": null
  },
  {
    "origin": "test_extern_objects.py",
    "text": "int f(void) { extern int x; return 0; }",
    "exit": null
  },
  {
    "origin": "test_extern_objects.py",
    "text": "extern int x; int f(void) { extern int x; return 0; }",
    "exit": null
  },
  {
    "origin": "test_extern_objects.py",
    "text": "extern thread_local int x;",
    "exit": null,
    "native_exceptions": {
      "gcc": {
        "category": "keyword gap",
        "records": [
          [
            "error",
            "expected ';' before 'int'"
          ]
        ]
      }
    }
  },
  {
    "origin": "test_extern_arrays.py",
    "text": "extern int a[2]; int f(void) { extern int a[2]; return 0; }",
    "exit": null
  },
  {
    "origin": "test_extern_arrays.py",
    "text": "int f(void) { extern int a[]; return 0; }",
    "exit": null
  },
  {
    "origin": "test_extern_arrays.py",
    "text": "extern thread_local int a[2];",
    "exit": null,
    "native_exceptions": {
      "gcc": {
        "category": "keyword gap",
        "records": [
          [
            "error",
            "expected ';' before 'int'"
          ]
        ]
      }
    }
  },
  {
    "origin": "test_tentative_scalars.py",
    "text": "extern int cell; int f(void) { extern int cell; return 0; }",
    "exit": null
  },
  {
    "origin": "test_tentative_scalars.py",
    "text": "thread_local int cell;",
    "exit": null,
    "native_exceptions": {
      "gcc": {
        "category": "keyword gap",
        "records": [
          [
            "error",
            "expected ';' before 'int'"
          ]
        ]
      }
    }
  },
  {
    "origin": "test_tentative_arrays.py",
    "text": "int f(void) { extern int items[]; return 0; }",
    "exit": null
  },
  {
    "origin": "test_tentative_arrays.py",
    "text": "thread_local int items[3];",
    "exit": null,
    "native_exceptions": {
      "gcc": {
        "category": "keyword gap",
        "records": [
          [
            "error",
            "expected ';' before 'int'"
          ]
        ]
      }
    }
  },
  {
    "origin": "test_register_parameters.py",
    "text": "int f(register void);",
    "exit": null,
    "native_exceptions": {
      "gcc": {
        "category": "divergence",
        "records": [
          [
            "error",
            "'void' as only parameter may not be qualified"
          ]
        ]
      }
    }
  },
  {
    "origin": "test_register_parameters.py",
    "text": "int f(register void) { return 42; }",
    "exit": null,
    "native_exceptions": {
      "gcc": {
        "category": "divergence",
        "records": [
          [
            "error",
            "'void' as only parameter may not be qualified"
          ]
        ]
      }
    }
  },
  {
    "origin": "test_register_parameters.py",
    "text": "int f(register typeof(void));",
    "exit": null,
    "native_exceptions": {
      "gcc": {
        "category": "keyword gap",
        "records": [
          [
            "error",
            "type defaults to 'int' in declaration of 'typeof' [-Wimplicit-int]"
          ]
        ]
      }
    }
  },
  {
    "origin": "test_register_parameters.py",
    "text": "typedef void V; int f(V register);",
    "exit": null,
    "native_exceptions": {
      "gcc": {
        "category": "divergence",
        "records": [
          [
            "error",
            "'void' as only parameter may not be qualified"
          ]
        ]
      }
    }
  },
  {
    "origin": "test_register_parameters.py",
    "text": "int f(int (*cb)(register void));",
    "exit": null,
    "native_exceptions": {
      "gcc": {
        "category": "divergence",
        "records": [
          [
            "error",
            "'void' as only parameter may not be qualified"
          ]
        ]
      }
    }
  },
  {
    "origin": "test_register_arrays.py",
    "text": "int main(void) { register int a[2]; return sizeof(a[0]); }",
    "exit": 4,
    "native_exceptions": {
      "gcc": {
        "category": "divergence",
        "records": [
          [
            "error",
            "ISO C forbids subscripting 'register' array [-Wpedantic]"
          ]
        ]
      },
      "clang": {
        "category": "divergence",
        "records": [
          [
            "error",
            "address of register variable requested"
          ]
        ]
      }
    }
  },
  {
    "origin": "test_register_arrays.py",
    "text": "int main(void) { register int a[2]; typeof(a+0) p; return 0; }",
    "exit": 0,
    "native_exceptions": {
      "gcc": {
        "category": "keyword gap",
        "records": [
          [
            "error",
            "implicit declaration of function 'typeof' [-Wimplicit-function-declaration]"
          ],
          [
            "error",
            "address of register variable 'a' requested"
          ],
          [
            "error",
            "expected ';' before 'p'"
          ]
        ]
      },
      "clang": {
        "category": "divergence",
        "records": [
          [
            "error",
            "address of register variable requested"
          ]
        ]
      }
    }
  },
  {
    "origin": "test_static_objects.py",
    "text": "int main(void) { static int cell; return 0; }",
    "exit": 0
  },
  {
    "origin": "test_static_objects.py",
    "text": "int main(void) { static int cell=0; return 0; }",
    "exit": 0
  },
  {
    "origin": "test_static_objects.py",
    "text": "int main(void) { static int cell[3]; return 0; }",
    "exit": 0
  },
  {
    "origin": "test_static_objects.py",
    "text": "typedef int T; int main(void) { T static cell; return 0; }",
    "exit": 0
  },
  {
    "origin": "test_static_objects.py",
    "text": "static thread_local int cell;",
    "exit": null,
    "native_exceptions": {
      "gcc": {
        "category": "keyword gap",
        "records": [
          [
            "error",
            "expected ';' before 'int'"
          ]
        ]
      }
    }
  },
  {
    "origin": "test_integer_initializers.py",
    "text": "typeof(nullptr) cell=nullptr;",
    "exit": null,
    "native_exceptions": {
      "gcc": {
        "category": "keyword gap",
        "records": [
          [
            "error",
            "return type defaults to 'int' [-Wimplicit-int]"
          ],
          [
            "error",
            "expected declaration specifiers before 'cell'"
          ],
          [
            "error",
            "old-style function definition [-Wold-style-definition]"
          ],
          [
            "error",
            "type of 'nullptr' defaults to 'int' [-Wimplicit-int]"
          ],
          [
            "error",
            "expected '{' at end of input"
          ]
        ]
      }
    }
  }
]
''' )


def records(stderr):
    return [list(x) for x in re.findall(r'(fatal error|error|warning|note): ([^\n]+)',
                                       stderr.replace('‘', "'").replace('’', "'"))]


NATIVE_EXCEPTIONS = {(case['origin'], case['text'], lane): expected
                     for case in CASES for lane, expected in case.get('native_exceptions', {}).items()}


def known_native_exception(case, lane, result, artifact, source):
    expected = NATIVE_EXCEPTIONS.get((case.get('origin'), case.get('text'), lane))
    if (expected is None or result.returncode != 1 or result.stdout or artifact.exists()
            or source.read_text() != case['text']+'\n' or records(result.stderr) != expected['records']):
        return False
    # No unrelated, unformatted stderr can be hidden after an expected error.
    diagnostic = re.compile(re.escape(str(source))+r':\d+(?::\d+)?: (?:fatal error|error|warning|note): .+')
    for line in result.stderr.splitlines():
        if not line or diagnostic.fullmatch(line):
            continue
        if line.startswith(str(source)+': In function '):
            continue
        if re.fullmatch(r'\s*\d+ \|.*|\s*\|.*', line):
            continue
        summary = re.fullmatch(r'(\d+) errors? generated\.', line)
        if summary and int(summary[1]) == sum(kind in ('error', 'fatal error') for kind, _ in expected['records']):
            continue
        return False
    return True


# Scoped classifier controls: an unrelated source, warning, extra error, crash,
# missing diagnostic, stale artifact, or stdout cannot become a native gap.
with tempfile.TemporaryDirectory(prefix='kcc storage promotions ') as directory:
    directory = Path(directory)
    source, il, assembly, obj, native_obj, executable = [directory/name for name in
        ('original.c', 'original.ssa', 'original.s', 'kcc.o', 'native.o', 'program')]
    version = subprocess.run([host, '--version'], capture_output=True, text=True, timeout=10)
    assert version.returncode == 0, version.stderr
    lane = 'clang' if 'clang' in version.stdout.lower() else 'gcc'
    agreements = executed = native_executed = object_proofs = 0
    exceptions = {'keyword gap': 0, 'divergence': 0}
    assert len(CASES) == 34 and len({(c['origin'], c['text']) for c in CASES}) == len(CASES)
    for case in CASES:
        text = case['text']
        # The exact recorded original is used in BOTH producers. Only an ending
        # newline is added, as in the legacy source.write_text(text+'\n') calls.
        source.write_text(text+'\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=20)
        assert result.returncode == 0 and not result.stderr, (case, result.stderr)
        if qbe:
            il.write_text(result.stdout)
            for artifact in (assembly, obj, executable):
                artifact.unlink(missing_ok=True)
            backend = subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)],
                                     capture_output=True, text=True, timeout=20)
            assert backend.returncode == 0 and not backend.stderr and assembly.exists(), (case, backend.stderr)
            assembled = subprocess.run([host, '-c', str(assembly), '-o', str(obj)],
                                       capture_output=True, text=True, timeout=20)
            assert assembled.returncode == 0 and obj.exists() and obj.stat().st_size > 0, (case, assembled.stderr)
            elf = subprocess.run(['readelf', '-h', str(obj)], capture_output=True, text=True, timeout=10)
            assert elf.returncode == 0 and 'REL (Relocatable file)' in elf.stdout, (case, elf.stderr)
            object_proofs += 1
            if case['exit'] is not None:
                linked = subprocess.run([host, str(obj), '-o', str(executable)], capture_output=True,
                                        text=True, timeout=20)
                assert linked.returncode == 0, (case, linked.stderr)
                run = subprocess.run([str(executable)], capture_output=True, text=True, timeout=10)
                assert run.returncode == case['exit'], (case, run)
                executed += 1
        native_obj.unlink(missing_ok=True)
        native = subprocess.run([host, '-std=c2x', '-pedantic-errors', '-c', str(source),
                                 '-o', str(native_obj)], capture_output=True, text=True, timeout=20)
        if native.returncode == 0:
            assert not native.stderr and not native.stdout and native_obj.exists() and native_obj.stat().st_size, (case, native)
            agreements += 1
            if case['exit'] is not None:
                executable.unlink(missing_ok=True)
                linked = subprocess.run([host, str(native_obj), '-o', str(executable)],
                                        capture_output=True, text=True, timeout=20)
                assert linked.returncode == 0, (case, linked.stderr)
                run = subprocess.run([str(executable)], capture_output=True, text=True, timeout=10)
                assert run.returncode == case['exit'], (case, run)
                native_executed += 1
        else:
            assert known_native_exception(case, lane, native, native_obj, source), (case, native.stderr)
            category = case['native_exceptions'][lane]['category']
            exceptions[category] += 1
            assert not known_native_exception(dict(case, text='int unrelated;'), lane, native, native_obj, source)
            for status in (0, 2, -6, -11, 127):
                bad = subprocess.CompletedProcess([], status, native.stdout, native.stderr)
                assert not known_native_exception(case, lane, bad, native_obj, source)
            for extra in ('error: unrelated failure\n', 'warning: unrelated warning\n', 'UNRELATED STDERR\n'):
                bad = subprocess.CompletedProcess([], 1, '', native.stderr+extra)
                assert not known_native_exception(case, lane, bad, native_obj, source)
            for stdout, stderr in [('unexpected stdout', native.stderr), ('', '')]:
                bad = subprocess.CompletedProcess([], 1, stdout, stderr)
                assert not known_native_exception(case, lane, bad, native_obj, source)
            native_obj.write_bytes(b'stale')
            assert not known_native_exception(case, lane, native, native_obj, source)
            native_obj.unlink()
print(f'Storage legacy promotions passed ({len(CASES)} exact mapped originals; '
      f'{object_proofs} QBE/ELF objects; {executed} KCC original runtimes; '
      f'{agreements} unchanged native compile agreements, {native_executed} native runtimes; '
      f"{exceptions['keyword gap']} exact keyword gaps and {exceptions['divergence']} explicit native divergences; {host})")

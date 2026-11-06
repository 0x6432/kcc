"""Direct _BitInt type-layout queries and conservative ABI boundary."""
import os
import platform
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root / 'build' / 'kcc'
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')

# The source contains no _BitInt values. Exercise every width and both signs,
# on both sides of each storage/alignment transition, in constant expressions.
checks = []
for width in range(1, 65):
    size = 1 if width <= 8 else 2 if width <= 16 else 4 if width <= 32 else 8
    for sign in (['unsigned'] if width == 1 else ['', 'signed', 'unsigned']):
        t = f'{sign} _BitInt({width})'
        checks += [f'static_assert(sizeof({t}) == {size});',
                   f'static_assert(alignof({t}) == {size});']
checks += [
    '#define WIDTH (3 * 3)',
    'enum { W = 8 };',
    'static_assert(sizeof(const _BitInt(W + 1) unsigned) == 2);',
    'static_assert(alignof(volatile signed _BitInt(WIDTH)) == 2);',
    'static_assert(sizeof(_BitInt(sizeof(unsigned _BitInt(64)) + 1)) == 2);',
    'static_assert(_Generic(sizeof(_BitInt(3)), unsigned long: 1, default: 0));',
    'struct A { char c; alignas(_BitInt(33)) int i; };',
    'static_assert(sizeof(struct A) == 16 && alignof(struct A) == 8);',
    'int main(void) { return sizeof(_BitInt(17)) * 10 + alignof(unsigned _BitInt(8)) + 1; }',
]
invalid = [
    ('int x; int f(void) { return sizeof(_BitInt(x)); }', 'integer constant expression'),
    ('int f(int x) { return sizeof(_BitInt(x++)); }', 'integer constant expression'),
    ('int f(void) { return sizeof(_BitInt(1.0)); }', 'integer constant expression'),
    ('int f(void) { return sizeof(_BitInt(1/0)); }', 'integer constant expression'),
    ('int f(void) { return sizeof(_BitInt(0)); }', 'outside the supported range'),
    ('int f(void) { return sizeof(_BitInt(1)); }', 'outside the supported range'),
    ('int f(void) { return sizeof(unsigned _BitInt(0)); }', 'outside the supported range'),
    ('int f(void) { return sizeof(_BitInt(-1)); }', 'outside the supported range'),
    ('int f(void) { return sizeof(_BitInt(65)); }', 'outside the supported range'),
    ('int f(void) { return alignof(unsigned _BitInt(65)); }', 'outside the supported range'),
    ('alignas(_BitInt(65)) int x;', 'outside the supported range'),
    ('alignas(_BitInt(8)) int x;', 'weaken'),
    ('int f(void) { return sizeof(unsigned _BitInt(18446744073709551615ULL)); }', 'outside the supported range'),
    ('int f(void) { return sizeof(_BitInt(8) int); }', 'cannot combine'),
    ('int f(void) { return sizeof(unsigned signed _BitInt(8)); }', 'duplicate or conflicting'),
    ('int f(void) { return sizeof(_Atomic(_BitInt(8))); }', 'does not support atomic'),
    ('int f(void) { return sizeof(restrict _BitInt(8)); }', 'does not support atomic or restrict'),
    ('typedef _BitInt(7) T;', 'only in direct sizeof'),
    ('_BitInt(7) x;', 'only in direct sizeof'),
    ('struct S { _BitInt(7) x; };', 'only in direct sizeof'),
    ('_BitInt(7) f(_BitInt(7) x);', 'only in direct sizeof'),
    ('int f(void) { return (int)(_BitInt(7))1; }', 'only in direct sizeof'),
    ('int f(void) { return sizeof(_BitInt(7) *); }', 'only in direct sizeof'),
    ('int f(void) { return sizeof(_BitInt(7)[2]); }', 'only in direct sizeof'),
    ('int f(void) { return sizeof(typeof(_BitInt(7))); }', 'only in direct sizeof'),
    ('int f(void) { return _Generic(0, _BitInt(7): 1, default: 0); }', 'only in direct sizeof'),
    ('int f(void) { return sizeof((_BitInt(7)){1}); }', 'only in direct sizeof'),
    ('enum E : _BitInt(8) { A };', 'fixed enum underlying type'),
]
with tempfile.TemporaryDirectory(prefix='kcc-bitint-layout-', dir=root / 'build') as directory:
    path = Path(directory)
    source, il, asm, exe = [path / n for n in ('input.c', 'out.ssa', 'out.s', 'out')]
    source.write_text('\n'.join(checks) + '\n')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0 and not result.stderr, result.stderr
    if qbe:
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), '-o', str(exe)], check=True)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
    # The existing type-query nesting budget applies to nested width queries.
    def nested(level):
        width = '2'
        for _ in range(level):
            width = f'sizeof(_BitInt({width})) + 1'
        return 'static_assert(' + width + ' > 0);'
    source.write_text(nested(64))
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    source.write_text(nested(65))
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode != 0 and not result.stdout and 'nesting exceeds limit' in result.stderr, result.stderr
    for program, message in invalid:
        source.write_text(program + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode != 0 and not result.stdout and message in result.stderr, (program, result.stderr)
# A host with native _BitInt can independently check the target-layout table.
# This does not test object or call interoperability.
host_checked = False
if platform.system() == 'Linux' and platform.machine() in ('x86_64', 'amd64'):
    probe = subprocess.run([host, '-std=c2x', '-x', 'c', '-fsyntax-only', '-'],
                           input='_BitInt(2) x;\n', capture_output=True, text=True, timeout=10)
    if probe.returncode == 0:
        native = []
        for width in range(1, 65):
            size = 1 if width <= 8 else 2 if width <= 16 else 4 if width <= 32 else 8
            for sign in (['unsigned'] if width == 1 else ['', 'signed', 'unsigned']):
                t = f'{sign} _BitInt({width})'
                native.append(f'_Static_assert(sizeof({t}) == {size} && _Alignof({t}) == {size}, "layout");')
        result = subprocess.run([host, '-std=c2x', '-x', 'c', '-fsyntax-only', '-'],
                                input='\n'.join(native), capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stderr
        host_checked = True
print('BitInt direct layout query checks passed' + (' with QBE runtime' if qbe else '') +
      ('; host layout comparison passed' if host_checked else '; host _BitInt layout comparison unavailable'))

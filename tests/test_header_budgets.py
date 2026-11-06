"""Compiler-owned fallback headers have bounded, separate resource budgets."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
headers = ('stdarg.h stdbool.h stdalign.h stddef.h stdint.h limits.h float.h '
           'stdnoreturn.h assert.h stdatomic.h stdlib.h string.h stdio.h errno.h '
           'math.h tgmath.h ctype.h inttypes.h time.h locale.h wchar.h wctype.h '
           'uchar.h stdbit.h signal.h fenv.h threads.h stdckdint.h').split()
prefix = ''.join('#include <' + header + '>\n' for header in headers)
with tempfile.TemporaryDirectory(prefix='kcc-header-budget-') as directory:
    source = Path(directory) / 'test.c'
    for declarations, ok in (('int main(void){return 0;}', True),
                             ('extern int repeat(void);' * 512, True),
                             ('extern int repeat(void);' * 513, False),
                             (''.join('int userfunc%d(void);' % i for i in range(256)), True),
                             (''.join('int userfunc%d(void);' % i for i in range(257)), False)):
        source.write_text(prefix + declarations)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=30)
        assert (result.returncode == 0) == ok, result.stderr
        if not ok:
            assert 'limit' in result.stderr, result.stderr
print('header resource budget checks completed')

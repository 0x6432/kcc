"""Check internal BitInt type-model expectations against a native Clang oracle.

Run with CLANG pointing to a Clang that supports C2x _BitInt. This independently
checks the expected width/rank/conversion model, not KCC's own lowering.
"""
import os
import subprocess
import tempfile
from pathlib import Path

clang = os.environ.get('CLANG', 'clang')

def spelling(width, unsigned):
    return ('unsigned ' if unsigned else '') + f'_BitInt({width})'

def main():
    lines = []
    types = [(w, u) for w in range(1, 65) for u in (False, True) if u or w > 1]
    for w, u in types:
        t = spelling(w, u)
        size = 1 if w <= 8 else 2 if w <= 16 else 4 if w <= 32 else 8
        lines.append(f'_Static_assert(sizeof({t}) == {size} && _Alignof({t}) == {size}, "layout {t}");')
        lines.append(f'_Static_assert(_Generic(+( ({t})0 ), {t}: 1, default: 0), "promotion {t}");')
        literal = (1 << (w - 1)) if u else (1 << (w - 2))
        lines.append(f'_Static_assert(_Generic({literal}'+('uwb' if u else 'wb')+f', {t}: 1, default: 0), "literal {t}");')
        # Compare a source sign-boundary value through every destination width.
        raw = 1 << (w - 1)
        source_value = raw if u else raw - (1 << w)
        for dest_width, dest_unsigned in types:
            dest = spelling(dest_width, dest_unsigned)
            value = source_value & ((1 << dest_width) - 1)
            if not dest_unsigned and value & (1 << (dest_width - 1)):
                value -= 1 << dest_width
            expected = value & ((1 << 64) - 1)
            lines.append(f'_Static_assert((unsigned long long)({dest})({t}){raw}ULL == {expected}ULL, "convert {w}/{int(u)} {dest_width}/{int(dest_unsigned)}");')
        for v, z in types:
            expected = spelling(w, u) if w > v else spelling(v, z) if v > w else spelling(w, u or z)
            lines.append(f'_Static_assert(_Generic((({t})0)+(({spelling(v,z)})0), {expected}: 1, default: 0), "rank {w}/{int(u)} {v}/{int(z)}");')
        si = spelling(w, u) if w > 32 else 'unsigned int' if w == 32 and u else 'int'
        ui = spelling(w, u) if w > 32 else 'unsigned int'
        lines.append(f'_Static_assert(_Generic((({t})0)+0, {si}: 1, default: 0), "int {t}");')
        lines.append(f'_Static_assert(_Generic((({t})0)+0U, {ui}: 1, default: 0), "uint {t}");')
        for suffix, expected in [('L', 'unsigned long' if w == 64 and u else 'long'),
                                 ('UL', 'unsigned long'),
                                 ('LL', 'unsigned long long' if w == 64 and u else 'long long'),
                                 ('ULL', 'unsigned long long')]:
            lines.append(f'_Static_assert(_Generic((({t})0)+0{suffix}, {expected}: 1, default: 0), "{suffix} {t}");')
    with tempfile.TemporaryDirectory(prefix='bitint-type-oracle-') as tmp:
        source = Path(tmp) / 'oracle.c'
        source.write_text('\n'.join(lines) + '\n')
        result = subprocess.run([clang, '-std=c2x', '-fsyntax-only', '-Werror', '-Wno-constant-logical-operand', str(source)], capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stderr[:10000]
    print(f'Clang BitInt type oracle: {len(lines)} assertions passed')

if __name__ == '__main__':
    main()

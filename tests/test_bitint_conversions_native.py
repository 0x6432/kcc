"""Differential constant typing and runtime BitInt conversion boundary matrix."""
from pathlib import Path
import tempfile
import subprocess
from test_bitint_arbitrary import ROOT, CLANG, compile_clang, compile_kcc, run

MASK64 = (1 << 64) - 1

def spelling(w, u):
    return ('unsigned ' if u else '') + f'_BitInt({w})'

def value_after(value, width, unsigned):
    v = value & ((1 << width) - 1)
    if not unsigned and v & (1 << (width - 1)):
        v -= 1 << width
    return v & MASK64

def main():
    types = [(w, u) for w in range(1, 65) for u in (0, 1) if u or w > 1]
    boundary_widths = {1, 2, 3, 7, 8, 9, 15, 16, 17, 31, 32, 33, 34, 47, 63, 64}
    sampled = [t for t in types if t[0] in boundary_widths]
    with tempfile.TemporaryDirectory(prefix='bitint-convert-', dir=ROOT/'build') as tmp:
        d = Path(tmp)
        # All source widths against boundary destinations, and boundary sources
        # against every destination. Volatile prevents constant folding.
        for start in range(0, len(types), 8):
            group = types[start:start+8]
            lines = []
            for i, (w, u) in enumerate(group):
                src = spelling(w, u)
                raw = 1 << (w - 1)
                source_value = raw if u else raw - (1 << w)
                expected_int = src if w > 32 else 'unsigned int' if w == 32 and u else 'int'
                expected_uint = src if w > 32 else 'unsigned int'
                expected_long = 'unsigned long' if w == 64 and u else 'long'
                lines.append(f'_Static_assert(_Generic(({src})0 + 0, {expected_int}:1, default:0), "int rank");')
                lines.append(f'_Static_assert(_Generic(({src})0 + 0U, {expected_uint}:1, default:0), "uint rank");')
                lines.append(f'_Static_assert(_Generic(({src})0 + 0L, {expected_long}:1, default:0), "long rank");')
                lines.append(f'int check{i}(void) {{ volatile {src} x=({src}){raw}UL;')
                destinations = types if (w, u) in sampled else sampled
                for j, (tw, tu) in enumerate(destinations):
                    target = spelling(tw, tu)
                    expected = value_after(source_value, tw, tu)
                    lines.append(f' if ((unsigned long)({target})x != {expected}UL) return {j+1};')
                lines.append(' return 0; }')
            lines.append('int main(void) {')
            for i in range(len(group)):
                lines.append(f'if (check{i}()) return {i+1};')
            lines.append('return 0; }')
            src = '\n'.join(lines)+'\n'
            for compiler in (compile_kcc, compile_clang):
                obj = compiler(d, src, 'conversion')
                exe = d/'conversion'
                run([CLANG, obj, ROOT/'build/libkccrt.a', '-o', exe])
                result = subprocess.run([str(exe)], timeout=10)
                if result.returncode:
                    raise AssertionError((compiler.__name__, 'source type', group[result.returncode-1]))
        checks = []
        for w, u in types:
            value = 1 << (w - 1 if u else w - 2)
            suffix = 'uwb' if u else 'wb'
            checks.append(f'_Static_assert(_Generic({value}{suffix}, {spelling(w,u)}: 1, default: 0), "literal");')
        checks += ['_Static_assert(_Generic(0wb, _BitInt(2):1, default:0), "zero");',
                   '_Static_assert(_Generic(0uwb, unsigned _BitInt(1):1, default:0), "zero unsigned");']
        source = '\n'.join(checks) + '\nint main(void){return 0;}\n'
        for compiler in (compile_kcc, compile_clang):
            obj = compiler(d, source, 'literals')
            exe = d/'literals'; run([CLANG, obj, '-o', exe]); run([exe])
    print('KCC and Clang conversion boundary matrix and 129 wb literal types passed')

if __name__ == '__main__': main()

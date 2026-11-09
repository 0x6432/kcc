"""Byte-width C23 _BitInt ABI and atomic checks on x86-64 SysV.

Cross-object checks use native _BitInt when the host compiler supports it;
otherwise explicitly use integer representation surrogates (not C23 evidence).
"""
import os
from pathlib import Path
import subprocess
import tempfile
from runtime_link import runtime_link_flags

ROOT = Path(__file__).resolve().parents[1]
KCC = ROOT / 'build/kcc'
QBE = os.environ.get('QBE', 'qbe')
HOST = os.environ.get('HOST_CC', 'cc')

def run(args):
    p = subprocess.run([str(a) for a in args], capture_output=True, text=True, timeout=45)
    assert p.returncode == 0, (args, p.stdout, p.stderr)
    return p

def host_supports_bitint(d):
    (d/'probe.c').write_text('unsigned _BitInt(8) f(unsigned _BitInt(8) x) { return x; }\n')
    return subprocess.run([HOST, '-std=c2x', '-c', str(d/'probe.c'), '-o', str(d/'probe.o')], capture_output=True).returncode == 0

def compile_kcc(d, source, stem):
    (d/f'{stem}.c').write_text(source)
    p = run([KCC, d/f'{stem}.c'])
    assert not p.stderr, p.stderr
    (d/f'{stem}.ssa').write_text(p.stdout)
    run([QBE, '-t', 'amd64_sysv', '-o', d/f'{stem}.s', d/f'{stem}.ssa'])
    run([HOST, '-c', d/f'{stem}.s', '-o', d/f'{stem}.o'])
    return d/f'{stem}.o'

def compile_host(d, source, stem):
    (d/f'{stem}.c').write_text(source)
    run([HOST, '-std=c2x', '-O2', '-Wall', '-Wextra', '-Werror', '-c', d/f'{stem}.c', '-o', d/f'{stem}.o'])
    return d/f'{stem}.o'

def pair(d, kdecl, hdecl, body, caller):
    for i in range(2):
        ko = compile_kcc(d, kdecl + (body if i == 0 else caller), 'k')
        ho = compile_host(d, hdecl + (caller if i == 0 else body), 'h')
        run([HOST, ko, ho, ROOT/'build/libkccrt.a', '-latomic', *runtime_link_flags(), '-o', d/'exe'])
        run([d/'exe'])

def main():
    with tempfile.TemporaryDirectory(prefix='bitint-abi-', dir=ROOT/'build') as tmp:
        d = Path(tmp)
        native = host_supports_bitint(d)
        for width, primitive in [(8, 'char'), (16, 'short'), (32, 'int'), (64, 'long')]:
            for signed in (True, False):
                sign = '' if signed else 'unsigned '
                kd = f'typedef {sign}_BitInt({width}) T;\n'
                hd = kd if native else f'typedef {"signed" if signed else "unsigned"} {primitive} T;\n'
                body = 'T transform(T x) { return x + (T)2; }\n'
                value = '-42' if signed else '40'
                answer = '-40' if signed else '42'
                caller = ('T transform(T); int main(void) { T (*fp)(T)=transform; '
                          f'T x=(T)({value}); return fp(x)!=(T)({answer});' + '}\n')
                pair(d, kd, hd, body, caller)
                decl = 'struct S { T x; T y; };\n'
                body = 'struct S transform(struct S x) { x.x += (T)2; return x; }\n'
                caller = ('struct S transform(struct S); int main(void) { struct S s={(T)40,(T)7}; '
                          'struct S t=transform(s); return t.x!=42 || t.y!=7 || s.x!=40; }\n')
                pair(d, kd+decl, hd+decl, body, caller)
                decl = 'struct S { T x; double d; long tail; };\n'
                body = 'struct S transform(struct S x) { x.x += (T)2; return x; }\n'
                caller = ('struct S transform(struct S); int main(void) { struct S s={(T)40,1.5,7}; '
                          'struct S t=transform(s); return t.x!=42 || t.d!=1.5 || t.tail!=7; }\n')
                pair(d, kd+decl, hd+decl, body, caller)
                # Bit-precise members with packed fields and zero-width barriers.
                for decl, init, check in [
                    ('struct S { unsigned a:3,b:4; T x; };\n', '{3,5,(T)40}', 't.a!=3 || t.b!=5'),
                    ('struct S { T x; unsigned :0; char pad[24]; };\n', '{(T)40,{0}}', 't.pad[0]!=0')]:
                    body = 'struct S transform(struct S x) { x.x += (T)2; return x; }\n'
                    caller = ('struct S transform(struct S); int main(void) { struct S s='+init+'; '
                              'struct S t=transform(s); return t.x!=42 || '+check+'; }\n')
                    pair(d, kd+decl, hd+decl, body, caller)
                if native:
                    decl = '#include <stdarg.h>\n'
                    body = ('int var(int n, ...) { va_list ap; va_start(ap,n); (void)n; '
                            'T x=va_arg(ap,T); va_end(ap); return (int)x; }\n')
                    value = '-42' if signed else '42'
                    caller = f'int var(int,...); int main(void) {{ return var(1,(T)({value})) != ({value}); }}\n'
                    pair(d, decl+kd, decl+hd, body, caller)
                # Native clang 15 does not accept atomic bit-precise types.
                # Use matching standard integer representations as an explicitly
                # bounded libatomic cross-object surrogate, never a C23 oracle.
                atomic_hd = f'typedef {"signed" if signed else "unsigned"} {primitive} T;\n'
                decl = '#include <stdatomic.h>\n'
                body = ('T update(_Atomic(T) *p) { T expected=(T)40; '
                        'if (!atomic_compare_exchange_strong(p,&expected,(T)41)) return (T)1; '
                        'return atomic_fetch_add(p,(T)1); }\n')
                caller = ('T update(_Atomic(T)*); int main(void) { _Atomic(T) x=(T)40; '
                          'return update(&x)!=(T)41 || atomic_load(&x)!=(T)42; }\n')
                pair(d, decl+kd, decl+atomic_hd, body, caller)
                source = kd + f'static_assert(sizeof(_Atomic({sign}_BitInt({width}))) == {width//8});\n' + '''#include <stdarg.h>
#include <stdatomic.h>
int var(int n, ...) { va_list ap; va_start(ap,n); (void)n; T x=va_arg(ap,T); va_end(ap); return (int)x; }
int main(void) { _Atomic(T) x=(T)40; T expected=(T)40;
    if (sizeof(_Atomic(T)) != sizeof(T)) return 1;
    if (atomic_fetch_add(&x,(T)1)!=(T)40) return 2;
    if (!atomic_compare_exchange_strong(&x,&expected,(T)42)) {
        if (expected!=(T)41) return 3;
    } else return 4;
    expected=(T)41;
    if (!atomic_compare_exchange_strong(&x,&expected,(T)42)) return 5;
    if (atomic_load(&x)!=(T)42) return 6;
    return var(0,(T)42)!=42;
}\n'''
                obj = compile_kcc(d, source, 'self')
                run([HOST, obj, ROOT/'build/libkccrt.a', '-latomic', *runtime_link_flags(), '-o', d/'exe'])
                run([d/'exe'])
        print('BitInt fixed and aggregate cross-object ABI:', 'native _BitInt' if native else 'primitive surrogates only')
        print('BitInt atomic ABI: standard-integer surrogate cross-calls')
        print('BitInt 8/16/32/64 atomic and variadic KCC self-execution passed')

if __name__ == '__main__':
    main()

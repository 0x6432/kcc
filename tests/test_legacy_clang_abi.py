"""Bounded legacy-Clang x86-64 aggregate ABI, with strict refusal of holes."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
kcc = Path(os.environ.get('KCC', root / 'build/kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')
mode = '--legacy-clang-abi'
decl = '''
struct A { float f; unsigned :1; };
struct C { float f; unsigned :31; float g; };
union U { float f; unsigned :1; };
struct Nested { struct A a; double d; };
struct Big { long x[3]; unsigned :1; float f; };
struct A fa(struct A x);
struct C fc(struct C x);
union U fu(union U x);
struct Nested fn(struct Nested x);
struct Big fb(struct Big x);
struct A pressure(double a,double b,double c,double d,double e,double f,double g,double h,struct A x,long tail);
'''
owner = decl + '''
struct A fa(struct A x) { x.f+=1; return x; }
struct C fc(struct C x) { x.f+=1; x.g+=2; return x; }
union U fu(union U x) { x.f+=1; return x; }
struct Nested fn(struct Nested x) { x.a.f+=1; x.d+=2; return x; }
struct Big fb(struct Big x) { x.x[2]++; x.f+=1; return x; }
struct A pressure(double a,double b,double c,double d,double e,double f,double g,double h,struct A x,long tail) {
 x.f += a+b+c+d+e+f+g+h+tail; return x;
}
'''
companion = decl + '''
int main(void) {
 struct A a={1.5f}, aa=fa(a); struct C c={1.5f,2.5f}, cc=fc(c);
 union U u={.f=1.5f}, uu=fu(u); struct Nested n={{1.5f},2.5}, nn=fn(n);
 struct Big b={{1,2,3},1.5f}, bb=fb(b);
 struct A (*p)(struct A)=fa; struct A pp=p(a);
 struct A pr=pressure(1,2,3,4,5,6,7,8,a,2);
 if (aa.f!=2.5f || a.f!=1.5f || cc.f!=2.5f || cc.g!=4.5f || c.g!=2.5f) return 1;
 if (uu.f!=2.5f || nn.a.f!=2.5f || nn.d!=4.5 || n.a.f!=1.5f) return 2;
 if (bb.x[0]!=1 || bb.x[2]!=4 || bb.f!=2.5f || b.x[2]!=3) return 3;
 if (pp.f!=2.5f || pr.f!=39.5f || a.f!=1.5f) return 4;
 return 0;
}
'''

def run(args, **kw):
    p = subprocess.run([str(a) for a in args], capture_output=True, text=True, timeout=30, **kw)
    assert p.returncode == 0 and not p.stdout and not p.stderr, (args, p.returncode, p.stdout, p.stderr)
    return p

def compile_kcc(source, obj, use_mode):
    args = [str(kcc)] + ([mode] if use_mode else []) + [str(source)]
    p = subprocess.run(args, capture_output=True, text=True, timeout=15)
    assert p.returncode == 0 and not p.stderr, (args, p.stderr)
    il, asm = obj.with_suffix('.ssa'), obj.with_suffix('.s')
    il.write_text(p.stdout)
    run([qbe, '-t', 'amd64_sysv', '-o', asm, il])
    run([host, '-c', asm, '-o', obj])

def run_matrix(d, native, use_mode):
    for a, b in [('native', 'native'), ('native', 'kcc'), ('kcc', 'native'), ('kcc', 'kcc')]:
        for kind, source, obj in [(a, d/'owner.c', d/'owner.o'), (b, d/'companion.c', d/'companion.o')]:
            if kind == 'kcc': compile_kcc(source, obj, use_mode)
            else: run([native, '-std=c11', '-pedantic-errors', '-c', source, '-o', obj])
        run([host, d/'owner.o', d/'companion.o', '-o', d/'test'])
        run([d/'test'])
    print(f'{native}: all four native/KCC combinations passed with {"legacy Clang" if use_mode else "default GCC"} ABI')

def run_unnamed_matrix(d, native):
    checked = rejected = 0
    bases = [
        ('unsigned char', range(1, 9)), ('unsigned short', range(1, 17)),
        ('unsigned int', range(1, 33)), ('_Bool', (1,)), ('enum E', range(1, 33)),
        ('unsigned long', (*range(1, 33), 64)),
        ('unsigned long long', (*range(1, 33), 64)),
    ]
    for typ in ('float', 'double'):
        for base, widths in bases:
            for width in widths:
                prefix = 'enum E { Z=0, P=1 };\n' if base == 'enum E' else ''
                declaration = prefix + f'struct S {{ {typ} a; {base} :{width}; float b; }};\n'
                owner_text = declaration + 'struct S f(struct S x) { x.a+=1; x.b+=2; return x; }\n'
                companion_text = declaration + (
                    'struct S f(struct S); int main(void) { struct S x={1.5,2.5f}, y=f(x); '
                    'return y.a==2.5 && y.b==4.5f && x.b==2.5f ? 0 : 1; }\n')
                (d/'matrix-owner.c').write_text(owner_text)
                (d/'matrix-companion.c').write_text(companion_text)
                # Both sides must independently pass the mode's ABI check.
                results = [subprocess.run([str(kcc), mode, str(d / filename)], capture_output=True,
                                          text=True, timeout=15)
                           for filename in ('matrix-owner.c', 'matrix-companion.c')]
                if any(result.returncode for result in results):
                    assert all(result.returncode == 1 and not result.stdout and
                               'aggregate ABI unsupported' in result.stderr for result in results), (
                                   typ, base, width, [(r.returncode, r.stderr) for r in results])
                    rejected += 1
                    continue
                assert all(not r.stderr for r in results), (typ, base, width)
                for a, b in [('native', 'kcc'), ('kcc', 'native')]:
                    for kind, source, obj in [(a, d/'matrix-owner.c', d/'matrix-owner.o'),
                                              (b, d/'matrix-companion.c', d/'matrix-companion.o')]:
                        if kind == 'kcc': compile_kcc(source, obj, True)
                        else: run([native, '-std=c11', '-pedantic-errors', '-c', source, '-o', obj])
                    run([host, d/'matrix-owner.o', d/'matrix-companion.o', '-o', d/'matrix'])
                    try: run([d/'matrix'])
                    except AssertionError as error:
                        raise AssertionError((typ, base, width, a, b, error)) from error
                checked += 1
    assert checked, (checked, rejected)
    print(f'{native}: {checked} unnamed-field layouts passed both directions; '
          f'{rejected} unrepresentable layouts rejected (NOT agreements)')


with tempfile.TemporaryDirectory(prefix='kcc-clang-abi-') as td:
    d = Path(td)
    (d/'owner.c').write_text(owner)
    (d/'companion.c').write_text(companion)
    # Both sema and codegen must choose the same ABI. Untouched code without
    # unnamed bit-fields should have identical generated IL in either mode.
    plain = d/'plain.c'
    plain.write_text('struct P { float x; int y; }; struct P f(struct P p) { return p; }\n')
    normal = subprocess.run([str(kcc), str(plain)], capture_output=True, text=True, timeout=10)
    alternate = subprocess.run([str(kcc), mode, str(plain)], capture_output=True, text=True, timeout=10)
    assert normal.returncode == alternate.returncode == 0 and not normal.stderr and not alternate.stderr
    assert normal.stdout == alternate.stdout
    # Clang omits an entire second eightbyte here. QBE 1.2 cannot represent
    # NO_CLASS in a register aggregate, so the mode must refuse it.
    hole = d/'hole.c'
    holes = [
        'struct B { double d; unsigned :1; }; struct B f(struct B b) { return b; }\n',
        'struct B { unsigned long :64; double d; }; struct B f(struct B b) { return b; }\n',
        'struct B { double d; unsigned :1; }; struct B f(struct B); '
        'int g(struct B *p) { struct B b=f(*p); return (int)b.d; }\n',
    ]
    for text in holes:
        hole.write_text(text)
        default = subprocess.run([str(kcc), str(hole)], capture_output=True, text=True, timeout=10)
        reject = subprocess.run([str(kcc), mode, str(hole)], capture_output=True, text=True, timeout=10)
        assert default.returncode == 0 and not default.stderr, default.stderr
        assert reject.returncode == 1 and not reject.stdout and 'aggregate ABI unsupported (M21, legacy Clang mode)' in reject.stderr, reject.stderr
    hole.write_text('struct B { double d; unsigned :1; }; int f(struct B *b) { return b->d==0; }\n')
    p = subprocess.run([str(kcc), mode, str(hole)], capture_output=True, text=True, timeout=10)
    assert p.returncode == 0 and not p.stderr
    for flags in ([mode, '--tokens'], [mode, '--pp-tokens'], [mode, '--warn-legacy-clang-abi']):
        p = subprocess.run([str(kcc), *flags, str(hole)], capture_output=True, text=True, timeout=10)
        assert p.returncode == 1 and not p.stdout and 'error:' in p.stderr, (flags, p.stderr)
    if qbe:
        gcc = shutil.which('gcc')
        if gcc: run_matrix(d, gcc, False)
        else: print('GCC unavailable: default cross-compiler matrix NOT run')
        clang = os.environ.get('KCC_CLANG_LEGACY_CC') or shutil.which('clang')
        if clang:
            version = subprocess.run([clang, '--version'], capture_output=True, text=True, timeout=10)
            if version.returncode == 0 and re.search(r'clang version 18\.1\.\d+\b', version.stdout):
                run_matrix(d, clang, True)
                run_unnamed_matrix(d, clang)
            else: print(f'{clang}: not verified Clang 18.1; legacy matrix NOT run')
        else: print('Clang 18.1 unavailable: legacy cross-compiler matrix NOT run')
    else:
        print('QBE unavailable: cross-compiler runtime matrices NOT run')
print('legacy Clang ABI: bounded classifications, unchanged default, and NO_CLASS refusal checked')

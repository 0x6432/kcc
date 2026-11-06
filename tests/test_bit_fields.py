"""M22 full-unit bit-fields: executable target/host interoperability and boundaries.

Run with QBE=/path/to/qbe python3 tests/test_bit_fields.py. Test files and
executables are created under this worktree's build directory. Only defined
programs are executed; unsupported cases are compiler-rejection checks.
"""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
KCC = Path(os.environ.get('KCC', ROOT / 'build/kcc'))
QBE = os.environ.get('QBE', 'qbe')
HOST = os.environ.get('HOST_CC', 'cc')

DECL = r'''
enum { W = 16 + 16 };
typedef unsigned int Word;
struct S { char before; Word u : W; signed int s : 32; char after; };
union U { unsigned int u : 32; int s : 32; char bytes[4]; };
struct P { char before; union { unsigned int p : 32; int n : 32; }; char after; };
struct Mix { char c; unsigned int a : (1 << 5), b : 32; short end; };
struct Flex { unsigned int n : 32; char data[]; };
extern struct S global;
extern union U overlay;
extern struct P promoted;
extern struct Mix mix[2];
extern struct Flex flex;
int mutate(struct S *p);
int examine(struct S *p);
struct S *once(struct S *p);
extern int calls;
'''
OWNER = DECL + r'''
struct S global = { .before = 7, .u = 4294967295U, .s = -123, .after = 9 };
union U overlay = { .u = 123456789U };
struct P promoted = { .before = 11, .p = 1234, .after = 12 };
struct Mix mix[2] = { { 1, 11U, 12U, 13 }, { 2, 21U, 22U, 23 } };
struct Flex flex = { .n = 42 };
int calls;
struct S *once(struct S *p) { calls++; return p; }
int mutate(struct S *p) {
  unsigned int old = p->u++;
  int x = (p->s += 10);
  return old == 4294967295U && p->u == 0 && x == -113 && p->s == -113;
}
int examine(struct S *p) {
  return p->before == 21 && p->u == 4000000000U && p->s == -17 && p->after == 22;
}
'''
COMPANION = DECL + r'''
int main(void) {
  struct S local = { 21, 4000000000U, -17, 22 };
  struct S copy = local;
  struct P p = { .before = 1, .p = 8, .after = 2 };
  if (sizeof(struct S)!=16 || _Alignof(struct S)!=4 ||
      sizeof(union U)!=4 || _Alignof(union U)!=4 || sizeof(struct P)!=12) return 1;
  if ((char *)&global.after - (char *)&global != 12 ||
      (char *)&promoted.after - (char *)&promoted != 8) return 2;
  if (global.before != 7 || global.u != 4294967295U || global.s != -123 || global.after != 9) return 3;
  if (overlay.u != 123456789U || promoted.p != 1234 || promoted.after != 12) return 4;
  if (!mutate(&global) || global.u != 0 || global.s != -113 || global.before != 7 || global.after != 9) return 5;
  if (!examine(&local) || !examine(&copy)) return 6;
  p.p <<= 2; if (p.p != 32 || p.before != 1 || p.after != 2) return 7;
  overlay.u = 4294967295U; if (overlay.u != 4294967295U) return 8;
  calls = 0; if ((once(&local)->u = 123U) != 123U || calls != 1 || local.u != 123U) return 9;
  calls = 0; if (once(&local)->s++ != -17 || calls != 1 || local.s != -16) return 10;
  calls = 0; if ((once(&local)->u += 7U) != 130U || calls != 1 || local.u != 130U) return 11;
  if (sizeof(struct Mix) != 16 || sizeof mix != 32 || mix[1].a != 21U || mix[1].b != 22U || mix[1].end != 23) return 13;
  mix[1].b = 33U; if (mix[1].a != 21U || mix[1].b != 33U || mix[1].end != 23) return 14;
  if (sizeof(struct Flex) != 4 || flex.n != 42 || (char *)flex.data - (char *)&flex != 4) return 15;
  if (_Generic(local.u, unsigned int: 1, default: 0) != 1 ||
      _Generic(local.s, int: 1, default: 0) != 1) return 12;
  return 0;
}
'''
# Diagnostics are not claimed to distinguish invalid C from valid-but-unsupported C.
REJECT = {
    'narrow': ('struct S { unsigned x:31; };', 'bit-fields are not supported yet'),
    'too-wide': ('struct S { unsigned x:33; };', 'bit-fields are not supported yet'),
    'zero-named': ('struct S { int x:0; };', 'bit-fields are not supported yet'),
    'negative': ('struct S { int x:-1; };', 'bit-fields are not supported yet'),
    'unnamed': ('struct S { unsigned :32; };', 'bit-fields are not supported yet'),
    'zero-barrier': ('struct S { unsigned :0; };', 'bit-fields are not supported yet'),
    'bool': ('struct S { _Bool x:1; };', 'bit-fields are not supported yet'),
    'short': ('struct S { unsigned short x:32; };', 'bit-fields are not supported yet'),
    'enum': ('enum E { A }; struct S { enum E x:32; };', 'bit-fields are not supported yet'),
    'long': ('struct S { unsigned long x:32; };', 'bit-fields are not supported yet'),
    'array': ('struct S { int x[1]:32; };', 'bit-fields are not supported yet'),
    'non-constant': ('int n; struct S { int x:n; };', 'bit-fields are not supported yet'),
    'not-ice': ('int n; struct S { int x:(n ? 32 : 32); };', 'bit-fields are not supported yet'),
    'float-width': ('struct S { int x:32.0; };', 'bit-fields are not supported yet'),
    'alignment': ('struct S { _Alignas(4) int x:32; };', 'alignment specifier cannot apply'),
    'volatile': ('struct S { volatile int x:32; };', 'bit-fields are not supported yet'),
    'address': ('struct S { int x:32; } s; int *p = &s.x;', 'cannot take the address of a bit-field'),
    'rvalue-sizeof': ('struct S { int x:32; }; int f(void) { return sizeof(((struct S){1}).x); }', 'sizeof cannot be applied to a bit-field'),
    'address-promoted': ('struct S { union { int x:32; }; } s; int *p = &(s.x);', 'cannot take the address of a bit-field'),
    'address-register': ('struct S { int x:32; }; int f(void) { register struct S s; int *p = &s.x; return 0; }', 'cannot take the address of a bit-field'),
    'sizeof': ('struct S { int x:32; } s; int a[sizeof(s.x)];', 'sizeof cannot be applied to a bit-field'),
    'typeof': ('struct S { int x:32; } s; typeof(s.x) a;', 'typeof cannot be applied to a bit-field'),
    'typeof-unqual': ('struct S { int x:32; } s; typeof_unqual(s.x) a;', 'typeof cannot be applied to a bit-field'),
    'offsetof': ('struct S { int x:32; }; int a[__kcc_offsetof(struct S, x)];', 'offsetof cannot designate a bit-field'),
    'const-write': ('struct S { const int x:32; } s; int f(void) { return s.x=1; }', 'modifiable lvalue'),
}
POSITIVE = r'''
struct S { const int c:32; unsigned u:32; };
struct S s = { .c = -1, .u = 2 };
int main(void) { int x=0; return sizeof(s.u+0)==4 && sizeof((x,s.u))==4 && sizeof(s.u=5)==4 && s.u==2 && s.c == -1 ? 0 : 1; }
'''

def run(args, **kw):
    result = subprocess.run([str(x) for x in args], text=True, capture_output=True, **kw)
    if result.returncode:
        raise AssertionError(f'{args}: {result.returncode}\n{result.stdout}\n{result.stderr}')
    return result


def object_file(src, out, compiler):
    if compiler == 'kcc':
        il = out.with_suffix('.ssa')
        asm = out.with_suffix('.s')
        il.write_text(run([KCC, src]).stdout)
        run([QBE, '-o', asm, il])
        run([HOST, '-c', asm, '-o', out])
    else:
        run([HOST, '-std=c11', '-pedantic-errors', '-Wall', '-Wextra', '-fno-common', '-c', src, '-o', out])


def main():
    assert KCC.is_file(), f'no compiler at {KCC}'
    (ROOT / 'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bit-fields-', dir=ROOT / 'build') as temp:
        d = Path(temp)
        (d/'owner.c').write_text(OWNER)
        (d/'companion.c').write_text(COMPANION)
        for owner, companion in [('kcc', 'host'), ('host', 'kcc'), ('kcc', 'kcc'), ('host', 'host')]:
            object_file(d/'owner.c', d/'owner.o', owner)
            object_file(d/'companion.c', d/'companion.o', companion)
            run([HOST, d/'owner.o', d/'companion.o', '-o', d/'program'])
            run([d/'program'])
        (d/'positive.c').write_text(POSITIVE)
        object_file(d/'positive.c', d/'positive.o', 'kcc')
        run([HOST, d/'positive.o', '-o', d/'positive'])
        run([d/'positive'])
        for name, (source, diagnostic) in REJECT.items():
            path = d/(name+'.c')
            path.write_text(source + '\n')
            result = subprocess.run([str(KCC), str(path)], text=True, capture_output=True)
            if result.returncode == 0 or diagnostic not in result.stderr or result.stdout:
                raise AssertionError(f'{name}: rc={result.returncode}\n{result.stderr}\n{result.stdout}')
    print(f'full-width bit-fields: 4 host/KCC combinations, 1 positive, {len(REJECT)} rejections passed')

if __name__ == '__main__':
    main()

"""Narrow bit-fields: SysV host interop, conversions, initialization and RMW."""
from pathlib import Path
import hashlib
import re
import os
import subprocess
import tempfile

from test_bit_fields import ROOT, KCC, HOST, QBE, object_file, run

DECL = r'''
struct Packed { char head; unsigned int a:8; signed int b:16; unsigned int c:8; char tail; };
struct Isolated { int lead; unsigned int u:3; int guard; signed int s:5; int end; };
struct Edge { char c; unsigned int x:31; short tail; };
union Both { signed int s:8; unsigned int u:16; int raw; };
struct Flex8 { unsigned int x:8; char data[]; };
struct Packed2 { unsigned a:16, b:16, c:8; char tail; };
struct Packed3 { char head; unsigned a:16; char middle; unsigned b:8; };
struct Separated { unsigned a:3, b:31; };
struct NextFull { unsigned a:8, b:32; };
struct Small { char head; signed a:3; char middle; unsigned b:7; char tail; };
struct Wide { char head; unsigned a:24; signed b:24; char tail; };
struct Promoted { char head; union { unsigned x:8; signed y:16; }; char tail; };
extern struct Promoted promoted;
extern struct Small small;
extern struct Wide wide;
extern struct Packed2 packed2;
extern struct Packed3 packed3;
extern struct Separated separated;
extern struct NextFull nextfull;
extern struct Packed packed;
extern struct Isolated isolated;
extern union Both both;
extern int calls;
struct Isolated *once(struct Isolated *p);
int check_foreign(struct Packed *p, struct Isolated *q);
'''
OWNER = DECL + r'''
struct Promoted promoted = { .head=2, .x=44, .tail=3 };
struct Small small = { 1, -3, 2, 99, 3 };
struct Wide wide = { 4, 0xfedcba, -123456, 5 };
struct Packed2 packed2 = { 0x1234, 0x5678, 42, 11 };
struct Packed3 packed3 = { 9, 0xabcd, 8, 7 };
struct Separated separated = { 7, 2147483647U };
struct NextFull nextfull = { 123, 4000000000U };
struct Packed packed = { .head=12, .a=250, .b=-1000, .c=201, .tail=13 };
struct Isolated isolated = { 42, 7, 77, -9, 91 };
union Both both = { .s=-12 };
int calls;
struct Isolated *once(struct Isolated *p) { calls++; return p; }
int check_foreign(struct Packed *p, struct Isolated *q) {
  if (p->head!=4 || p->a!=5 || p->b!=-6 || p->c!=7 || p->tail!=8) return 0;
  if (q->lead!=1 || q->u!=2 || q->guard!=3 || q->s!=-4 || q->end!=5) return 0;
  p->a=199; p->b=-1200; q->u=6; q->s=-13;
  return 1;
}
'''
COMPANION = DECL + r'''
int main(void) {
  struct Packed p = { 4, 5, -6, 7, 8 };
  struct Isolated q = { 1, 2, 3, -4, 5 };
  struct Packed copy = p;
  struct Edge edge = { 1, 2147483647U, 9 };
  struct Flex8 flex = { .x = 33 };
  if (sizeof(struct Packed)!=8 || _Alignof(struct Packed)!=4 ||
      (char *)&p.tail-(char *)&p!=5 || sizeof(struct Isolated)!=20 ||
      sizeof(struct Edge)!=12 || (char *)&edge.tail-(char *)&edge!=8 ||
      sizeof(struct Flex8)!=4 || (char *)flex.data-(char *)&flex!=1) return 1;
  if (sizeof(struct Promoted)!=12 || promoted.head!=2 || promoted.x!=44 || promoted.tail!=3) return 17;
  promoted.x=233; if (promoted.x!=233 || promoted.head!=2 || promoted.tail!=3) return 18;
  if (sizeof(struct Small)!=8 || (char *)&small.middle-(char *)&small!=2 ||
      (char *)&small.tail-(char *)&small!=4 || small.head!=1 || small.a!=-3 ||
      small.middle!=2 || small.b!=99 || small.tail!=3 || sizeof(struct Wide)!=8 ||
      (char *)&wide.tail-(char *)&wide!=7 || wide.head!=4 || wide.a!=0xfedcba ||
      wide.b!=-123456 || wide.tail!=5) return 15;
  small.a=3; small.b=127; wide.a=0xabcdef; wide.b=-600000;
  if (small.head!=1 || small.middle!=2 || small.tail!=3 || wide.head!=4 || wide.tail!=5 ||
      small.a!=3 || small.b!=127 || wide.a!=0xabcdef || wide.b!=-600000) return 16;
  if (sizeof(struct Packed2)!=8 || (char *)&packed2.tail-(char *)&packed2!=5 ||
      sizeof(struct Packed3)!=8 || (char *)&packed3.middle-(char *)&packed3!=3 ||
      sizeof(struct Separated)!=8 || sizeof(struct NextFull)!=8 ||
      packed2.a!=0x1234 || packed2.b!=0x5678 || packed2.c!=42 || packed2.tail!=11 ||
      packed3.head!=9 || packed3.a!=0xabcd || packed3.middle!=8 || packed3.b!=7 ||
      separated.a!=7 || separated.b!=2147483647U || nextfull.a!=123 || nextfull.b!=4000000000U) return 13;
  packed2.b=0x1234; packed3.a=0x6789; separated.a=3; nextfull.b=42;
  if (packed2.a!=0x1234 || packed2.b!=0x1234 || packed2.c!=42 || packed2.tail!=11 ||
      packed3.head!=9 || packed3.middle!=8 || packed3.b!=7 || separated.b!=2147483647U || nextfull.a!=123) return 14;
  if (packed.head!=12 || packed.a!=250 || packed.b!=-1000 || packed.c!=201 || packed.tail!=13 ||
      isolated.u!=7 || isolated.s!=-9 || both.s!=-12) return 2;
  if (!check_foreign(&p,&q) || p.a!=199 || p.b!=-1200 || p.c!=7 || p.tail!=8 ||
      q.u!=6 || q.s!=-13 || q.guard!=3 || copy.a!=5) return 3;
  if (q.u - 7 >= 0 || ~q.u >= 0 || (1 ? q.u : -1) - 7 >= 0 ||
      _Generic(+q.u, int: 1, default: 0)!=1 ||
      (0, q.u)-7 >= 0 || (q.u=6)-7 >= 0 || (q.u++)-7 >= 0) return 4;
  q.u=6;
  calls=0; if ((once(&q)->u=11)!=3 || calls!=1 || q.u!=3 || q.guard!=3) return 5;
  calls=0; if (once(&q)->u++!=3 || calls!=1 || q.u!=4) return 6;
  calls=0; if ((once(&q)->u+=6)!=2 || calls!=1 || q.u!=2) return 7;
  calls=0; if ((once(&q)->s+=3)!=-10 || calls!=1 || q.s!=-10) return 8;
  if ((p.a=258)!=2 || p.a!=2 || p.b!=-1200 || p.c!=7 || p.head!=4 || p.tail!=8) return 9;
  if ((++p.b)!=-1199 || p.b++!=-1199 || p.b!=-1198) return 10;
  both.u=65535; if (both.u!=65535) return 11;
  if (edge.x!=2147483647U || edge.tail!=9 || flex.x!=33) return 12;
  return 0;
}
'''
LOCAL = r'''
/* Formerly rejected layouts now have runtime coverage. */
struct Shared34 { unsigned a:3, b:4; };
struct Shared38 { unsigned a:3, b:8; };
struct Shared1216 { unsigned a:12, b:16; };
struct P { unsigned a:8; signed b:16; unsigned c:8; };
struct P global = { .a={3}, .b={-7}, .c={9}, .a={4} };
struct N { char c; unsigned a:3; char b; };
struct N gn = { .c=4, .a={7}, .b=9 };
int main(void) {
  struct Shared34 x={5,9}; struct Shared38 y={5,199}; struct Shared1216 z={3000,60000};
  if(x.a!=5 || x.b!=9 || y.a!=5 || y.b!=199 || z.a!=3000 || z.b!=60000) return 6;
  x.b=7; y.b=88; z.b=12345;
  if(x.a!=5 || x.b!=7 || y.a!=5 || y.b!=88 || z.a!=3000 || z.b!=12345) return 7;
  struct N n = { .c=4, .a={7}, .b=9 };
  if (gn.c!=4 || gn.a!=7 || gn.b!=9 || n.c!=4 || n.a!=7 || n.b!=9) return 4;
  if ((n.a+=2)!=1 || n.c!=4 || n.b!=9) return 5;
  struct P p = { .a={5}, .b={-8}, .c={10}, .a={6} };
  if (global.a!=4 || global.b!=-7 || global.c!=9) return 1;
  if (p.a!=6 || p.b!=-8 || p.c!=10) return 2;
  if (!_Generic(p.a, unsigned char:1, default:0)) return 8;
  p.b=32768; if (p.b!=-32768 || p.a!=6 || p.c!=10) return 3;
  return 0;
}
'''
REJECT = [
    'struct S { unsigned a:0; };',
    'struct S { unsigned :0; };',
    'struct S { volatile unsigned a:8; };',
    'struct S { [[gnu::packed]] unsigned a:8; };',
    'struct S { [[gnu::aligned(1)]] unsigned a:8; };',
    'struct S { unsigned a:8; } s; unsigned *p = &s.a;',
    'struct S { unsigned a:8; } s; int n[sizeof(s.a)];',
    'struct S { unsigned a:8; }; int n[__kcc_offsetof(struct S, a)];',
    'struct S { const unsigned a:8; } s; void f(void) { s.a=1; }',
]

def width_matrix(d):
    # Exercise every width in both directions with a preceding and following
    # byte, exposing starts within a unit as well as unit-boundary rollover.
    declarations, owner, checks = [], [], []
    for width in range(1, 33):
        for signed, tag in [(False, 'u'), (True, 's')]:
            name = f'{tag}{width}'
            typ = 'signed' if signed else 'unsigned'
            declarations.append(f'struct {name} {{ char pre; {typ} x:{width}; char post; }};')
            declarations.append(f'extern struct {name} {name}; extern int size_{name};')
            declarations.append(f'{typ} int read_{name}(void);')
            value = -1 if signed else 1
            changed = (0 if width == 1 else -2) if signed else 1
            owner.append(f'struct {name} {name} = {{ 11, {value}, 22 }};')
            owner.append(f'int size_{name} = sizeof(struct {name});')
            owner.append(f'{typ} int read_{name}(void) {{ return {name}.x; }}')
            checks.append(f'if (size_{name} != sizeof(struct {name}) || {name}.pre != 11 || '
                          f'{name}.x != ({value}) || {name}.post != 22) return 1;')
            checks.append(f'{name}.x = {changed}; if (read_{name}() != ({changed}) || '
                          f'{name}.pre != 11 || {name}.post != 22) return 2;')
    decl = '\n'.join(declarations) + '\n'
    (d/'matrix-owner.c').write_text(decl + '\n'.join(owner) + '\n')
    (d/'matrix-companion.c').write_text(decl + 'int main(void) {\n' + '\n'.join(checks) + '\nreturn 0; }\n')
    for a, b in [('host', 'kcc'), ('kcc', 'host')]:
        object_file(d/'matrix-owner.c', d/'matrix-owner.o', a)
        object_file(d/'matrix-companion.c', d/'matrix-companion.o', b)
        run([HOST, d/'matrix-owner.o', d/'matrix-companion.o', '-o', d/'matrix'])
        run([d/'matrix'])

# The original fixture combines seven checks under return 4. Clang 18.1
# evaluates the postfix-expression arithmetic differently from GCC/KCC.
# Accept only the exact original, host version and result, then independently
# locate the failing subexpression and execute all later checks using a
# supplemental explicit-int cast. Neither run is an original-source agreement.
def clang_postfix_discrepancy(d, owner_kind, execution):
    version = subprocess.run([HOST, '--version'], capture_output=True, text=True, timeout=10)
    original = d/'companion.c'
    if not (version.returncode == 0 and re.search(r'clang version 18\.1\.\d+\b', version.stdout)
            and hashlib.sha256(original.read_bytes()).hexdigest() ==
            '9fe8ffb88d9ef8df6a9fd4a7c29d4be577f37711e63d43fd472b96f4e10a5806'
            and execution.returncode == 4 and not execution.stdout and not execution.stderr):
        return False
    combined = """if (q.u - 7 >= 0 || ~q.u >= 0 || (1 ? q.u : -1) - 7 >= 0 ||
      _Generic(+q.u, int: 1, default: 0)!=1 ||
      (0, q.u)-7 >= 0 || (q.u=6)-7 >= 0 || (q.u++)-7 >= 0) return 4;"""
    isolated = """if (q.u - 7 >= 0) return 41;
  if (~q.u >= 0) return 42;
  if ((1 ? q.u : -1) - 7 >= 0) return 43;
  if (_Generic(+q.u, int: 1, default: 0)!=1) return 44;
  if ((0, q.u)-7 >= 0) return 45;
  if ((q.u=6)-7 >= 0) return 46;
  if ((q.u++)-7 >= 0) return 47;"""
    assert COMPANION.count(combined) == 1
    diagnostic = d/'diagnostic.c'
    diagnostic.write_text(COMPANION.replace(combined, isolated))
    object_file(diagnostic, d/'diagnostic.o', 'host')
    run([HOST, d/'owner.o', d/'diagnostic.o', '-o', d/'diagnostic'])
    result = subprocess.run([str(d/'diagnostic')], capture_output=True, text=True, timeout=10)
    assert (result.returncode, result.stdout, result.stderr) == (47, '', ''), (owner_kind, result)
    # This is a supplemental program only, not a native comparison of the
    # original. It reaches all checks after the known divergent expression.
    cast = '(q.u++)-7 >= 0'
    assert COMPANION.count(cast) == 1
    supplemental = d/'supplemental.c'
    supplemental.write_text(COMPANION.replace(cast, '(int)(q.u++)-7 >= 0'))
    object_file(supplemental, d/'supplemental.o', 'host')
    run([HOST, d/'owner.o', d/'supplemental.o', '-o', d/'supplemental'])
    run([d/'supplemental'])
    print(f'Clang 18.1 postfix bit-field discrepancy ({owner_kind}/host): '
          'original NOT a runtime agreement; supplemental cast passed')
    return True


def main():
    (ROOT/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='narrow-fields-', dir=ROOT/'build') as tmp:
        d = Path(tmp)
        (d/'owner.c').write_text(OWNER)
        (d/'companion.c').write_text(COMPANION)
        for a, b in [('host','host'), ('host','kcc'), ('kcc','host'), ('kcc','kcc')]:
            object_file(d/'owner.c', d/'owner.o', a)
            object_file(d/'companion.c', d/'companion.o', b)
            run([HOST, d/'owner.o', d/'companion.o', '-o', d/'test'])
            result = subprocess.run([str(d/'test')], capture_output=True, text=True, timeout=10)
            if result.returncode or result.stdout or result.stderr:
                if b != 'host' or not clang_postfix_discrepancy(d, a, result):
                    raise AssertionError((a, b, result.returncode, result.stdout, result.stderr))
        width_matrix(d)
        (d/'local.c').write_text(LOCAL)
        object_file(d/'local.c', d/'local.o', 'kcc')
        run([HOST, d/'local.o', '-o', d/'local'])
        run([d/'local'])
        for i, source in enumerate(REJECT):
            path = d/f'reject{i}.c'; path.write_text(source)
            r = subprocess.run([str(KCC), str(path)], text=True, capture_output=True)
            if r.returncode == 0 or r.stdout or not ('bit-field' in r.stderr or 'modifiable lvalue' in r.stderr or 'layout-altering GNU attribute' in r.stderr):
                raise AssertionError((source, r.returncode, r.stdout, r.stderr))
    print(f'narrow bit-fields: 4 host/KCC combinations exercised (reported discrepancies are NOT agreements), 64-width matrix in both directions, initializer test, {len(REJECT)} rejections passed')

if __name__ == '__main__':
    main()

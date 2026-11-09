"""Native Clang/QBE differential coverage for arbitrary-width BitInt values.

All programs are defined C; cross-object cases run with KCC and Clang on each
side. Non-native aggregate and variadic ABI and atomics remain rejected.
"""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
KCC = ROOT / 'build/kcc'
QBE = os.environ.get('QBE', 'qbe')
CLANG = os.environ.get('CLANG', 'clang')

def run(args, **kwargs):
    result = subprocess.run([str(x) for x in args], capture_output=True, text=True, timeout=90, **kwargs)
    if result.returncode:
        raise AssertionError((args, result.returncode, result.stdout, result.stderr))
    return result

def compile_kcc(d, source, name):
    c = d / f'{name}.c'; c.write_text(source)
    ssa = d / f'{name}.ssa'; ssa.write_text(run([KCC, c]).stdout)
    asm = d / f'{name}.s'; obj = d / f'{name}.o'
    run([QBE, '-t', 'amd64_sysv', '-o', asm, ssa])
    run([CLANG, '-c', asm, '-o', obj])
    return obj

def compile_clang(d, source, name):
    c = d / f'{name}.c'; c.write_text(source)
    obj = d / f'{name}.o'
    run([CLANG, '-std=c2x', '-O2', '-Werror', '-Wno-constant-logical-operand', '-c', c, '-o', obj])
    return obj

def main():
    types = [(w, u) for w in range(1, 65) for u in (0, 1) if u or w > 1]
    declarations, implementation, tests = [], [], []
    for w, u in types:
        tag = f'{"u" if u else "s"}{w}'
        name = f'T{tag}'
        spelling = ('unsigned ' if u else '') + f'_BitInt({w})'
        declarations.append(f'typedef {spelling} {name}; extern {name} g{tag}; {name} id{tag}({name}); {name} add{tag}({name},{name}); {name} pack{tag}({','.join([name]*10)}); struct R{tag} {{ {name} x; char c; {name} y; }}; {name} touch{tag}(struct R{tag} *, {name});')
        implementation.append(f'{name} g{tag}=({name})-1; {name} id{tag}({name} x){{return x;}} {name} add{tag}({name} x,{name} y){{return x+y;}} {name} pack{tag}({','.join(f'{name} p{i}' for i in range(10))}){{return p9;}} {name} touch{tag}(struct R{tag} *p,{name} v){{ {name} old=p->x; p->x=v; return old; }}')
        size = 1 if w <= 8 else 2 if w <= 16 else 4 if w <= 32 else 8
        expected = (1 << w) - 1 if u else (1 << 64) - 1
        # Each function keeps local counts and expression depths bounded.
        shift = '' if w == 1 else f' || (unsigned long)(x >> 1)!={expected if not u else expected >> 1}UL'
        boundary = 1 << (w - 1)
        boundary_expected = boundary if u else (boundary | (((1 << 64) - 1) ^ ((1 << w) - 1)))
        tests.append(f'''int check{tag}(void) {{
 {name} x=({name})-1, y=({name})1, edge=({name}){boundary}UL; volatile {name} v=x; {name} a[2]={{0,x}}; {name} (*fp)({name})=id{tag};
 struct L{tag} {{ {name} n; int z; }} local={{x,7}}; struct R{tag} rec={{edge,7,x}};
 if(sizeof(x)!={size} || _Alignof({name})!={size}) return 1;
 if((unsigned long)x!={expected}UL || (unsigned long)g{tag}!={expected}UL) return 2;
 if((unsigned long)id{tag}(x)!={expected}UL || (unsigned long)v!={expected}UL || (unsigned long)a[1]!={expected}UL) return 3;
 if(add{tag}(x,y)!=0 || x+y!=0 || (unsigned long)pack{tag}(y,y,y,y,y,y,y,y,y,edge)!={boundary_expected}UL) return 4;
 if ((unsigned long)(x | ({name})0)!={expected}UL{shift}) return 5;
 x+=y; if(x!=0) return 6; x--; if((unsigned long)x!={expected}UL) return 7;
 if((unsigned long)*(&a[0]+({name})1)!={expected}UL || (unsigned long)local.n!={expected}UL || local.z!=7) return 8;
 if ((unsigned long)fp(edge)!={boundary_expected}UL || (unsigned long)(x*y)!={expected}UL || x/y!=x || x%y!=0 || ~x!=0) return 9;
 if (sizeof(rec)!={3*size} || (unsigned long)touch{tag}(&rec,y)!={boundary_expected}UL || rec.x!=y || rec.c!=7 || rec.y!=x) return 11;
 switch (x) {{ case ({name})-1: break; default: return 10; }}
 return 0; }}''')
    with tempfile.TemporaryDirectory(prefix='bitint-arbitrary-', dir=ROOT/'build') as tmp:
        d = Path(tmp)
        for start in range(0, len(types), 16):
            group = types[start:start+16]
            decl = '\n'.join(declarations[start:start+16])+'\n'
            body = decl+'\n'.join(implementation[start:start+16])+'\n'
            caller = decl+'\n'.join(tests[start:start+16])+'\nint main(void) {\n' + '\n'.join(f'if(check{"u" if u else "s"}{w}()) return {i + 1};' for i,(w,u) in enumerate(group))+'\nreturn 0; }\n'
            for side in (0, 1):
                ko = compile_kcc(d, body if side == 0 else caller, f'k{side}')
                co = compile_clang(d, caller if side == 0 else body, f'c{side}')
                exe = d/f'exe{side}'
                run([CLANG, ko, co, ROOT/'build/libkccrt.a', '-o', exe])
                result = subprocess.run([str(exe)], timeout=10)
                if result.returncode:
                    raise AssertionError(('group', start, 'side', side, 'type', group[result.returncode-1]))
    print('Clang cross-object BitInt values, fixed calls, objects and storage passed for all 127 signed/unsigned types')

if __name__ == '__main__': main()

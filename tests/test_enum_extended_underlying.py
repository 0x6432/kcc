"""C23 fixed enums backed by the target's wide-field extended integer types.

GCC 11 cannot compile fixed enums; primitive long surrogates check ABI and
storage, not native C23 syntax or arithmetic policy.
"""
from pathlib import Path
import subprocess
import tempfile
from test_bit_fields import ROOT, HOST, KCC, object_file, run


def main():
    (ROOT/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='extended-enum-', dir=ROOT/'build') as tmp:
        d=Path(tmp)
        for width in range(33,64):
            for signed in (True,False):
                base='signed long' if signed else 'unsigned long'
                value='-1' if signed else f'{(1<<width)-1}UL'
                runtime='e!=-1 || e/2!=0' if signed else 'e+1!=0 || ~e!=0'
                text=f'''
                struct Raw {{ {base} x:{width}; }} raw;
                typedef typeof(+raw.x) T;
                enum E : T {{ ZERO=0, VALUE={value} }};
                enum E e=VALUE; const enum E ce=VALUE;
                struct F {{ enum E x:{width}; }} f={{VALUE}};
                int main(void) {{
                  if(sizeof(e)!=8 || _Alignof(enum E)!=8 || {runtime}) return 1;
                  if(!_Generic(e,T:1,default:0) || f.x!=VALUE || ce!=VALUE) return 2;
                  auto inferred=f.x; if(!_Generic(inferred,T:1,default:0)) return 3;
                  if({'0' if signed else 'inferred+1!=0'}) return 4;
                  e=1; e+=2; if(e!=3) return 5;
                  f.x=1; f.x++; if(f.x!=2) return 6;
                  return 0;
                }}
                '''
                (d/'case.c').write_text(text)
                object_file(d/'case.c',d/'case.o','kcc'); run([HOST,d/'case.o','-o',d/'case']); run([d/'case'])
        for signed in (True,False):
            base='signed long' if signed else 'unsigned long'
            value='-1' if signed else '8589934591UL'
            kccdecl=f'''struct Raw {{ {base} x:33; }} raw; typedef typeof(+raw.x) T;
                         enum E : T {{ VALUE={value} }}; typedef enum E EType;'''
            hostdecl=f'typedef {base} EType;'
            common='''extern EType e; EType echo(EType); int receive(int,...);'''
            owner='''#include <stdarg.h>
                EType e=VALUE; EType echo(EType x) {return x;}
                int receive(int n, ...) {va_list ap; va_start(ap,n);
                  EType x=va_arg(ap,EType); va_end(ap); return n==1 && x==VALUE;}'''
            companion='''int main(void) {
                if(sizeof(e)!=8 || echo(e)!=VALUE || !receive(1,e)) return 1;
                return 0; }'''
            for left,right in [('kcc','host'),('host','kcc'),('kcc','kcc'),('host','host')]:
                for filename,compiler,body in [('owner.c',left,owner),('companion.c',right,companion)]:
                    # The type-source record is a definition, so give it internal linkage.
                    decl=(kccdecl.replace(' raw;', ' raw;').replace('struct Raw {', 'static struct Raw {')
                          if compiler=='kcc' else hostdecl+'\n#define VALUE ('+value+')')
                    (d/filename).write_text(decl+'\n'+common+'\n'+body+'\n')
                object_file(d/'owner.c',d/'owner.o',left)
                object_file(d/'companion.c',d/'companion.o',right)
                run([HOST,d/'owner.o',d/'companion.o','-o',d/'cross']); run([d/'cross'])
        # Extended types of the same signedness but distinct widths are not compatible.
        (d/'bad.c').write_text('''struct S { unsigned long a:33, b:34; } s;
          typedef typeof(+s.a) A; typedef typeof(+s.b) B;
          enum E : A { X }; int f(enum E x) { return _Generic(x,B:1,default:0); }
          int main(void) {return f(X);}''')
        object_file(d/'bad.c',d/'bad.o','kcc'); run([HOST,d/'bad.o','-o',d/'bad']); run([d/'bad'])
        for name, text in {
          'field-too-wide': "struct S {unsigned long x:33;} s; typedef typeof(+s.x) U; enum E:U {A}; struct T {enum E x:34;};",
          'enum-out-of-range': "struct S {unsigned long x:33;} s; typedef typeof(+s.x) U; enum E:U {A=8589934592UL};",
          'duplicate-compatible-associations': "struct S {unsigned long x:33;} s; typedef typeof(+s.x) U; enum E:U {A}; int f(enum E x){return _Generic(x,U:1,enum E:2);}",
        }.items():
            (d/'reject.c').write_text(text)
            result=subprocess.run([KCC,d/'reject.c'],capture_output=True,text=True)
            if result.returncode==0: raise AssertionError(f'{name} was incorrectly accepted')
    print('extended-underlying enums: 62 signed/unsigned widths, inference, static and bit-field behavior; GCC surrogate cross-object fixed/variadic ABI passed')

if __name__=='__main__': main()

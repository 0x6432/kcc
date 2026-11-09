"""Bounded SysV aggregate ellipsis and va_arg cross-object ABI checks."""
from pathlib import Path
import subprocess
import tempfile
from test_aggregate_abi import ROOT, KCC, test_pair, reject


def main():
    with tempfile.TemporaryDirectory(prefix='aggregate-varargs-', dir=ROOT/'build') as tmp:
        d = Path(tmp)
        # All extents exercise rounded register slots and stack overflow copies.
        for n in list(range(1, 17)) + [17, 24, 63, 64, 65, 255, 256, 1024]:
            decl = '#include <stdarg.h>\n' + f'struct S {{ unsigned char a[{n}]; }}; '
            body = ('int read(int tag,...) { va_list a; va_start(a,tag); '
                    'struct S s=va_arg(a,struct S); int z=va_arg(a,int); va_end(a); '
                    f'return tag==7 && s.a[0]==40 && s.a[{n-1}]==40 && z==2; }} ')
            caller = ('int read(int,...); int main(void) { struct S s={0}; '
                      f's.a[0]=40; s.a[{n-1}]=40; return !read(7,s,2); }}')
            test_pair(d, decl, body, caller)
        # Both classes, both orders, SSE-only pairs, union, bit-fields.
        shapes = [
            ('struct S { double d; long x; };', '{1.5,40}', 's.d==1.5 && s.x==40'),
            ('struct S { long x; double d; };', '{40,1.5}', 's.d==1.5 && s.x==40'),
            ('struct S { double x,y; };', '{1.5,2.5}', 's.x==1.5 && s.y==2.5'),
            ('struct S { long x,y; };', '{40,2}', 's.x==40 && s.y==2'),
            ('union S { double x; long y; };', '{.y=40}', 's.y==40'),
            ('struct S { unsigned a:3,b:5; double x; };', '{3,12,1.5}', 's.a==3 && s.b==12 && s.x==1.5'),
        ]
        for shape, init, check in shapes:
            tag = 'union' if shape.startswith('union') else 'struct'
            decl = '#include <stdarg.h>\n' + shape + ' '
            body = (f'int read(int tag,...) {{ va_list a,b; va_start(a,tag); va_copy(b,a); '
                    f'{tag} S s=va_arg(a,{tag} S); {tag} S t=va_arg(b,{tag} S); '
                    'int z=va_arg(a,int); int k=va_arg(b,int); va_end(a); va_end(b); '
                    f'return ({check}) && ({check.replace("s.", "t.")}) && z==2 && k==2; }} ')
            caller = f'int read(int,...); int main(void) {{ {tag} S s={init}; return !read(7,s,2); }}'
            test_pair(d, decl, body, caller)
        # Register exhaustion forces whole-aggregate rollback; subsequent
        # scalar reads still use the unconsumed register bank.
        decl = '#include <stdarg.h>\nstruct S { double d; long x; }; '
        body = '''int read(int tag,...) { va_list ap; va_start(ap,tag);
          int a=va_arg(ap,int), b=va_arg(ap,int), c=va_arg(ap,int), d=va_arg(ap,int), e=va_arg(ap,int);
          struct S s=va_arg(ap,struct S); double tail=va_arg(ap,double); va_end(ap);
          return a+b+c+d+e==15 && s.x==40 && s.d==1.5 && tail==2.5; }'''
        caller = 'int read(int,...); int main(void) { struct S s={1.5,40}; return !read(0,1,2,3,4,5,s,2.5); }'
        test_pair(d, decl, body, caller)
        body = '''int read(int tag,...) { va_list ap; va_start(ap,tag);
          double a=va_arg(ap,double), b=va_arg(ap,double), c=va_arg(ap,double), d=va_arg(ap,double);
          double e=va_arg(ap,double), f=va_arg(ap,double), g=va_arg(ap,double), h=va_arg(ap,double);
          struct S s=va_arg(ap,struct S); int tail=va_arg(ap,int); va_end(ap);
          return a+b+c+d+e+f+g+h==8.0 && s.x==40 && s.d==1.5 && tail==2; }'''
        caller = 'int read(int,...); int main(void) { struct S s={1.5,40}; return !read(0,1.,1.,1.,1.,1.,1.,1.,1.,s,2); }'
        test_pair(d, decl, body, caller)
        # Both slots of one register class must be available, not just the first.
        decl = '#include <stdarg.h>\nstruct S { long x,y; }; '
        body = '''int read(int tag,...) { va_list ap; va_start(ap,tag);
          int a=va_arg(ap,int), b=va_arg(ap,int), c=va_arg(ap,int), d=va_arg(ap,int);
          struct S s=va_arg(ap,struct S); int tail=va_arg(ap,int); va_end(ap);
          return a+b+c+d==10 && s.x==40 && s.y==9 && tail==2; }'''
        caller = 'int read(int,...); int main(void) { struct S s={40,9}; return !read(0,1,2,3,4,s,2); }'
        test_pair(d, decl, body, caller)
        decl = '#include <stdarg.h>\nstruct S { double x,y; }; '
        body = '''int read(int tag,...) { va_list ap; va_start(ap,tag);
          double a=va_arg(ap,double), b=va_arg(ap,double), c=va_arg(ap,double), d=va_arg(ap,double);
          double e=va_arg(ap,double), f=va_arg(ap,double), g=va_arg(ap,double);
          struct S s=va_arg(ap,struct S); double tail=va_arg(ap,double); va_end(ap);
          return a+b+c+d+e+f+g==7.0 && s.x==1.5 && s.y==2.5 && tail==3.; }'''
        caller = 'int read(int,...); int main(void) { struct S s={1.5,2.5}; return !read(0,1.,1.,1.,1.,1.,1.,1.,s,3.); }'
        test_pair(d, decl, body, caller)
        # Named mixed record consumes both register banks before va_start.
        decl = '#include <stdarg.h>\nstruct S { double d; long x; }; '
        body = '''int read(struct S named,...) { va_list ap; va_start(ap,named);
          struct S s=va_arg(ap,struct S); int tail=va_arg(ap,int); va_end(ap);
          return named.x==7 && named.d==3. && s.x==40 && s.d==1.5 && tail==2; }'''
        caller = 'int read(struct S,...); int main(void) { struct S n={3.,7},s={1.5,40}; return !read(n,s,2); }'
        test_pair(d, decl, body, caller)
        # A stack record followed by another stack argument must advance correctly.
        decl = '#include <stdarg.h>\nstruct S { char a[25]; }; '
        body = '''int read(int tag,...) { va_list ap; va_start(ap,tag);
          struct S s=va_arg(ap,struct S); struct S t=va_arg(ap,struct S); va_end(ap);
          return s.a[0]==40 && s.a[24]==4 && t.a[0]==2 && t.a[24]==9; }'''
        caller = 'int read(int,...); int main(void) { struct S s={0},t={0}; s.a[0]=40;s.a[24]=4;t.a[0]=2;t.a[24]=9;return !read(0,s,t); }'
        test_pair(d, decl, body, caller)
        # Each syntactic va_arg has a stable entry slot across loop iterations;
        # unevaluated sizeof does not advance the list or consume a slot at runtime.
        decl = '#include <stdarg.h>\nstruct S { long x; double d; }; '
        body = '''int read(int n,...) { va_list ap; va_start(ap,n); long sum=0; int i=0;
          if(sizeof(va_arg(ap,struct S))!=sizeof(struct S)) return 0;
          while(i<n) { struct S s=va_arg(ap,struct S); sum+=s.x+(long)s.d; i++; }
          va_end(ap); return sum==42; }'''
        caller = 'int read(int,...); int main(void) { struct S a={10,1.},b={20,2.},c={3,6.}; return !read(3,a,b,c); }'
        test_pair(d, decl, body, caller)
        # Six prior GP values place a scalar on the stack. The following
        # 16-aligned memory record must round the overflow pointer up to 16.
        decl = '#include <stdarg.h>\nstruct S { _Alignas(16) long x[5]; }; '
        body = '''int read(int tag,...) { va_list ap; va_start(ap,tag);
          int a=va_arg(ap,int), b=va_arg(ap,int), c=va_arg(ap,int);
          int d=va_arg(ap,int), e=va_arg(ap,int), f=va_arg(ap,int);
          struct S s=va_arg(ap,struct S); long tail=va_arg(ap,long); va_end(ap);
          return a+b+c+d+e+f==21 && s.x[0]==40 && s.x[4]==9 && tail==2; }'''
        caller = 'int read(int,...); int main(void) { struct S s={{40,0,0,0,9}}; return !read(0,1,2,3,4,5,6,s,2L); }'
        test_pair(d, decl, body, caller)
        # A 16-byte-aligned register record also rolls back atomically to a
        # correctly aligned stack slot if one register class is exhausted.
        decl = '#include <stdarg.h>\nstruct S { _Alignas(16) double d; long x; }; '
        body = '''int read(int tag,...) { va_list ap; va_start(ap,tag);
          int a=va_arg(ap,int), b=va_arg(ap,int), c=va_arg(ap,int);
          int d=va_arg(ap,int), e=va_arg(ap,int), f=va_arg(ap,int);
          struct S s=va_arg(ap,struct S); double tail=va_arg(ap,double); va_end(ap);
          return a+b+c+d+e+f==21 && s.x==40 && s.d==1.5 && tail==2.5; }'''
        caller = 'int read(int,...); int main(void) { struct S s={1.5,40}; return !read(0,1,2,3,4,5,6,s,2.5); }'
        test_pair(d, decl, body, caller)
        # Static resource budget is charged even for discarded va_arg results.
        prefix = ('#include <stdarg.h>\nstruct S { int x; }; '
                  'int f(int n, ...) { va_list a; va_start(a,n); ')
        (d/'limit.c').write_text(prefix + '(void)va_arg(a,struct S);'*256 + 'va_end(a);return 0;}')
        p = subprocess.run([str(KCC), str(d/'limit.c')], capture_output=True, text=True)
        assert p.returncode == 0, p.stderr
        reject(d, prefix + '(void)va_arg(a,struct S);'*257 + 'va_end(a);return 0;}',
               'function exceeds record value temporary limit (256)')
        reject(d, '#include <stdarg.h>\nstruct S {int n; char x[];}; '
               'void f(int n,...){va_list a;va_start(a,n);(void)va_arg(a,struct S);}',
               'aggregate ABI unsupported (M21): requires complete record without flexible array, size 1..1024, alignment <= 16 and representable eightbytes')
        reject(d, '#include <stdarg.h>\nstruct S { _Alignas(16) int x; }; '
               'void f(int n,...){va_list a;va_start(a,n);(void)va_arg(a,struct S);}',
               'aggregate ABI unsupported (M21): requires complete record without flexible array, size 1..1024, alignment <= 16 and representable eightbytes')
    print('Aggregate varargs: integer/SSE/mixed and memory records, va_copy, register rollback and stack advancement, both cross-object directions passed')

if __name__ == '__main__':
    main()

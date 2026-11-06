"""Scalar SysV variadic calls: direct/indirect, promotions, stack and diagnostics."""
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KCC = Path(os.environ.get('KCC', ROOT / 'build/kcc'))
QBE = os.environ.get('QBE')
HOST = os.environ.get('HOST_CC', 'cc')


def checked(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result


def link_and_run(directory, kcc_text, host_text):
    source = directory / 'source.c'
    il = directory / 'source.ssa'
    assembly = directory / 'source.s'
    obj = directory / 'source.o'
    companion = directory / 'host.c'
    host_obj = directory / 'host.o'
    program = directory / 'program'
    source.write_text(kcc_text)
    result = checked([str(KCC), str(source)])
    assert not result.stderr, result.stderr
    il.write_text(result.stdout)
    checked([QBE, '-t', 'amd64_sysv', '-o', str(assembly), str(il)])
    checked([HOST, '-c', str(assembly), '-o', str(obj)])
    companion.write_text(host_text)
    checked([HOST, '-std=c2x', '-O2', '-Wall', '-Wextra', '-Werror',
             '-c', str(companion), '-o', str(host_obj)])
    checked([HOST, str(obj), str(host_obj), '-o', str(program)])
    checked([str(program)])


def compile_source(directory, source):
    path = directory / 'input.c'
    path.write_text(source)
    return subprocess.run([str(KCC), str(path)], capture_output=True, text=True, timeout=15)


def main():
    with tempfile.TemporaryDirectory() as temporary:
        d = Path(temporary)
        # Exact former test_compile.py rejection is now a valid declaration.
        result = compile_source(d, 'int f(int,...) ;')
        assert result.returncode == 0 and not result.stderr, (result.stdout, result.stderr)
        invalid = [
            'int f(int, ...); int g(void){return f();}',
            'int f(int); int f(int,...);',
            'int f(int,...); int f(int);',
            'int f(int,...); int g(void){int (*p)(int)=f; return 0;}',
            'int f(void,...);', 'int f(int,...,int);', 'int f(...,...);',
            'int f(int ...);', 'int f(int, ...,);',
            'struct S { int x; }; int f(int,...); int g(void){ struct S s; return f(1,s); }',
            'int f(int,...); void v(void); int g(void){return f(0,v());}',
            '#include <stdarg.h>\nenum E : unsigned short { A=7 }; int f(int n,...){va_list a;va_start(a);return va_arg(a,enum E);}',
            '#include <stdarg.h>\nenum E : bool { A=1 }; int f(int n,...){va_list a;va_start(a);return va_arg(a,enum E);}',
        ]
        for source in invalid:
            result = compile_source(d, source)
            assert result.returncode != 0 and result.stderr and not result.stdout, (source, result.stdout, result.stderr)

        # New C23 ellipsis-only syntax, including a no-argument call and a definition.
        source = 'int f(...){return 7;} int main(void){return f()!=7 || f(3,4)!=7;}'
        link_and_run(d, source, '')

        # nullptr_t retains its type under default argument promotions.
        source = r'''
#include <stdarg.h>
#include <stddef.h>
int take(int marker, ...) {
  va_list a, copy; va_start(a); va_copy(copy,a);
  nullptr_t p=va_arg(a, nullptr_t), q=va_arg(copy, nullptr_t);
  int n=va_arg(a,int); va_end(copy); va_end(a);
  return marker==3 && p==nullptr && q==nullptr && n==42;
}
int main(void) { return !take(3,nullptr,42); }
'''
        link_and_run(d, source, '')

        # Enums compatible with their promoted types retain their va_arg type.
        source = r'''
#include <stdarg.h>
enum Small { A=7 }; enum Large : long { B=4294967296L };
int take(int n, ...) {
  va_list a; va_start(a);
  enum Small x=va_arg(a,enum Small); enum Large y=va_arg(a,enum Large);
  va_end(a); return n==2 && x==A && y==B;
}
int main(void) { return !take(2,A,B); }
'''
        link_and_run(d, source, '')
        # C23 permits fetching nullptr_t as a same-representation pointer.
        source = r'''
#include <stdarg.h>
int take(int n, ...) { va_list a; va_start(a); void *p=va_arg(a,void *);
  va_end(a); return n==1 && p==0; }
int main(void) { return !take(1,nullptr); }
'''
        link_and_run(d, source, '')

        # KCC calls a real host va_arg implementation, both directly and via a pointer.
        kcc = '''
int host(int,...);
int run(void) {
  int x=42; signed char a=-7; unsigned short b=65535;
  int (*p)(int,...)=host;
  return host(8,a,b,3,4,5,6,1234567890123L,&x)!=1 ||
         p(8,a,b,3,4,5,6,1234567890123L,&x)!=1 || host(0)!=1;
}
'''
        host = '''
#include <stdarg.h>
int host(int n,...) {
  va_list ap; va_start(ap,n);
  if (!n) {va_end(ap); return 1;}
  int a=va_arg(ap,int), b=va_arg(ap,int), c=va_arg(ap,int), d=va_arg(ap,int);
  int e=va_arg(ap,int), f=va_arg(ap,int); long g=va_arg(ap,long); int *p=va_arg(ap,int*);
  va_end(ap); return n==8 && a==-7 && b==65535 && c==3 && d==4 && e==5 && f==6 && g==1234567890123L && *p==42;
}
int run(void); int main(void){return run();}
'''
        link_and_run(d, kcc, host)
        # Host calls a KCC variadic definition with fixed arguments in registers and on stack.
        kcc = '''int f(int a,int b,int c,int d,int e,int f,int g,...) {
  return a+b+c+d+e+f+g;
}'''
        host = '''int f(int,int,int,int,int,int,int,...);
int main(void){return f(1,2,3,4,5,6,7,8,9)!=28;}'''
        link_and_run(d, kcc, host)
        # Host calls a KCC function that consumes, copies and ends its argument list.
        kcc = r'''
#include <stdarg.h>
int from_host(int n, ...) {
  va_list a, copy;
  va_start(a, n);
  va_copy(copy, a);
  int first=va_arg(a,int);
  int also=va_arg(copy,int);
  double d=va_arg(a,double);
  long v=va_arg(a,long);
  int *p=va_arg(a,int *);
  va_end(copy); va_end(a);
  return first==7 && also==7 && d==2.5 && v==1234567890123L && *p==9;
}
'''
        host = r'''
int from_host(int,...);
int main(void){ int x=9; return !from_host(4,7,2.5,1234567890123L,&x); }
'''
        link_and_run(d, kcc, host)
        # KCC passes a promoted float to a native variadic callee.
        kcc = 'int host_float(int,...); int run(void){float x=2.5f; return !host_float(1,x);}'
        host = '#include <stdarg.h>\nint host_float(int n,...){va_list a;va_start(a,n);double x=va_arg(a,double);va_end(a);return x==2.5;} int run(void);int main(void){return run();}'
        link_and_run(d, kcc, host)
        for text in [
            '#include <stdarg.h>\nint f(void){va_list a; va_start(a); return 0;}',
            '#include <stdarg.h>\nint f(int n,...){va_list a; va_start(a,n); return va_arg(a,short);}',
            '#include <stdarg.h>\nint f(int n,...){int a=0; va_start(a,n); return 0;}',
        ]:
            result = compile_source(d, text)
            assert result.returncode != 0 and result.stderr and not result.stdout, (text, result.stderr)

        # Redeclaration/composite and compatible pointer types preserve ellipsis.
        kcc = '''int host(int,...); int host(int,...);
typedef int Fn(int,...); int run(void){Fn *p=host; return p(0)!=1;}'''
        host = '''int host(int n,...){return n==0;} int run(void); int main(void){return run();}'''
        link_and_run(d, kcc, host)
    print('variadic scalar ABI and diagnostic tests passed')


if __name__ == '__main__':
    if QBE:
        main()
    else:
        print('variadic ABI tests skipped (set QBE to enable)')

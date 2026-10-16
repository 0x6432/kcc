"""Additive compound assignment: one lvalue, usual conversions, stored result."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
integers = ['_Bool', 'char', 'signed char', 'unsigned char', 'short', 'unsigned short',
            'int', 'unsigned', 'long', 'unsigned long', 'long long', 'unsigned long long']
programs = []
for name in integers[1:]:
    programs.append(f'int main(void) {{ {name} x=40; '
                    'if((x+=2)!=42 || x!=42 || (x-=2)!=40 || x!=40) return 1; '
                    'if(sizeof(x+=2)!=sizeof x || x!=40) return 2; return x+2; }')
# Conversion order matters: left promotion, usual arithmetic, then back to the
# stored type. Constants are chosen to avoid signed arithmetic overflow.
for left,initial,right,value,result in [
    ('signed char','-1','unsigned long','4294967296UL','-1'),
    ('unsigned char','255','long','257L','0'),
    ('short','-32768','unsigned','65536U','-32768'),
    ('unsigned short','65535','long long','2LL','1'),
    ('int','-1','unsigned','2U','1'),
    ('unsigned','0','long','-1L','4294967295U'),
    ('long','-1L','unsigned','4294967295U','4294967294L'),
    ('unsigned long','0UL','int','-1','18446744073709551615UL'),
    ('long long','-2LL','unsigned long','3UL','1LL'),
    ('unsigned long long','0ULL','int','-1','18446744073709551615ULL'),
]:
    programs.append(f'int main(void) {{ {left} x={initial}; {right} y={value}; '
                    f'if((x+=y)!={result} || x!={result}) return 1; return 42; }}')
for name,maximum in [('unsigned char','255U'),('unsigned short','65535U'),('unsigned','4294967295U'),
                     ('unsigned long','18446744073709551615UL'),('unsigned long long','18446744073709551615ULL')]:
    programs.append(f'int main(void) {{ {name} x=0; if((x-=1)!={maximum} || x!={maximum}) return 1; '
                    'if((x+=1)!=0 || x!=0) return 2; return 42; }')
for name in integers:
    programs.append(f'int main(void) {{ {name} a[3]; {name} *p=a; '
                    'if((p+=2)!=a+2 || p!=a+2 || (p-=1)!=a+1 || p!=a+1) return 1; '
                    'if((p+=2)!=a+3 || (p-=3)!=a || p!=a) return 2; '
                    'if(sizeof(p+=1)!=8 || p!=a) return 3; return 42; }')
for name in integers:
    # Signed types exercise negative offsets; unsigned use positive offsets.
    offset = '1' if name.startswith('unsigned') or name == '_Bool' else '-1'
    index = 'a+2' if offset == '1' else 'a'
    programs.append(f'int main(void) {{ int a[3]; int *p=a+1; {name} n={offset}; '
                    f'if((p+=n)!={index} || (p-=n)!=a+1 || p!=a+1) return 1; return 42; }}')
programs += [
    'int main(void) { _Bool b=0; if((b+=2)!=1 || b!=1) return 1; '
    'if((b+=1)!=1 || b!=1 || (b-=1)!=0 || b!=0) return 2; '
    'if((b-=2)!=1 || b!=1 || (b+=4294967295U)!=0 || b!=0) return 3; '
    'if((b+=4294967296UL)!=1 || b!=1) return 4; return 42; }',
    'int main(void) { int x=1,y=2; if((x+=y+=3)!=6 || x!=6 || y!=5) return 1; '
    'int z=0; if((z=x-=y-=1)!=2 || x!=2 || y!=4 || z!=2) return 2; '
    'if((x+=1?2:3)!=4 || x!=4) return 3; return 42; }',
    'int main(void) { int a[2][3]; int (*p)[3]=a; if((p+=1)!=a+1 || (p-=1)!=a) return 1; '
    'int *v[3]; int **q=v; if((q+=2)!=v+2 || (q-=2)!=v) return 2; '
    'const int *r=a[0]; if((r+=3)!=a[0]+3 || (r-=3)!=a[0]) return 3; return 42; }',
    'int *locate(int *p,int *n) { *n=*n+1; return p; } '
    'int amount(int *n) { *n=*n+1; return 2; } '
    'int main(void) { int x=40,a=0,b=0; '
    'if((*locate(&x,&a)+=amount(&b))!=42 || x!=42 || a!=1 || b!=1) return 1; '
    'if((*locate(&x,&a)-=amount(&b))!=40 || x!=40 || a!=2 || b!=2) return 2; '
    'if(sizeof(*locate(&x,&a)+=amount(&b))!=4 || a!=2 || b!=2 || x!=40) return 3; return 42; }',
    'int **locate(int **p,int *n) { *n=*n+1; return p; } '
    'int amount(int *n) { *n=*n+1; return 2; } '
    'int main(void) { int a[3]; int *p=a; int l=0,r=0; '
    'if((*locate(&p,&l)+=amount(&r))!=a+2 || p!=a+2 || l!=1 || r!=1) return 1; '
    'if((*locate(&p,&l)-=amount(&r))!=a || p!=a || l!=2 || r!=2) return 2; return 42; }',
    'int main(void) { int a[2]; a[0]=40; a[1]=3; int i=0; '
    'if((a[i++]+=2)!=42 || a[0]!=42 || i!=1) return 1; '
    'int *p=a; if((*p++-=2)!=40 || a[0]!=40 || p!=a+1) return 2; return 42; }',
    'int main(void) { int x=0; if(0 && (x+=1)) return 1; '
    'if(!(1 || (x-=1)) || x!=0) return 2; '
    'if((1?x+=40:(x-=2))!=40 || x!=40) return 3; '
    'if((0?(x-=2):(x+=2))!=42 || x!=42) return 4; '
    'if((x-=2,x+=2)!=42 || x!=42) return 5; return 42; }',
    '#define ADD +=\n#define JOIN(a,b) a##b\nint main(void) { int x=40; '
    'x ADD 4; x JOIN(-,=) 2; return x; }',
    'int main(void) { int sum=0; for(int i=0;i<6;i+=1) sum+=7; '
    '_Static_assert(sizeof(sum+=1)==4,"size"); if(sum!=42) return 1; return sum; }',
]
constraints = [
    ('int f(void) { return 1+=2; }','modifiable'),
    ('int f(void) { int x=0; return (x=1)+=2; }','modifiable'),
    ('int f(void) { int x=0; return (x+=1)+=2; }','modifiable'),
    ('int f(void) { int x=0; (x+=1)=2; return 0; }','modifiable'),
    ('int f(void) { const int x=0; return x-=1; }','modifiable'),
    ('int f(void) { int *const p=0; p+=1; return 0; }','modifiable'),
    ('int f(void) { int a[2]; a+=1; return 0; }','modifiable'),
    ('int id(void); int f(void) { id+=1; return 0; }','modifiable'),
    ('void v(void); int f(void) { v()+=1; return 0; }','modifiable'),
    ('int f(void) { int x=0; return ((int)x)-=1; }','modifiable'),
    ('int f(void) { void *p=0; p+=1; return 0; }','complete object'),
    ('int f(void) { int (*p)(void)=0; p-=1; return 0; }','complete object'),
    ('int f(void) { int (*p)[]=0; p+=1; return 0; }','complete object'),
    ('int f(void) { int x=0; int *p=0; x+=p; return 0; }','integer right'),
    ('int f(void) { int *p=0; p-=p; return 0; }','integer right'),
    ('void v(void); int f(void) { int x=0; x+=v(); return 0; }','integer right'),
    ('int f(void) { const int x=0; return sizeof(x+=1); }','modifiable'),
    ('int f(void) { int x=0; _Static_assert((x+=1),"not ICE"); return 0; }','integer constant expression'),
    ('int f(void) { int x=0; return &(x+=1)!=0; }','lvalue'),
]
with tempfile.TemporaryDirectory(prefix='kcc additive assignment ') as directory:
    directory = Path(directory)
    source,native,il,assembly,obj,executable = [directory/n for n in ('k.c','h.c','p.ssa','p.s','h.o','p')]

    def compile_source(text,success=True,message=''):
        source.write_text(text+'\n')
        result = subprocess.run([str(compiler),str(source)],capture_output=True,text=True,timeout=10)
        if success:
            assert result.returncode == 0 and not result.stderr,(text[:1200],result.stderr)
            if qbe:
                il.write_text(result.stdout)
                subprocess.run([qbe,'-t','amd64_sysv','-o',str(assembly),str(il)],check=True,timeout=10)
        else:
            assert result.returncode == 1 and not result.stdout and message in result.stderr,(text[:1200],result.stderr)

    def run(objects):
        result = subprocess.run([host,*map(str,objects),'-o',str(executable)],capture_output=True,text=True,timeout=10)
        assert result.returncode == 0,result.stderr
        assert subprocess.run([str(executable)],timeout=5).returncode == 42

    for text in programs:
        compile_source(text)
        if qbe:
            run([assembly])
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors',str(native),'-o',str(executable)],
                                capture_output=True,text=True,timeout=10)
        assert result.returncode == 0,(text,result.stderr)
        assert subprocess.run([str(executable)],timeout=5).returncode == 42
    for text,message in constraints:
        compile_source(text,False,message)
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)],
                                capture_output=True,text=True,timeout=10)
        assert result.returncode != 0,text
    # Valid VLA syntax is our runtime-bound subset limit, not a C constraint.
    compile_source('int f(void) { int x=1; int a[x+=1]; return 0; }',False,'integer constant expression')
    # Legacy native hosts do not know nullptr: not counted as native evidence.
    compile_source('int f(void) { nullptr+=1; return 0; }',False,'modifiable')
    compile_source('int f(void) { int x=0; x+=nullptr; return 0; }',False,'integer right')
    compile_source('int f(void) { int *p=0; p-=nullptr; return 0; }',False,'integer right')
    # Constraint-valid, execution undefined: compile only.
    compile_source('int *f(void) { int *p=0; return p+=1; }')

    for name in integers:
        initial,delta,expected = ('0','2','1') if name == '_Bool' else ('40','2','42')
        prototype = f'{name} update({name} *,int,int,int,int,int,int,long); '
        helper = (f'{name} update({name} *p,int a,int b,int c,int d,int e,int f,long g) {{ '
                  'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6) return 0; return *p+=g; }')
        driver = (f'int main(void) {{ {name} x={initial}; '
                  f'if(update(&x,1,2,3,4,5,6,{delta}L)!={expected} || x!={expected}) return 1; return 42; }}')
        pointer_prototype = f'{name} *advance({name} **,long); '
        pointer_helper = f'{name} *advance({name} **p,long n) {{ return *p+=n; }}'
        pointer_driver = (f'int main(void) {{ {name} a[3]; {name} *p=a+2; '
                          'if(advance(&p,-2L)!=a || p!=a) return 1; return 42; }')
        for kcc_text,host_text in [(helper,prototype+driver),(prototype+driver,helper),
                                   (pointer_helper,pointer_prototype+pointer_driver),(pointer_prototype+pointer_driver,pointer_helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],
                                        capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                run([assembly,obj])
    for count,valid in [(63,True),(64,False)]:
        compile_source('int f(void) { int x=0; return ('+'* &'*count+'x)+=1; }',valid,'depth')

print(f'Additive assignments passed: {len(programs)} strict native original programs, {len(constraints)} native constraint rejections, '
      f'nullptr constraints, VLA subset limit, compile-only null update, exact depth, once-only operands; {host}'
      + ('; QBE/runtime and 48 mixed-stack narrow/pointer-return ABI arrangements passed' if qbe else ''))

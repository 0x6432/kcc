"""Integer compound operators retain one lvalue and explicit calculation types."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
integers = ['_Bool','char','signed char','unsigned char','short','unsigned short',
            'int','unsigned','long','unsigned long','long long','unsigned long long']
operations = [('*=','7','6','42'),('/=','84','2','42'),('%=','92','50','42'),
              ('&=','106','63','42'),('^=','21','63','42'),('|=','40','2','42'),
              ('<<=','21','1','42'),('>>=','84','1','42')]
boolean_operations = [('1','0','0'),('1','2','0'),('1','2','1'),('1','2','0'),
                      ('1','3','1'),('0','2','1'),('1','1','1'),('1','1','0')]
programs = []
for name in integers:
    for index,(op,initial,right,expected) in enumerate(operations):
        if name == '_Bool':
            initial,right,expected = boolean_operations[index]
        programs.append(f'int main(void) {{ {name} x={initial}; '
                        f'if((x{op}{right})!={expected} || x!={expected}) return 1; '
                        f'if(sizeof(x{op}{right})!=sizeof x || x!={expected}) return 2; return 42; }}')
# Mixed widths/signs, independent shift promotion and wide QBE word-count use.
for name,initial,op,right,expected in [
    ('unsigned','4294967295U','/=','2','2147483647U'),
    ('unsigned long','18446744073709551615UL','/=','2L','9223372036854775807UL'),
    ('unsigned long long','18446744073709551615ULL','%=','256','255ULL'),
    ('int','-85','/=','2','-42'),('long','-85L','%=','2L','-1L'),
    ('long long','-85LL','/=','2LL','-42LL'),
    ('int','-84','>>=','1U','-42'),('signed char','-84','>>=','1UL','-42'),
    ('long','-84L','>>=','1U','-42L'),
    ('unsigned long','9223372036854775808UL','>>=','63ULL','1UL'),
    ('unsigned long long','1ULL','<<=','40UL','1099511627776ULL'),
    ('unsigned char','255','>>=','1ULL','127'),
    ('unsigned char','255','*=','257UL','255'),
    ('signed char','21','*=','258L','42'),
    ('unsigned short','65535','%=','256UL','255'),
    ('int','-1','&=','4294967338UL','42'),
    ('unsigned long','4294967296UL','|=','42U','4294967338UL'),
    ('_Bool','1','*=','4294967296UL','1'),
    ('_Bool','0','|=','4294967296UL','1'),
    ('_Bool','1','^=','4294967296UL','1'),
]:
    programs.append(f'int main(void) {{ {name} x={initial}; '
                    f'if((x{op}{right})!={expected} || x!={expected}) return 1; return 42; }}')
for op,initial,right,expected in operations:
    programs.append('int *locate(int *p,int *n) { *n+=1; return p; } '
                    f'int amount(int *n) {{ *n+=1; return {right}; }} '
                    f'int main(void) {{ int x={initial},l=0,r=0; '
                    f'if((*locate(&x,&l){op}amount(&r))!={expected} || x!={expected} || l!=1 || r!=1) return 1; '
                    f'if(sizeof(*locate(&x,&l){op}amount(&r))!=4 || l!=1 || r!=1) return 2; '
                    f'if(0 && (x{op}{right})) return 3; if(!(1 || (x{op}{right})) || x!={expected}) return 4; return 42; }}')
programs += [
    'int main(void) { int x=84,y=4; if((x/=y*=2)!=10 || x!=10 || y!=8) return 1; '
    'x=1; y=2; if((x<<=y+=1)!=8 || x!=8 || y!=3) return 2; '
    'x=40; if((1?x|=2:(x&=0))!=42 || x!=42) return 3; '
    'if((x^=2,x|=2)!=42 || x!=42) return 4; return 42; }',
    '#define JOIN(a,b) a##b\n#define TIMES *=\nint main(void) { int x=7; '
    'x TIMES 6; x JOIN(<<,=) 1; x JOIN(>>,=) 1; return x; }',
    'int main(void) { int x=21; _Static_assert(sizeof(x<<=1)==4,"size"); '
    'if(x!=21) return 1; return x*=2; }',
]
constraints = []
for op,_,_,_ in operations:
    constraints += [
        (f'int f(void) {{ int *p=0; p{op}1; return 0; }}','pointer left'),
        (f'int f(void) {{ int x=0; int *p=0; x{op}p; return 0; }}','integer right'),
        (f'int f(void) {{ const int x=1; x{op}1; return 0; }}','modifiable'),
        (f'int f(void) {{ int x=1; (x=1){op}1; return 0; }}','modifiable'),
        (f'int f(void) {{ int x=1; _Static_assert((x{op}1),"not ICE"); return 0; }}','integer constant expression'),
    ]
constraints += [
    ('void v(void); int f(void) { int x=0; x*=v(); return 0; }','integer right'),
    ('int f(void) { int x=0; return sizeof((const int)x>>=1); }','modifiable'),
    ('int f(void) { int x=0; return &(x*=1)!=0; }','lvalue'),
]
with tempfile.TemporaryDirectory(prefix='kcc integer compound ') as directory:
    directory = Path(directory)
    source,native,il,assembly,obj,executable = [directory/n for n in ('k.c','h.c','p.ssa','p.s','h.o','p')]

    def compile_source(text,success=True,message=''):
        source.write_text(text+'\n')
        result = subprocess.run([str(compiler),str(source)],capture_output=True,text=True,timeout=10)
        if success:
            assert result.returncode == 0 and not result.stderr,(text[:1400],result.stderr)
            if qbe:
                il.write_text(result.stdout)
                subprocess.run([qbe,'-t','amd64_sysv','-o',str(assembly),str(il)],check=True,timeout=10)
        else:
            assert result.returncode == 1 and not result.stdout and message in result.stderr,(text[:1400],result.stderr)

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
    compile_source('int f(void) { int x=1; int a[x*=2]; return 0; }',False,'integer constant expression')
    compile_source('int f(void) { int x=1; x*=nullptr; return 0; }',False,'integer right')
    compile_source('int f(void) { nullptr>>=1; return 0; }',False,'modifiable')
    # Runtime-invalid operations are only compiled. Never execute them.
    for operation in ['/=0','%=0','<<=-1','>>=32','*=2147483647']:
        compile_source(f'int f(void) {{ int x=2; return x{operation}; }}')

    for name in integers:
        for op,initial,delta,expected in [('*=','7','6L','42'),('>>=','84','1L','42')]:
            if name == '_Bool':
                initial,delta,expected = ('1','2L','1') if op == '*=' else ('1','1L','0')
            prototype = f'{name} update({name} *,int,int,int,int,int,int,long); '
            helper = (f'{name} update({name} *p,int a,int b,int c,int d,int e,int f,long g) {{ '
                      f'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6) return 0; return *p{op}g; }}')
            driver = (f'int main(void) {{ {name} x={initial}; '
                      f'if(update(&x,1,2,3,4,5,6,{delta})!={expected} || x!={expected}) return 1; return 42; }}')
            for kcc_text,host_text in [(helper,prototype+driver),(prototype+driver,helper)]:
                compile_source(kcc_text)
                if qbe:
                    native.write_text(host_text+'\n')
                    result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],
                                            capture_output=True,text=True,timeout=10)
                    assert result.returncode == 0,(host_text,result.stderr)
                    run([assembly,obj])
    for count,valid in [(63,True),(64,False)]:
        compile_source('int f(void) { int x=1; return ('+'* &'*count+'x)*=2; }',valid,'depth')

print(f'Integer compound assignments passed: {len(programs)} strict native original programs, {len(constraints)} native constraint rejections, '
      f'nullptr constraints, VLA subset limit, compile-only invalid arithmetic, exact depth, once-only operands; {host}'
      + ('; QBE/runtime and 48 mixed-stack narrow-result/wide-count ABI arrangements passed' if qbe else ''))

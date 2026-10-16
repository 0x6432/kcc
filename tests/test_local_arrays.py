"""Bounded one-dimensional local arrays, decay and pointer-to-array addresses.

All executed elements are written before read. Resource-limit fixtures are
compiled only, never executed; arbitrary fuzz-generated C is never run.
"""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root / 'build' / 'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
integers = ['_Bool', 'char', 'signed char', 'unsigned char', 'short',
            'unsigned short', 'int', 'unsigned', 'long', 'unsigned long',
            'long long', 'unsigned long long']
legacy_separator_gaps = 0
programs = []
for name in integers:
    programs.append(f'''int main(void) {{ {name} a[5]; int i=0;
 while(i<5) {{ a[i]=i+1; i=i+1; }}
 {name} *p=a; if(p!=&a[0] || a+5-p!=5L || (a+5)[-1]!=({name})5) return 1;
 if((&a+1)-&a!=1L || &a-(&a+1)!=-1L || &(*(&a))[0]!=p) return 2;
 if((&a)[0][3]!=({name})4 || (*(&a))[2]!=({name})3) return 3;
 if((a[0]=7)!=({name})7 || p[0]!=({name})7) return 4;
 return 42; }}''')
programs += [
    '#define N 0b1\'01U\nint main(void) { int a[N]; int i=0; '
    'while(i<N) { a[i]=i+1; i=i+1; } return a[4]+37; }',
    'int *identity(int *p) { return p; } int main(void) { int a[3]; '
    'a[0]=10; a[1]=11; a[2]=21; int *p=identity(a); return p[0]+p[1]+p[2]; }',
    'int main(void) { int a[3]; a[0]=2; a[1]=3; a[2]=4; '
    'int *p[3]; p[0]=&a[0]; p[1]=&a[1]; p[2]=&a[2]; '
    'if(p+3-p!=3L || (&p+1)-&p!=1L || *p[1]!=3) return 1; '
    'int **q=p; if(q[2]!=&a[2] || (&p)[0][0]!=&a[0]) return 2; return 42; }',
    'int main(void) { int a[2]; a[0]=40; a[1]=2; '
    '{ int a[1]; a[0]=99; if(a[0]!=99) return 1; } return a[0]+a[1]; }',
    'int main(void) { int sum=0; for(int a[1]; sum<42;) { a[0]=1; sum=sum+a[0]; } return sum; }',
    'int main(void) { int a[1]; int b[1]; a[0]=40; b[0]=2; '
    'if(&a==&b || a==b || !a || !&a) return 1; return a[0]+b[0]; }',
]

with tempfile.TemporaryDirectory(prefix='kcc local arrays ') as directory:
    directory = Path(directory)
    source, other, il, assembly, obj, executable = [directory / name for name in
                                                   ('k.c', 'h.c', 'p.ssa', 'p.s', 'h.o', 'p')]

    def compile_source(text):
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True,
                                text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)],
                           check=True, timeout=10)
        return result.stdout

    def link_and_run(host_text=None):
        objects = [str(assembly)]
        if host_text is not None:
            other.write_text(host_text)
            subprocess.run([host, '-std=c2x', '-fsigned-char', '-c', str(other),
                            '-o', str(obj)], capture_output=True, check=True, timeout=10)
            objects.append(str(obj))
        subprocess.run([host, *objects, '-o', str(executable)], check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, host_text

    for text in programs:
        compile_source(text)
        if qbe:
            link_and_run()
        result = subprocess.run([host, '-std=c2x', '-fsigned-char', str(source), '-o', str(executable)],
                                capture_output=True, text=True, timeout=10)
        if result.returncode:
            # GCC 11 predates C23 digit separators. The original spelling has
            # already passed kcc/QBE; use an explicit equal-valued host oracle,
            # following test_integer_spellings.py, not a compiler workaround.
            version = subprocess.run([host, '-dumpfullversion'], capture_output=True,
                                     text=True, check=True, timeout=5).stdout.strip()
            assert version.startswith('11.') and text.startswith("#define N 0b1'01U"), (text, result.stderr)
            legacy_separator_gaps += 1
            other.write_text(text.replace("0b1'01U", '5U', 1))
            subprocess.run([host, '-std=c2x', '-fsigned-char', str(other), '-o', str(executable)],
                           capture_output=True, check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, text

    # Both arrangements include a kcc-owned local array borrowed by a host
    # function, plus host-owned arrays passed into kcc code. No pointer escapes
    # the lifetime of its automatic storage.
    for name in integers:
        helper = f'''{name} update({name} *p) {{ p[1]=7; return p[0]+p[1]+p[2]; }}\n'''
        relay = f'''{name} update({name} *);
int local(void) {{ {name} a[3]; a[0]=1; a[1]=2; a[2]=3;
 if(update(a)!=({name})((({name})1)+(({name})7)+(({name})3))) return 1;
 if(a[1]!=({name})7) return 2; return 42; }}\n'''
        host_driver = f'''int local(void); {name} update({name} *);
int main(void) {{ {name} a[3]; a[0]=1; a[1]=2; a[2]=3;
 if(update(a)!=({name})((({name})1)+(({name})7)+(({name})3))) return 3;
 if(a[1]!=({name})7) return 4; return local(); }}\n'''
        # In the first direction kcc helpers mutate both array owners; in the
        # second direction host helpers receive decayed kcc-owned storage.
        for text, host_text in [(helper + relay, host_driver), (relay, helper + host_driver)]:
            compile_source(text)
            if qbe:
                link_and_run(host_text)
        other.write_text(helper + relay + host_driver)
        subprocess.run([host, '-std=c2x', '-fsigned-char', str(other), '-o', str(executable)],
                       capture_output=True, check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, name

    # Sizes, true target alignment and whole-array stride are visible in IL.
    for name, size, alignment in [('char', 1, 4), ('short', 2, 4), ('int', 4, 4),
                                  ('long', 8, 8), ('int *', 8, 8)]:
        result = compile_source(f'int f(void) {{ {name} a[3]; return (&a+1)-&a; }}')
        assert f'alloc{alignment} {size*3}\n' in result, result
        assert f', {size*3}\n' in result, result
        # Forming whole-array addresses must not load the array's bytes.
        assert 'load' not in result, result

    # Declared object bytes include parameter spill objects and all scopes;
    # the sum resets between functions. Only compile these large fixtures.
    boundary = [
        ('int f(void) { char a[1048576]; return 0; }', True),
        ('int f(void) { char a[1048577]; return 0; }', False),
        ('int f(void) { long a[131072]; return 0; }', True),
        ('int f(void) { long a[131073]; return 0; }', False),
        ('int f(int p) { char a[1048572]; return 0; }', True),
        ('int f(int p) { char a[1048573]; return 0; }', False),
        ('int f(void) { char a[524288]; { char b[524288]; } return 0; }', True),
        ('int f(void) { char a[524288]; { char b[524289]; } return 0; }', False),
        ('int f(void) { char a[1048576]; return 0; } int g(void) { char b[1048576]; return 0; }', True),
    ]
    for text, valid in boundary:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'storage limit' in result.stderr, result.stderr

    for count, valid in [(126, True), (127, False)]:
        text = 'int f(void) { int a[1]; return ' + '! ' * count + 'a; }'
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'depth' in result.stderr, result.stderr

    rejected = [
        ('int main(void) { int a[0]; return 0; }', 'array bound'),
        ('int main(void) { int a[18446744073709551615ULL]; return 0; }', 'storage limit'),
        ('int main(void) { int a[-1]; return 0; }', 'integer literal'),
        ('int main(void) { int n=3; int a[n]; return 0; }', 'integer literal'),
        ('int main(void) { int a[1+2]; return 0; }', "expected ']'"),
        ('int main(void) { int a[]; return 0; }', 'integer literal'),
        ('int main(void) { int a[2][3]; return 0; }', "expected ';'"),
        ('int main(void) { int a[2]=1; return 0; }', 'array initializers'),
        ('int main(void) { int a[2]; int b[2]; a=b; return 0; }', 'modifiable lvalue'),
        ('int main(void) { int a[2]; *(&a)=a; return 0; }', 'modifiable lvalue'),
        ('int main(void) { int a[2]; int *p=&a; return 0; }', 'pointer conversion'),
        ('int main(void) { int a[2]; int b[3]; return &a==&b; }', 'compatible pointer'),
        ('int main(void) { int a[2]; return +a; }', 'integer operand'),
        ('int f(int a[2]) { return 0; }', ''),
    ]
    for text, message in rejected:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)
print(f'Local arrays passed ({len(programs)} full-value programs, both-direction borrowed-array ABI for all primitive types, '
      f'pointer elements, decay/address stride, alignment, storage/depth constraints, {legacy_separator_gaps} legacy separator gaps; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

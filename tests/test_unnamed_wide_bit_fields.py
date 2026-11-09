"""Unnamed 33–63-bit long fields: layout and by-value interoperability."""
from pathlib import Path
import subprocess
import tempfile
from test_bit_fields import ROOT, HOST, KCC, legacy_clang_options, object_file, run


def matrix(d, prefix, widths, options):
    declarations, definitions, checks = [], [], []
    bases = ('signed long', 'unsigned long', 'signed long long', 'unsigned long long')
    for width in widths:
        for i, base in enumerate(bases):
            name=f'S{prefix}_{width}_{i}'
            declarations += [f'struct {name} {{ unsigned p:{prefix}; {base} :{width}; float f; char end; }};',
                             f'struct {name} f{name}(struct {name} x); int size{name}(void); int offset{name}(void);']
            definitions += [f'struct {name} f{name}(struct {name} x){{x.f+=2; x.end++; return x;}}',
                            f'int size{name}(void){{return sizeof(struct {name});}}',
                            f'int offset{name}(void){{struct {name} s; return (char*)&s.end-(char*)&s;}}']
            checks += [f'struct {name} x{name}={{{(1<<prefix)-1},1.5f,7}}, y{name}=f{name}(x{name});',
                       f'if(sizeof(x{name})!=size{name}() || (char*)&x{name}.end-(char*)&x{name}!=offset{name}() || '
                       f'y{name}.p!={(1<<prefix)-1} || y{name}.f!=3.5f || y{name}.end!=8 || x{name}.end!=7) return 1;']
    decl='\n'.join(declarations)+'\n'
    (d/'owner.c').write_text(decl+'\n'.join(definitions)+'\n')
    (d/'companion.c').write_text(decl+'int main(void){\n'+'\n'.join(checks)+'\nreturn 0;}\n')
    for a,b in (('host','kcc'),('kcc','host')):
        object_file(d/'owner.c',d/'owner.o',a,options); object_file(d/'companion.c',d/'companion.o',b,options)
        run([HOST,d/'owner.o',d/'companion.o','-o',d/'test'])
        try: run([d/'test'])
        except AssertionError as e: raise AssertionError((prefix, tuple(widths), a, b, e)) from e


def main():
    (ROOT/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='unnamed-wide-',dir=ROOT/'build') as tmp:
        d=Path(tmp); options=legacy_clang_options()
        # Exact formerly rejected source, now a layout-only acceptance.
        (d/'original.c').write_bytes(b'struct S { long :33; int x; };')
        object_file(d/'original.c',d/'original.o','kcc',options)
        decl = ("union U { unsigned long :63; double d; }; "
                "struct N { union U u; unsigned long long :35; long tail; };")
        owner = (decl + "\nunion U fu(union U x){x.d+=2;return x;} "
                 "struct N fn(struct N x){x.u.d+=2; x.tail++;return x;}\n")
        caller = (decl + "\nunion U fu(union U); struct N fn(struct N); int main(void){"
                  "union U u={.d=1.5}, v=fu(u); struct N n={.u={.d=1.5},.tail=7}, m=fn(n);"
                  "return v.d!=3.5 || u.d!=1.5 || m.u.d!=3.5 || m.tail!=8 || n.tail!=7; }\n")
        (d/'owner.c').write_text(owner); (d/'companion.c').write_text(caller)
        for a,b in (('host','host'),('host','kcc'),('kcc','host'),('kcc','kcc')):
            object_file(d/'owner.c',d/'owner.o',a,options); object_file(d/'companion.c',d/'companion.o',b,options)
            run([HOST,d/'owner.o',d/'companion.o','-o',d/'test']); run([d/'test'])
        for prefix in range(1,8):
            for widths in (range(33,49), range(49,64)):
                matrix(d,prefix,widths,options)
        # Legacy Clang cannot lower a leading NO_CLASS eightbyte through QBE.
        # The same shape remains usable with the default GCC classification.
        for width in (33, 63):
            source = f'struct S {{ unsigned long :{width}; float f; }}; struct S f(struct S x){{return x;}}'
            (d/'hole.c').write_text(source)
            default = subprocess.run([str(KCC),str(d/'hole.c')],capture_output=True,text=True,timeout=15)
            legacy = subprocess.run([str(KCC),'--legacy-clang-abi',str(d/'hole.c')],capture_output=True,text=True,timeout=15)
            assert default.returncode == 0 and default.stdout and not default.stderr, (source,default.stderr)
            assert legacy.returncode == 1 and not legacy.stdout and 'aggregate ABI unsupported (M21, legacy Clang mode)' in legacy.stderr, (source,legacy.stderr)
        # Width and base-type restrictions remain in force.
        for source in ('struct S { long x:65; };', 'struct S { volatile long x:33; };',
                       'struct S { unsigned long :65; int x; };', 'struct S { unsigned :33; int x; };'):
            (d/'reject.c').write_text(source)
            result=subprocess.run([str(KCC),*options,str(d/'reject.c')],capture_output=True,text=True,timeout=15)
            assert result.returncode==1 and not result.stdout and 'bit-field' in result.stderr, (source, result.stderr)
    print(f'unnamed long-base 33–63: 868 prefix/layout combinations in both host/KCC directions passed; ABI {"legacy Clang" if options else "default"}')


if __name__=='__main__': main()

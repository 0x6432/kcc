"""Int-compatible enum bit-fields on x86-64 SysV."""
from pathlib import Path
import subprocess
import tempfile
from test_bit_fields import ROOT, HOST, KCC, legacy_clang_options, object_file, run

DECL = r'''
enum E { NEG=-1, ZERO=0, POS=1 }; typedef enum E ET;
struct S { char c; enum E a:9; unsigned p:7; enum E b:32; char end; };
union U { enum E a:5; double d; };
struct Barrier { enum E a:3; enum E :0; char end; };
extern struct S global; extern union U un; extern struct Barrier barrier;
struct S change(struct S v); union U uchange(union U v);
'''
OWNER = DECL + r'''
struct S global={2,-17,63,-123456,9}; union U un={.a=NEG}; struct Barrier barrier={NEG,42};
struct S change(struct S v){v.a+=3; v.b++; return v;}
union U uchange(union U v){v.a=0;return v;}
'''
COMPANION = DECL + r'''
int main(void){
 struct S s=change(global); union U u=uchange(un);
 if(global.a!=-17 || global.b!=-123456 || global.p!=63 || global.end!=9) return 1;
 if(s.a!=-14 || s.b!=-123455 || s.c!=2 || s.p!=63 || s.end!=9 || u.a!=0) return 2;
 if((global.a=-7)!=-7 || global.a++!=-7 || global.a!=-6 || ++global.a!=-5) return 3;
 if(_Generic(+global.a,int:1,default:0)!=1 || _Generic(+global.b,int:1,default:0)!=1) return 4;
 if((char*)&barrier.end-(char*)&barrier!=4 || barrier.a!=-1 || barrier.end!=42) return 5;
 return 0;
}
'''

def matrix(d,prefix,mode):
    decl, owner, checks = [], [], []
    if mode=='ordinary':
        prefix_text='enum E { NEG=-1, ZERO=0, POS=1 };\n'; field='enum E'; initial='-1'; updated='0'
    elif mode=='fixed_signed':
        prefix_text='enum E : int { NEG=-1, ZERO=0, POS=1 };\n'; field='enum E'; initial='-1'; updated='0'
    else:
        prefix_text='enum E : unsigned int { ZERO=0, POS=1 };\n'; field='enum E'; initial='0'; updated='1'
    for width in range(1,33):
        name=f'v{prefix}_{width}'
        decl += [f'struct {name} {{ unsigned p:{prefix}; {field} x:{width}; unsigned y:3; char end; }};',
                 f'extern struct {name} g{name}; struct {name} f{name}(struct {name} x);']
        owner += [f'struct {name} g{name}={{{(1<<prefix)-1},{initial},3,77}};',
                  f'struct {name} f{name}(struct {name} x){{x.x={updated};x.y=6;return x;}}']
        checks += [f'struct {name} r{name}=f{name}(g{name});',
                   f'if(r{name}.p!={(1<<prefix)-1} || r{name}.x!={updated} || r{name}.y!=6 || r{name}.end!=77 || g{name}.x!={initial}) return 1;']
    text=prefix_text+'\n'.join(decl)+'\n'
    src_owner=text+'\n'.join(owner)+'\n'; src_companion=text+'\nint main(void){\n'+'\n'.join(checks)+'\nreturn 0;}\n'
    # GCC 11 lacks C23 fixed enums. For the fixed-enum ABI only, use a
    # separately compiled representation-compatible primitive-field surrogate;
    # this is not a native C23 syntax/semantics agreement.
    base='signed int' if mode=='fixed_signed' else 'unsigned int'
    def host_source(s):
        if mode=='ordinary': return s
        return s.replace(prefix_text,'').replace('enum E x:',base+' x:')
    for a,b in [('host','kcc'),('kcc','host')]:
        (d/'owner.c').write_text(host_source(src_owner) if a=='host' else src_owner)
        (d/'companion.c').write_text(host_source(src_companion) if b=='host' else src_companion)
        object_file(d/'owner.c',d/'owner.o',a); object_file(d/'companion.c',d/'companion.o',b)
        run([HOST,d/'owner.o',d/'companion.o','-o',d/'test']); run([d/'test'])

def unnamed_matrix(d,typ,kcc_options):
    decl, owner, checks = [], [], []
    for width in range(1,33):
        name=f'n{typ}_{width}'
        decl += [f'struct {name} {{ {typ} x; enum E :{width}; float y; }};',
                 f'struct {name} f{name}(struct {name} x);']
        owner += [f'struct {name} f{name}(struct {name} x){{x.x+=1; x.y+=2; return x;}}']
        checks += [f'struct {name} a{name}={{1.5,2.5f}}, b{name}=f{name}(a{name});',
                   f'if(b{name}.x!=2.5 || b{name}.y!=4.5f || a{name}.y!=2.5f) return 1;']
    text='enum E { NEG=-1, ZERO=0, POS=1 }; typedef enum E ET;\n'+'\n'.join(decl)+'\n'
    (d/'owner.c').write_text(text+'\n'.join(owner)+'\n')
    (d/'companion.c').write_text(text+'\nint main(void){\n'+'\n'.join(checks)+'\nreturn 0;}\n')
    for a,b in [('host','kcc'),('kcc','host')]:
        object_file(d/'owner.c',d/'owner.o',a,kcc_options); object_file(d/'companion.c',d/'companion.o',b,kcc_options)
        run([HOST,d/'owner.o',d/'companion.o','-o',d/'test']); run([d/'test'])

def main():
    (ROOT/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='enum-fields-',dir=ROOT/'build') as tmp:
        d=Path(tmp); (d/'owner.c').write_text(OWNER); (d/'companion.c').write_text(COMPANION)
        for a,b in [('host','host'),('host','kcc'),('kcc','host'),('kcc','kcc')]:
            object_file(d/'owner.c',d/'owner.o',a); object_file(d/'companion.c',d/'companion.o',b)
            run([HOST,d/'owner.o',d/'companion.o','-o',d/'test']); run([d/'test'])
        for mode in ('ordinary','fixed_signed','fixed_unsigned'):
            for prefix in range(1,8): matrix(d,prefix,mode)
        kcc_options = legacy_clang_options()
        for typ in ('float','double'): unnamed_matrix(d,typ,kcc_options)
        # The colon following an enum tag must remain a member declarator
        # when the next expanded token starts a width expression.
        direct = r'''
        #define COLON :
        #define WIDTH (1 + 2)
        enum E { NEG=-1, W=3 };
        struct S { char x; enum E COLON WIDTH, y:5; enum E : W;
                   enum E : sizeof(char); enum E : 0; char end; };
        struct S g={1, -3, 42};
        int main(void) {
            struct S s={2, -4, 43};
            return g.x!=1 || g.y!=-3 || g.end!=42 ||
                   s.x!=2 || s.y!=-4 || s.end!=43 ||
                   sizeof(struct S)!=8 || (char*)&g.end-(char*)&g!=4;
        }
        '''
        (d/'direct.c').write_text(direct+'\n')
        for compiler in ('host','kcc'):
            object_file(d/'direct.c',d/'direct.o',compiler)
            run([HOST,d/'direct.o','-o',d/'direct']); run([d/'direct'])
        # Fixed-underlying definitions still take the enum-specifier colon,
        # while a later colon after a tag is an unnamed field.
        (d/'direct_fixed.c').write_text(r'''
        enum E : unsigned int { E0=0, E1=1 };
        struct S {
            enum F : int { F0=0, F1=1 } named:3;
            enum E : (1 ? 2 : 3), x:2;
        };
        int main(void) { struct S s={F1,E1}; return s.named!=1 || s.x!=1; }
        ''')
        object_file(d/'direct_fixed.c',d/'direct_fixed.o','kcc')
        run([HOST,d/'direct_fixed.o','-o',d/'direct_fixed']); run([d/'direct_fixed'])
        (d/'fixed.c').write_text("""enum E : unsigned int { ZERO=0, MAX=4294967295U };
        struct S { enum E x:32; unsigned p:3; }; struct S g={MAX,7};
        int main(void){ struct S s={MAX,3}; if(_Generic(+s.x,unsigned int:1,default:0)!=1) return 1;
        if(s.x++!=4294967295U || s.x!=0 || g.x!=4294967295U || g.p!=7) return 2;
        if((s.x=MAX)!=4294967295U || s.p!=3) return 3; return 0; }""")
        object_file(d/'fixed.c',d/'fixed.o','kcc'); run([HOST,d/'fixed.o','-o',d/'fixed']); run([d/'fixed'])
        # Previously rejected int-compatible enum field, checked only with KCC:
        # GCC may choose a different compatible type for a nonnegative enum.
        (d/'former.c').write_text('enum E { A }; struct S { enum E x:32; }; struct S s={0}; int main(void){return s.x!=0;}')
        object_file(d/'former.c',d/'former.o','kcc'); run([HOST,d/'former.o','-o',d/'former']); run([d/'former'])
        for source in ['enum E : short { A }; struct S { enum E x:3; };',
                       'enum E : unsigned long { A }; struct S { enum E x:32; };',
                       'enum E { A }; struct S { enum E x:33; };',
                       'enum E { A }; struct S { enum E x:0; };',
                       'enum E { A }; struct S { enum E : 33; };',
                       'enum E { A }; struct S { enum E : ; };',
                       'enum E { A }; struct S { volatile enum E x:1; };']:
            (d/'reject.c').write_text(source); r=subprocess.run([str(KCC),str(d/'reject.c')],text=True,capture_output=True)
            diagnostic='aggregate ABI unsupported' if 'f(struct' in source else ('expected' if ': ;' in source else 'bit-field')
            if r.returncode==0 or r.stdout or diagnostic not in r.stderr: raise AssertionError((source,r.returncode,r.stderr,r.stdout))
    print('enum bit-fields: 288 ordinary host/KCC layouts and 448 fixed-enum/primitive-surrogate layouts '
          f"in both directions passed; unnamed ABI: {'legacy Clang' if kcc_options else 'default'}; "
          'fixed-enum native C23 comparison unavailable')

if __name__=='__main__': main()

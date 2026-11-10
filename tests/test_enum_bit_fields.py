"""Integer-compatible enum bit-fields on x86-64 SysV."""
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

def narrow_fixed_matrix(d, prefix, base, max_width, signed):
    # The host uses an equivalent primitive bit-field surrogate, not the C23
    # enum declaration: GCC 11 cannot parse fixed enum syntax.
    enum = f'enum E : {base} {{ E0=0, E1=1 }};\n'
    decl, owner, checks = [], [], []
    initial, updated = ('-1', '0') if signed else ('0', '1')
    for width in range(1, max_width + 1):
        name = f'n{prefix}_{width}'
        decl += [f'struct {name} {{ unsigned p:{prefix}; enum E a:{width}; '
                 f'unsigned char tail:3; char end; }};',
                 f'extern struct {name} g{name}; int size_{name}(void); '
                 f'struct {name} f{name}(struct {name} x);']
        owner += [f'struct {name} g{name}={{{(1<<prefix)-1},{initial},5,77}};',
                  f'int size_{name}(void){{return sizeof(struct {name});}}',
                  f'struct {name} f{name}(struct {name} x){{x.a={updated}; '
                  'x.tail=3; return x;}']
        checks += [f'struct {name} r{name}=f{name}(g{name});',
                   f'if(size_{name}()!=sizeof(struct {name}) || '
                   f'g{name}.a!={initial} || r{name}.a!={updated} || '
                   f'r{name}.p!={(1<<prefix)-1} || r{name}.tail!=3 || '
                   f'r{name}.end!=77) return {width};']
    header = enum + '\n'.join(decl) + '\n'
    source_owner = header + '\n'.join(owner) + '\n'
    source_companion = header + 'int main(void){\n' + '\n'.join(checks) + '\nreturn 0;}\n'
    def surrogate(source):
        return source.replace(enum, '').replace('enum E a:', base+' a:')
    for owner_kind, companion_kind in [('host','kcc'), ('kcc','host')]:
        (d/'owner.c').write_text(surrogate(source_owner) if owner_kind=='host' else source_owner)
        (d/'companion.c').write_text(surrogate(source_companion) if companion_kind=='host' else source_companion)
        object_file(d/'owner.c', d/'owner.o', owner_kind)
        object_file(d/'companion.c', d/'companion.o', companion_kind)
        run([HOST, d/'owner.o', d/'companion.o', '-o', d/'test'])
        try: run([d/'test'])
        except AssertionError as e: raise AssertionError(f'{base} prefix {prefix} {owner_kind}/{companion_kind}: {e}') from e

def narrow_fixed_controls(d, base, signed):
    # Width-limited updates, integer promotion, static initialization and an
    # unnamed zero-width separator exercise more than simple ABI layout.
    enum = f'enum E : {base} {{ E0=0, E1=1 }};\n'
    initial = '-1' if signed else '7'
    text = enum + f"""
    typedef enum E ET;
    struct S {{ enum E a:3; ET b:3; enum E :0; char tail; }};
    struct S global = {{{initial}, 1, 42}};
    int main(void) {{
        struct S s = {{{initial}, 1, 43}};
        if (s.a!={initial} || global.a!={initial} || s.b!=1 || s.tail!=43) return 1;
        if (s.a++!={initial} || s.a!=0 || global.a!={initial}) return 2;
        if (++s.b!=2 || (s.a=1)!=1 || s.a!=1) return 3;
        if (_Generic(+s.a, int:1, default:0)!=1) return 4;
        return 0;
    }}
    """
    for compiler in ('host', 'kcc'):
        source = text if compiler == 'kcc' else (text.replace(enum, f'typedef {base} ET;\n')
                    .replace('typedef enum E ET;', '').replace('enum E a:', base+' a:')
                    .replace('enum E :0', base+' :0'))
        (d/'controls.c').write_text(source+'\n')
        object_file(d/'controls.c', d/'controls.o', compiler)
        run([HOST, d/'controls.o', '-o', d/'controls'])
        run([d/'controls'])

def wide_fixed_matrix(d, prefix, base, signed):
    # Compare all 64 widths with primitive field surrogates. Cast reads
    # so expression differences between GCC and Clang do not affect layout checks.
    enum = f'enum E : {base} {{ E0=0, E1=1 }};\n'
    decl, owner, checks = [], [], []
    initial, updated = ('-1', '0') if signed else ('0', '1')
    for width in range(1, 65):
        name = f'w{prefix}_{width}'
        decl += [f'struct {name} {{ unsigned p:{prefix}; enum E a:{width}; unsigned tail:3; char end; }};',
                 f'extern struct {name} g{name}; int size_{name}(void); struct {name} f{name}(struct {name} x);']
        owner += [f'struct {name} g{name}={{{(1<<prefix)-1},{initial},5,77}};',
                  f'int size_{name}(void){{return sizeof(struct {name});}}',
                  f'struct {name} f{name}(struct {name} x){{x.a={updated}; x.tail=3; return x;}}']
        checks += [f'struct {name} r{name}=f{name}(g{name});',
                   f'if(size_{name}()!=sizeof(struct {name}) || (long long)g{name}.a!={initial} || '
                   f'(long long)r{name}.a!={updated} || r{name}.p!={(1<<prefix)-1} || '
                   f'r{name}.tail!=3 || r{name}.end!=77) return {width};']
    header = enum + '\n'.join(decl) + '\n'
    source_owner = header + '\n'.join(owner) + '\n'
    source_companion = header + 'int main(void){\n' + '\n'.join(checks) + '\nreturn 0;}\n'
    def surrogate(source):
        return source.replace(enum, '').replace('enum E a:', base+' a:')
    for a,b in [('host','kcc'), ('kcc','host')]:
        (d/'owner.c').write_text(surrogate(source_owner) if a=='host' else source_owner)
        (d/'companion.c').write_text(surrogate(source_companion) if b=='host' else source_companion)
        object_file(d/'owner.c',d/'owner.o',a); object_file(d/'companion.c',d/'companion.o',b)
        run([HOST,d/'owner.o',d/'companion.o','-o',d/'test'])
        try: run([d/'test'])
        except AssertionError as e: raise AssertionError(f'{base} prefix {prefix} {a}/{b}: {e}') from e

def bool_fixed_controls(d):
    enum = 'enum E : _Bool { E0=0, E1=1 };\n'
    text = enum + r"""
    typedef enum E ET;
    struct S { char c; enum E a:1; ET b:1; enum E :0; char tail; };
    union U { enum E b:1; char c; };
    extern struct S g; extern union U u;
    struct S change(struct S s);
    """
    owner = text + r"""
    struct S g={9,2,0,42}; union U u={.b=9};
    struct S change(struct S s){s.a=0; s.b=3; return s;}
    """
    companion = text + r"""
    int main(void) { struct S s=change(g);
      if (g.a!=1 || g.b!=0 || g.tail!=42 || u.b!=1 || s.a!=0 || s.b!=1) return 1;
      if ((g.b=7)!=1 || g.b!=1 || g.b++!=1 || g.b!=1 || --g.b!=0) return 2;
      if (_Generic(+g.a,int:1,default:0)!=1) return 3;
      return 0;
    }
    """
    def surrogate(source):
        return source.replace(enum, '').replace('typedef enum E ET;', 'typedef _Bool ET;').replace('enum E ', '_Bool ')
    for a,b in [('host','kcc'), ('kcc','host')]:
        (d/'owner.c').write_text((surrogate(owner) if a=='host' else owner)+'\n')
        (d/'companion.c').write_text((surrogate(companion) if b=='host' else companion)+'\n')
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
        for base, maximum, signed in [('char', 8, True), ('signed char', 8, True),
                                      ('unsigned char', 8, False), ('short', 16, True),
                                      ('unsigned short', 16, False)]:
            for prefix in range(1, 8): narrow_fixed_matrix(d, prefix, base, maximum, signed)
            narrow_fixed_controls(d, base, signed)
        bool_fixed_controls(d)
        for base, signed in [('long', True), ('unsigned long', False),
                             ('long long', True), ('unsigned long long', False)]:
            for prefix in range(1, 8): wide_fixed_matrix(d, prefix, base, signed)
            narrow_fixed_controls(d, base, signed)
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
        # Ordinary enums whose values force long/unsigned long compatibility,
        # wide fields and full-width values, not only explicitly fixed enums.
        (d/'ordinary_wide.c').write_text(r"""
        enum S { NEG=-2147483649L, ZERO=0 }; enum U { BIG=18446744073709551615UL };
        struct V { enum S x:64; enum U y:64; enum U :0; char tail; };
        struct V global={NEG,BIG,42};
        int main(void) { struct V v=global;
          if(v.x!=NEG || v.y!=BIG || v.tail!=42) return 1;
          if(v.y++!=BIG || v.y!=0 || ++v.x!=-2147483648L) return 2;
          return 0;
        }
        """)
        object_file(d/'ordinary_wide.c',d/'ordinary_wide.o','kcc')
        run([HOST,d/'ordinary_wide.o','-o',d/'ordinary_wide']); run([d/'ordinary_wide'])
        # Uncast arithmetic on wide enum fields uses width-specific GCC-like
        # extended integer types, including wrap and mixed-rank conversions.
        (d/'wide_operations.c').write_text(r"""
        enum E : unsigned long { ZERO=0, MAX=8589934591UL };
        struct S { enum E x:33; }; struct S g={MAX};
        int main(void){ struct S s=g;
          if (s.x+1 != 0 || (s.x+1UL)!=8589934592UL || ~s.x!=0) return 1;
          s.x=7; s.x+=3; if(s.x!=10 || s.x*3!=30) return 2;
          switch(s.x){case 10:break; default:return 3;}
          return sizeof(+s.x)!=8;
        }
        """)
        object_file(d/'wide_operations.c',d/'wide_operations.o','kcc')
        run([HOST,d/'wide_operations.o','-o',d/'wide_operations']); run([d/'wide_operations'])
        for source in ['enum E : short { A }; struct S { enum E x:17; };',
                       'enum E : unsigned char { A }; struct S { enum E x:9; };',
                       'enum E : signed char { A }; struct S { enum E :9; int x; };',
                       'enum E : short { A }; struct S { enum E x:0; };',
                       'enum E : _Bool { A }; struct S { enum E x:2; };',
                       'enum E : short { A }; struct S { volatile enum E x:3; };',
                       'enum E : unsigned long { A }; struct S { enum E x:65; };',
                       'enum E { A }; struct S { enum E x:33; };',
                       'enum E { A }; struct S { enum E x:0; };',
                       'enum E { A }; struct S { enum E : 33; };',
                       'enum E { A }; struct S { enum E : ; };',
                       'enum E { A }; struct S { volatile enum E x:1; };']:
            (d/'reject.c').write_text(source); r=subprocess.run([str(KCC),str(d/'reject.c')],text=True,capture_output=True)
            diagnostic='aggregate ABI unsupported' if 'f(struct' in source else ('expected' if ': ;' in source else 'bit-field')
            if r.returncode==0 or r.stdout or diagnostic not in r.stderr: raise AssertionError((source,r.returncode,r.stderr,r.stdout))
    print('enum bit-fields: 288 ordinary host/KCC layouts and 2632 fixed-enum/primitive-surrogate layouts '
          f"in both directions passed; unnamed ABI: {'legacy Clang' if kcc_options else 'default'}; "
          'fixed-enum native C23 comparison unavailable')

if __name__=='__main__': main()

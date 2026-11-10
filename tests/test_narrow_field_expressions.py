"""GCC-policy narrow bit-field value types across C23 expression contexts."""
from pathlib import Path
import subprocess
import tempfile
from test_bit_fields import ROOT, HOST, KCC, object_file, run

KINDS=[('signed char',8,True),('unsigned char',8,False),('short',16,True),('unsigned short',16,False),('int',32,True),('unsigned int',32,False),('long',32,True),('unsigned long',32,False)]

def source(base,width,signed,enum,auto):
    decl=f'enum E : {base} {{ E0=0 }};\n' if enum else ''
    typ='enum E' if enum else base
    val='-1' if signed else '1'
    expected_size=1 if width<=8 else 2 if width<=16 else 4
    promote='unsigned int' if width==32 and not signed else 'int'
    inferred='''auto value=s.x; if(!_Generic(value,T:1,default:0) || value!=VALUE) return 5;''' if auto else ''
    return decl+f'''
    struct S {{ {typ} x:{width}; }} s={{ {val} }};
    typedef typeof((0,s.x)) T;
    T saved={val};
    #define VALUE ({val})
    int main(void) {{
      T x=s.x; if(x!=VALUE || saved!=VALUE || sizeof(x)!={expected_size} || sizeof((0,s.x))!={expected_size}) return 1;
      if(!_Generic(s.x,T:1,default:0) || !_Generic((0,s.x),T:1,default:0)) return 2;
      if(sizeof(s.x=0)!={expected_size} || sizeof(s.x++)!={expected_size} || !_Generic((s.x=0),T:1,default:0)) return 7;
      if(_Alignof(T)!={expected_size}) return 8;
      if(!_Generic(+s.x,{promote}:1,default:0)) return 3;
      if(s.x!=VALUE || s.x+1!=VALUE+1) return 4;
      {inferred}
      s.x=0; if(s.x!=0) return 6;
      return 0;
    }}
    '''+'\n'

def main():
    version=subprocess.run([HOST,'--version'],capture_output=True,text=True).stdout.lower()
    oracle='clang' not in version
    (ROOT/'build').mkdir(exist_ok=True)
    count=0
    with tempfile.TemporaryDirectory(prefix='narrow-expr-',dir=ROOT/'build') as tmp:
        d=Path(tmp)
        for base,maximum,signed in KINDS:
            for width in range(1,maximum+1):
                for enum in (False,True):
                    (d/'case.c').write_text(source(base,width,signed,enum,True))
                    object_file(d/'case.c',d/'kcc.o','kcc'); run([HOST,d/'kcc.o','-o',d/'kcc']); run([d/'kcc'])
                    if oracle:
                        # GCC 11 cannot parse fixed enum syntax or C23 auto.
                        native=source(base,width,signed,False,False).replace('typeof','__typeof__')
                        (d/'native.c').write_text(native)
                        object_file(d/'native.c',d/'native.o','host'); run([HOST,d/'native.o','-o',d/'native']); run([d/'native'])
                    count+=1
        # The value type is a real extended integer type, including as the
        # underlying type of a fixed enum, not just a _Generic marker.
        for width in (3,7,9,17,31):
            for signed in (True,False):
                base='signed int' if signed else 'unsigned int'
                value='-1' if signed else str((1<<width)-1)
                size=1 if width<=8 else 2 if width<=16 else 4
                text=f"""struct F {{{base} x:{width};}} f;
                  typedef typeof((0,f.x)) T; enum E:T {{ZERO=0, VALUE={value}}};
                  enum E global=VALUE; struct S {{enum E x:{width};}} s={{VALUE}};
                  int main(void) {{ auto a=s.x; if(sizeof(global)!={size} || global!=VALUE) return 1;
                    if(!_Generic(global,T:1,default:0) || !_Generic(a,T:1,default:0)) return 2;
                    global=0; global++; if(global!=1 || s.x!=VALUE) return 3; return 0; }}
                  """
                (d/'enum.c').write_text(text+'\n')
                object_file(d/'enum.c',d/'enum.o','kcc');run([HOST,d/'enum.o','-o',d/'enum']);run([d/'enum'])
        if oracle:
            for width in (1,7,8,9,16,17,31,32):
                for signed in (True,False):
                    base='signed int' if signed else 'unsigned int'
                    value='-1' if signed else '1'
                    header=f"static struct F {{ {base} x:{width}; }} f; typedef typeof((0,f.x)) T;\n"
                    common='extern T global; T echo(T); int receive(int,...);\n'
                    owner=f"""#include <stdarg.h>
                    T global={value}; T echo(T x) {{return x;}}
                    int receive(int n, ...) {{ va_list ap; va_start(ap,n);
                      int x=va_arg(ap,int); va_end(ap); return n==1 && x=={value}; }}
                    """
                    companion=f"""int main(void) {{ if(echo(global)!={value} || !receive(1,global)) return 1;
                      return 0; }}
                    """
                    # unsigned 32-bit values promote to unsigned int, not int.
                    if width==32 and not signed:
                        owner=owner.replace('int x=va_arg(ap,int)', 'unsigned int x=va_arg(ap,unsigned int)')
                    for left,right in [('kcc','host'),('host','kcc')]:
                        for name,compiler,body in [('owner.c',left,owner),('companion.c',right,companion)]:
                            text=header+common+body+'\n'
                            (d/name).write_text(text.replace('typeof','__typeof__') if compiler=='host' else text)
                        object_file(d/'owner.c',d/'owner.o',left); object_file(d/'companion.c',d/'companion.o',right)
                        run([HOST,d/'owner.o',d/'companion.o','-o',d/'cross']);run([d/'cross'])
        (d/'bool.c').write_text('''struct S {_Bool x:1;}s={1};
          int main(void){auto x=s.x; if(!_Generic(s.x,_Bool:1,default:0)) return 1;
          if(!_Generic(x,_Bool:1,default:0) || sizeof((0,s.x))!=1) return 2; return 0;}\n''')
        object_file(d/'bool.c',d/'bool.o','kcc'); run([HOST,d/'bool.o','-o',d/'bool']);run([d/'bool'])
    print(f'narrow field expressions: {count} primitive/enum cases; GCC surrogate oracle and cross-object ABI: {oracle}')

if __name__=='__main__': main()

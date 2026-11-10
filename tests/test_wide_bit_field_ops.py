"""End-to-end GCC-policy arithmetic on 33–63-bit integer bit-fields.

Clang chooses a different implementation-defined type; only GCC is a native
expression oracle. Enum cases use a primitive host surrogate because GCC 11
cannot parse C23 fixed-underlying enums.
"""
from pathlib import Path
import subprocess
import tempfile
from test_bit_fields import ROOT, HOST, KCC, object_file, run

KINDS = [('signed long', True), ('unsigned long', False),
         ('signed long long', True), ('unsigned long long', False)]

def fixture(base, signed, width, enum):
    prefix = f'enum E : {base} {{ E0=0, E1=1 }};\n' if enum else ''
    typ = 'enum E' if enum else base
    if signed:
        body = f"""
        struct S s={{-1}}; long arr[3]={{4,8,12}};
        if (s.x+0U!=-1 || s.x<0!=1 || (s.x>>1)!=-1 || sizeof(+s.x)!=8) return 1;
        if (_Generic(+s.x,long:1,long long:2,default:0)!=0) return 2;
        s.x=12; s.x+=5; if(s.x!=17 || s.x*2!=34 || (s.x>>1)!=8) return 3;
        s.x=1; if(arr[s.x]!=8 || (1?s.x:0)!=1) return 4;
        switch(s.x){{case 1:break;default:return 5;}}
        s.x=-17; if(s.x/5!=-3 || s.x%5!=-2 || (s.x&7)!=7) return 6;
        return 0;
        """
    else:
        maxvalue=(1<<width)-1; after=1<<width
        body = f"""
        struct S s={{{maxvalue}ULL}}; long arr[3]={{4,8,12}};
        if (s.x+1!=0 || ~s.x!=0 || -s.x!=1 || (s.x+1UL)!={after}UL) return 1;
        if (sizeof(+s.x)!=8 || _Generic(+s.x,unsigned long:1,default:0)!=0) return 2;
        s.x=12; s.x+=5; if(s.x!=17 || s.x*2!=34 || (s.x<<1)!=34) return 3;
        s.x=1; if(arr[s.x]!=8 || (1?s.x:0)!=1) return 4;
        switch(s.x){{case 1:break;default:return 5;}}
        s.x=17; if(s.x/5!=3 || s.x%5!=2 || (s.x^3)!=18) return 6;
        return 0;
        """
    return prefix + f'struct S {{ {typ} x:{width}; }};\nint main(void){{\n' + body + '}\n'

def main():
    (ROOT/'build').mkdir(exist_ok=True)
    version=subprocess.run([HOST,'--version'],capture_output=True,text=True,timeout=10).stdout.lower()
    gcc_oracle='clang' not in version
    with tempfile.TemporaryDirectory(prefix='wide-ops-',dir=ROOT/'build') as tmp:
        d=Path(tmp)
        for base,signed in KINDS:
            for width in range(33,64):
                for enum in (False,True):
                    text=fixture(base,signed,width,enum)
                    (d/'source.c').write_text(text)
                    object_file(d/'source.c',d/'kcc.o','kcc')
                    run([HOST,d/'kcc.o','-o',d/'test']); run([d/'test'])
                    if gcc_oracle:
                        host_text=fixture(base,signed,width,False)
                        (d/'native.c').write_text(host_text)
                        object_file(d/'native.c',d/'native.o','host')
                        run([HOST,d/'native.o','-o',d/'native']); run([d/'native'])
        # Effects through assignment/postfix/comma, pointer indices, typeof
        # and actual variadic passing/retrieval of the extended expression type.
        (d/'integration.c').write_text(r"""
        #include <stdarg.h>
        struct S { unsigned long u:33; signed long s:40; } g={7,-3};
        typedef typeof(+g.u) U; typedef typeof(+g.s) S;
        S static_signed=-1; U static_unsigned=8589934591UL;
        int take(int n, ...) { va_list ap; va_start(ap,n);
            U u=va_arg(ap,U); S s=va_arg(ap,S);
            va_end(ap); return u==7 && s==-3; }
        int main(void) { int a[3]={4,8,12};
          unsigned char *bytes=(unsigned char*)&static_signed;
          for(int i=0;i<8;i++) if(bytes[i]!=255) return 4;
          if(static_unsigned!=8589934591UL || !take(2,g.u,g.s)) return 1;
          if(_Generic(g.u,U:0,default:1) || _Generic((0,g.s),S:0,default:1)) return 5;
          if((0,g.u)+1!=8 || (g.u=2)+1!=3 || g.u++ + 1!=3) return 2;
          if(a[g.u-1]!=12 || sizeof(typeof((0,g.u)))!=8) return 3;
          return 0; }
        """)
        (d/'mixed-bitint.c').write_text(r"""
        struct S { unsigned long u:33; signed long s:40; unsigned long v:40; } g;
        typedef typeof(+g.u) U; typedef typeof(+g.v) V;
        int main(void) {
          if (!_Generic(g.u + (_BitInt(33))1, U:1, default:0)) return 1;
          if (!_Generic((_BitInt(33))1 + g.u, U:1, default:0)) return 2;
          if (!_Generic(g.s + (unsigned _BitInt(40))1, V:1, default:0)) return 3;
          return 0;
        }
        """)
        object_file(d/'mixed-bitint.c',d/'mixed-bitint.o','kcc')
        run([HOST,d/'mixed-bitint.o','-o',d/'mixed-bitint']); run([d/'mixed-bitint'])
        object_file(d/'integration.c',d/'integration.o','kcc')
        run([HOST,d/'integration.o','-o',d/'integration']); run([d/'integration'])
        if gcc_oracle:
            (d/'integration-native.c').write_text((d/'integration.c').read_text().replace('typeof', '__typeof__'))
            object_file(d/'integration-native.c',d/'integration-native.o','host')
            run([HOST,d/'integration-native.o','-o',d/'integration-native']); run([d/'integration-native'])
        if gcc_oracle:
            # Separate objects in both directions test the actual x86-64 ABI,
            # including fixed returns, ellipsis and signed static storage.
            decl = r"""
            #include <stdarg.h>
            struct Fields { unsigned long u:33; signed long s:40; };
            extern struct Fields fields;
            typedef typeof(+fields.u) U;
            typedef typeof(+fields.s) S;
            extern S negative;
            U echo(U x); int receive(int n, ...);
            """
            owner = decl + r"""
            struct Fields fields={8589934591UL,-3}; S negative=-1;
            U echo(U x) { return x; }
            int receive(int n, ...) { va_list ap; va_start(ap,n);
              U u=va_arg(ap,U); S s=va_arg(ap,S); va_end(ap);
              return n==2 && u==8589934591UL && s==-3; }
            """
            companion = decl + r"""
            int main(void) {
              unsigned char *p=(unsigned char*)&negative;
              for(int i=0;i<8;i++) if(p[i]!=255) return 1;
              if(echo(fields.u)!=8589934591UL || !receive(2,fields.u,fields.s)) return 2;
              return 0;
            }
            """
            for left,right in [('kcc','host'),('host','kcc'),('kcc','kcc'),('host','host')]:
                (d/'owner.c').write_text(owner.replace('typeof', '__typeof__') if left == 'host' else owner)
                (d/'companion.c').write_text(companion.replace('typeof', '__typeof__') if right == 'host' else companion)
                object_file(d/'owner.c',d/'owner.o',left)
                object_file(d/'companion.c',d/'companion.o',right)
                run([HOST,d/'owner.o',d/'companion.o','-o',d/'cross']); run([d/'cross'])
    print(f'wide field expressions: 248 integer/enum cases; GCC oracle: {gcc_oracle}; mixed ranks, updates, switch, pointer, typeof and variadics passed; cross-object GCC ABI: {gcc_oracle}')

if __name__=='__main__': main()

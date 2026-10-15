"""Live host object pointers exercise kcc values without unsupported address syntax."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root/'build'/'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
identity = '''int *identity(int *p) { int *q=p; return (int *)q; }
int **identity_two(int **p) { return (int **)p; }
_Bool truth(int *p) { return p; }
int negate(int *p) { return !p; }
int *choose(int *p,int *q) { if(p) return p; return q; }
'''
identity_prototypes = '''int *identity(int *); int **identity_two(int **);
_Bool truth(int *); int negate(int *); int *choose(int *,int *);
'''
signature = 'int bits(int *a,char *b,short *c,long *d,unsigned char *e,int *f,int **g,_Bool *h)'
arguments = 'a,b,c,d,e,f,g,h'
# Logical/! use full pointer truth, not pointer comparisons or dereference.
bits_body = ''' { return !!a+(!!b<<1)+(!!c<<2)+(!!d<<3)+(!!e<<4)+(!!f<<5)+(!!g<<6)+(!!h<<7); }
'''
relay = signature.replace('bits(', 'relay(')+' { return bits('+arguments+'); }\n'
prototypes = signature+';\n'+signature.replace('bits(', 'relay(')+';\n'
main = '''int main(void) {
 int a=42,f=7; char b=1; short c=2; long d=3; unsigned char e=4; int *g=&a; _Bool h=1;
 if(identity(&a)!=&a || identity(0)!=0 || identity_two(&g)!=&g) return 1;
 if(!truth(&a) || truth(0) || negate(&a) || !negate(0)) return 2;
 if(choose(&a,&f)!=&a || choose(0,&f)!=&f) return 3;
 if(bits(&a,&b,&c,&d,&e,&f,&g,&h)!=255) return 4;
 if(bits(0,&b,&c,&d,&e,&f,&g,&h)!=254) return 5;
 if(bits(&a,0,&c,&d,&e,&f,&g,&h)!=253) return 6;
 if(bits(&a,&b,0,&d,&e,&f,&g,&h)!=251) return 7;
 if(bits(&a,&b,&c,0,&e,&f,&g,&h)!=247) return 8;
 if(bits(&a,&b,&c,&d,0,&f,&g,&h)!=239) return 9;
 if(bits(&a,&b,&c,&d,&e,0,&g,&h)!=223) return 10;
 if(bits(&a,&b,&c,&d,&e,&f,0,&h)!=191) return 11;
 if(bits(&a,&b,&c,&d,&e,&f,&g,0)!=127) return 12;
 if(relay(&a,&b,&c,&d,&e,&f,&g,&h)!=255) return 13;
 if(relay(&a,&b,&c,&d,&e,&f,0,0)!=63) return 14;
 return 42;
}
'''
# bits/identity are kcc callees, relay is a kcc caller of a host function. A
# second linkage arrangement reverses those roles. main remains host C because
# address-of and null-pointer source syntax intentionally belong to later steps.
kcc_one = identity+signature+bits_body+signature.replace('bits(', 'host_bits(')+';\n'+relay.replace('return bits(', 'return host_bits(')
host_one = identity_prototypes+prototypes+signature.replace('bits(', 'host_bits(')+bits_body+main
kcc_two = identity_prototypes+signature+';\n'+relay
host_two = identity+signature+bits_body+signature.replace('bits(', 'relay(')+';\n'+main
with tempfile.TemporaryDirectory(prefix='kcc pointer values ') as directory:
    directory = Path(directory)
    source, other, il, assembly, obj, executable = [directory/name for name in ('k.c','h.c','p.ssa','p.s','h.o','p')]
    for text, host_text in [(kcc_one,host_one), (kcc_two,host_two)]:
        source.write_text(text)
        other.write_text(host_text)
        result = subprocess.run([str(compiler),str(source)],capture_output=True,text=True,timeout=5)
        assert result.returncode==0 and not result.stderr, result.stderr
        assert 'call $' in result.stdout and ' l %t' in result.stdout, result.stdout
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe,'-t','amd64_sysv','-o',str(assembly),str(il)],check=True,timeout=10)
            subprocess.run([host,'-std=c2x','-fsigned-char','-c',str(other),'-o',str(obj)],check=True,timeout=10)
            subprocess.run([host,str(assembly),str(obj),'-o',str(executable)],check=True,timeout=10)
            result = subprocess.run([str(executable)],timeout=5)
            assert result.returncode==42, result.returncode
    # The syntax/type bound is independent of expression depth and token cache.
    for depth, valid in [(1,True),(64,True),(65,False)]:
        stars = '*'*depth
        source.write_text(f'int {stars}f(int {stars}p) {{ return (int {stars})p; }}\n')
        result = subprocess.run([str(compiler),str(source)],capture_output=True,text=True,timeout=5)
        assert (result.returncode==0)==valid and bool(result.stdout)==valid,result.stderr
        if not valid:
            assert 'pointer type exceeds depth limit (64)' in result.stderr,result.stderr
        elif qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe,'-t','amd64_sysv','-o',str(assembly),str(il)],check=True,timeout=10)
    rejected = [
        ('int *f(char *p) { return p; }','pointer conversion'),
        ('int *f(int **p) { return p; }','pointer conversion'),
        ('int *f(int *p) { int *q=0; return p; }','pointer conversion'),
        ('int *f(int *p) { return (int *)0; }','pointer conversion'),
        ('int f(int *p) { return (int)p; }','pointer conversion'),
        ('char *f(int *p) { return (char *)p; }','pointer conversion'),
        ('int *f(int *p) { p=1; return p; }','pointer conversion'),
        ('int f(int *p) { return +p; }','requires an integer'),
        ('int f(int *p) { return -p; }','requires an integer'),
        ('int f(int *p) { return ~p; }','requires an integer'),
        ('int *f(int *p) { return p+1; }','pointer binary'),
        ('int f(int *p) { return p==p; }','pointer binary'),
        ('int *f(void); unsigned *f(void);','incompatible function'),
        ('int f(int **); int f(int *);','incompatible function'),
        ('int *main(void) { int *p; return p; }','main must return int'),
    ]
    for text, message in rejected:
        source.write_text(text+'\n')
        result = subprocess.run([str(compiler),str(source)],capture_output=True,text=True,timeout=5)
        assert result.returncode==1 and not result.stdout and message in result.stderr,(text,result.stderr)
    # Unsupported declarator syntax must not be reinterpreted as a simpler type.
    for text in ('int (*f)(void);','int f(int p[2]);','void *f(void);','int *const f(void);'):
        source.write_text(text+'\n')
        result = subprocess.run([str(compiler),str(source)],capture_output=True,text=True,timeout=5)
        assert result.returncode==1 and not result.stdout and result.stderr,(text,result.stderr)
print(f'Pointer values passed (live-object ABI both linkage directions, mixed eight args, 64/65 type bounds, {len(rejected)+4} constraints; {host})'
      + ('; QBE/runtime passed' if qbe else '; runtime requires QBE'))

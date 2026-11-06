"""Bit-precise wb/WB literals with currently supported exact minimal widths."""
from pathlib import Path
import subprocess
import tempfile
from test_bit_fields import ROOT, HOST, KCC, object_file, run

SOURCE = r'''
#define CAT_(a,b) a##b
#define CAT(a,b) CAT_(a,b)
#define I8 CAT(64,wb)
static _BitInt(8) s8=I8; static unsigned _BitInt(8) u8=0x80uWB;
static _BitInt(16) s16=0b100000000000000WB; static unsigned _BitInt(16) u16=32768wbu;
static _BitInt(32) s32=1'073'741'824wb; static unsigned _BitInt(32) u32=2147483648Uwb;
static _BitInt(64) s64=4611686018427387904WB; static unsigned _BitInt(64) u64=0x8000000000000000WBU;
static_assert(_Generic(64wb, _BitInt(8):1, default:0));
static_assert(_Generic(127WB, _BitInt(8):1, default:0));
static_assert(_Generic(255uwb, unsigned _BitInt(8):1, default:0));
static_assert(_Generic(128UWB, unsigned _BitInt(8):1, default:0));
static_assert(_Generic(16384WB, _BitInt(16):1, default:0));
static_assert(_Generic(32768wbu, unsigned _BitInt(16):1, default:0));
static_assert(_Generic(1073741824wb, _BitInt(32):1, default:0));
static_assert(_Generic(2147483648uwb, unsigned _BitInt(32):1, default:0));
static_assert(_Generic(4611686018427387904wb, _BitInt(64):1, default:0));
static_assert(_Generic(9223372036854775808uwb, unsigned _BitInt(64):1, default:0));
static_assert(_Generic(0xffffffffffffffffuwb, unsigned _BitInt(64):1, default:0));
static_assert(0xffffffffffffffffuwb == 18446744073709551615UL);
enum E { E8=64wb, E9 }; static_assert(E9==65);
static_assert(sizeof(64wb)==1 && sizeof(32768uwb)==2 && sizeof(1073741824wb)==4 && sizeof(0x8000000000000000UWB)==8);
static_assert(~64wb == -65);
int main(void) {
 if(s8!=64 || u8!=128 || s16!=16384 || u16!=32768) return 1;
 if(s32!=1073741824 || u32!=2147483648U || s64!=4611686018427387904L || u64!=9223372036854775808UL) return 2;
 if ((unsigned _BitInt(8))(u8+128uwb)!=0 || ~s8!=-65) return 3;
 if (_Generic(I8,_BitInt(8):1,default:0)!=1) return 4;
 return 0;
}
'''

def main():
    (ROOT/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bitint-literals-',dir=ROOT/'build') as tmp:
        d=Path(tmp); (d/'positive.c').write_text(SOURCE)
        object_file(d/'positive.c',d/'positive.o','kcc'); run([HOST,d/'positive.o','-o',d/'positive']); run([d/'positive'])
        for literal in ('0wb','1wb','63wb','128wb','1uwb','127uwb','256uwb','32768wb','2147483648wb','0xffffffffffffffffwb'):
            (d/'reject.c').write_text(f'int main(void){{return {literal};}}')
            r=subprocess.run([str(KCC),str(d/'reject.c')],text=True,capture_output=True)
            if r.returncode==0 or r.stdout or 'bit-precise integer literals are not supported yet for this required width' not in r.stderr:
                raise AssertionError((literal,r.returncode,r.stderr,r.stdout))
        for source, diagnostic in [('#if 64wb\n#endif\nint main(void){return 0;}', 'bit-precise integer literals are not supported yet'), ('int f(int, ...); int g(void){return f(1,128uwb);}', 'variadic ABI')]:
            (d/'reject.c').write_text(source)
            r=subprocess.run([str(KCC),str(d/'reject.c')],text=True,capture_output=True)
            if r.returncode==0 or r.stdout or diagnostic not in r.stderr:
                raise AssertionError((source,r.returncode,r.stderr,r.stdout))
        for literal in ('64wB','64Wb','64wbL','64uwbu'):
            (d/'reject.c').write_text(f'int main(void){{return {literal};}}')
            r=subprocess.run([str(KCC),str(d/'reject.c')],text=True,capture_output=True)
            if r.returncode==0 or r.stdout or 'unsupported integer suffix' not in r.stderr:
                raise AssertionError((literal,r.returncode,r.stderr,r.stdout))
    print('bit-precise literals: 8/16/32/64 exact-width execution and boundary rejections passed; host C23 comparison unavailable')

if __name__=='__main__': main()

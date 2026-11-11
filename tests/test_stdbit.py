"""Target-specific C23 stdbit.h unsigned integer helpers."""
import os
import subprocess
import tempfile
from pathlib import Path
from runtime_link import runtime_link_flags

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')
source_text = r'''
#include <stdbit.h>
#include <stdbit.h>
#if __STDC_ENDIAN_NATIVE__ != __STDC_ENDIAN_LITTLE__
#error wrong target endian
#endif
#define CHECK(T,W) { T x=(T)8; T zero=(T)0; T all=(T)~zero; \
 if (stdc_leading_zeros(zero)!=(W) || stdc_trailing_zeros(zero)!=(W)) return 1; \
 if (stdc_leading_ones(all)!=(W) || stdc_trailing_ones(all)!=(W)) return 2; \
 if (stdc_first_leading_one(x)!=(W)-3 || stdc_first_trailing_one(x)!=4) return 3; \
 if (stdc_first_leading_zero(all) || stdc_first_trailing_zero(all)) return 4; \
 if (stdc_count_ones(x)!=1 || stdc_count_zeros(x)!=(W)-1) return 5; \
 if (!stdc_has_single_bit(x) || stdc_has_single_bit(zero)) return 6; \
 if (stdc_bit_width(x)!=4 || stdc_bit_floor((T)9)!=(T)8 || stdc_bit_ceil((T)9)!=(T)16) return 7; \
 if (stdc_bit_floor(zero) || stdc_bit_ceil(zero)!=(T)1) return 8; \
 if (!_Generic(stdc_bit_floor(x), T: 1, default: 0) || !_Generic(stdc_bit_ceil(x), T: 1, default: 0)) return 11; \
 x=(T)3; if(stdc_bit_ceil(x++)!=(T)4 || x!=(T)4) return 12; }
int calls; unsigned int value(void) { calls++; return 9U; }
int main(void) {
 CHECK(unsigned char,8) CHECK(unsigned short,16) CHECK(unsigned int,32)
 CHECK(unsigned long,64) CHECK(unsigned long long,64)
 { unsigned int n=7; if (stdc_count_ones(n++) != 3 || n != 8) return 9; }
 if (stdc_leading_zeros_ui(1U)!=31 || stdc_bit_width_ull(0x8000000000000000ULL)!=64) return 10;
 if (stdc_bit_floor(value())!=8 || calls!=1) return 13;
 { volatile unsigned int v=7; if(stdc_count_ones(v++)!=3 || v!=8) return 14; }
 return 42;
}
'''
with tempfile.TemporaryDirectory(prefix='kcc-stdbit-') as directory:
    path = Path(directory)
    source = path / 'test.c'
    source.write_text(source_text)
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0 and not result.stderr, result.stderr
    if qbe:
        il, asm, exe = (path / n for n in ('test.ssa', 'test.s', 'test'))
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), str(Path(os.environ.get('KCC_RUNTIME', root / 'build/libkccrt.a'))), *runtime_link_flags(), '-o', str(exe)], check=True)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
    source.write_text('#include <stdbit.h>\nint f(void){return stdc_count_ones(-1);}\n')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=20)
    assert result.returncode != 0 and result.stderr
print('stdbit checks completed')

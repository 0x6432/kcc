"""C23 UTF-8 conversion runtime: scalar model, restartability, TLS and KCC ABI."""
import os
import subprocess
import tempfile
from pathlib import Path
from runtime_link import runtime_link_flags

root = Path(__file__).resolve().parents[1]
kcc = Path(os.environ.get('KCC', root / 'build/kcc'))
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
runtime = Path(os.environ.get('KCC_RUNTIME', root/'build/libkccrt.a'))
with tempfile.TemporaryDirectory(prefix='kcc uchar8 ') as tmp:
    d = Path(tmp)
    native, source, il, asm, exe = [d / name for name in ('native.c', 'kcc.c', 'kcc.ssa', 'kcc.s', 'test')]
    source.write_text('''#include <uchar.h>
size_t kread(char8_t *p,const char *s,size_t n,mbstate_t *st){return mbrtoc8(p,s,n,st);}
size_t kwrite(char *s,char8_t c,mbstate_t *st){return c8rtomb(s,c,st);}
''')
    native.write_text(r'''
#define _XOPEN_SOURCE 700
#include <errno.h>
#include <locale.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#include <uchar.h>
size_t mbrtoc8(unsigned char *,const char *,size_t,mbstate_t *);
size_t c8rtomb(char *,unsigned char,mbstate_t *);
#ifdef KCC_WRAPPERS
size_t kread(unsigned char *,const char *,size_t,mbstate_t *);
size_t kwrite(char *,unsigned char,mbstate_t *);
#define READ kread
#define WRITE kwrite
#else
#define READ mbrtoc8
#define WRITE c8rtomb
#endif
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"failure line %d: %s\n",__LINE__,#x); return 1; } } while (0)
static unsigned encode(uint32_t c, unsigned char b[4]) {
 if(c<0x80){b[0]=c;return 1;}
 if(c<0x800){b[0]=0xc0|(c>>6);b[1]=0x80|(c&63);return 2;}
 if(c<0x10000){b[0]=0xe0|(c>>12);b[1]=0x80|((c>>6)&63);b[2]=0x80|(c&63);return 3;}
 b[0]=0xf0|(c>>18);b[1]=0x80|((c>>12)&63);b[2]=0x80|((c>>6)&63);b[3]=0x80|(c&63);return 4;
}
static pthread_barrier_t barrier;
static void *worker(void *arg) {
 unsigned char b[4], c; char out[8]; uint32_t cp=(uint32_t)(uintptr_t)arg;
 unsigned n=encode(cp,b);
 if (READ(&c,(char *)b,n,0)!=n || c!=b[0]) return (void *)1;
 pthread_barrier_wait(&barrier);
 for(unsigned i=1;i<n;i++) if(READ(&c,"x",1,0)!=(size_t)-3 || c!=b[i]) return (void *)2;
 if(WRITE(out,b[0],0)!=0) return (void *)3;
 pthread_barrier_wait(&barrier);
 for(unsigned i=1;i<n;i++) {
   size_t r=WRITE(out,b[i],0); if(r!=(i==n-1?n:0)) return (void *)4;
 }
 if(memcmp(out,b,n)) return (void *)5;
 return 0;
}
int main(void) {
 mbstate_t st={0}; unsigned char c=99; char out[16]={0};
 CHECK(setlocale(LC_ALL,"C")!=0);
 CHECK(READ(&c,"A",1,&st)==1 && c=='A' && mbsinit(&st));
 CHECK(READ(&c,"",1,&st)==0 && c==0 && mbsinit(&st));
 CHECK(READ(&c,"x",0,&st)==(size_t)-2 && mbsinit(&st));
 CHECK(WRITE(out,'A',&st)==1 && out[0]=='A' && mbsinit(&st));
 CHECK(WRITE(0,'A',&st)==1 && mbsinit(&st));
 errno=0; CHECK(READ(&c,"\xc3\xa9",2,&st)==(size_t)-1 && errno==EILSEQ);
 memset(&st,0,sizeof(st));
 CHECK(setlocale(LC_ALL,"C.utf8")!=0 || setlocale(LC_ALL,"C.UTF-8")!=0);
 for(uint32_t cp=0;cp<=0x10ffff;cp++) {
   if(cp>=0xd800 && cp<=0xdfff) continue;
   unsigned char b[4]; unsigned n=encode(cp,b); mbstate_t rd={0}, wr={0};
   size_t r=READ(&c,(const char *)b,n,&rd);
   CHECK(r==(cp? n:0) && c==b[0]);
   for(unsigned i=1;i<n;i++) {CHECK(!mbsinit(&rd)); CHECK(READ(&c,"q",1,&rd)==(size_t)-3 && c==b[i]);}
   CHECK(mbsinit(&rd));
   for(unsigned i=0;i<n;i++) {r=WRITE(out,b[i],&wr); CHECK(r==(i==n-1?n:0));}
   CHECK(mbsinit(&wr) && memcmp(out,b,n)==0);
 }
 memset(&st,0,sizeof(st));
 CHECK(READ(&c,"\xf0\x9f",2,&st)==(size_t)-2 && !mbsinit(&st));
 CHECK(READ(&c,"\x98\x80",2,&st)==2 && c==0xf0);
 CHECK(READ(&c,"z",1,&st)==(size_t)-3 && c==0x9f);
 CHECK(READ(0,0,0,&st)==(size_t)-3);
 CHECK(READ(&c,"z",1,&st)==(size_t)-3 && c==0x80 && mbsinit(&st));
 CHECK(READ(&c,"z",1,&st)==1 && c=='z');
 /* Copying an in-progress state must make two independent continuations. */
 memset(&st,0,sizeof(st)); CHECK(READ(&c,"\xe2\x82\xac",3,&st)==3 && c==0xe2);
 mbstate_t clone=st; CHECK(READ(&c,"",0,&st)==(size_t)-3 && c==0x82);
 CHECK(READ(&c,"",0,&clone)==(size_t)-3 && c==0x82);
 CHECK(READ(&c,"",0,&st)==(size_t)-3 && c==0xac && mbsinit(&st));
 CHECK(READ(&c,"",0,&clone)==(size_t)-3 && c==0xac && mbsinit(&clone));
 memset(&st,0,sizeof(st)); CHECK(WRITE(out,0xe2,&st)==0); clone=st;
 CHECK(WRITE(out,0x82,&st)==0 && WRITE(out,0xac,&st)==3);
 CHECK(WRITE(out,0x82,&clone)==0 && WRITE(out,0xac,&clone)==3);
 CHECK(mbsinit(&clone) && !memcmp(out,"\xe2\x82\xac",3));
 memset(&st,0,sizeof(st)); errno=0;
 CHECK(READ(&c,"\xed\xa0\x80",3,&st)==(size_t)-1 && errno==EILSEQ);
 memset(&st,0,sizeof(st)); CHECK(WRITE(out,0xe0,&st)==0 && !mbsinit(&st));
 errno=0; CHECK(WRITE(out,0x80,&st)==(size_t)-1 && errno==EILSEQ);
 memset(&st,0,sizeof(st)); CHECK(WRITE(out,0xed,&st)==0); errno=0;
 CHECK(WRITE(out,0xa0,&st)==(size_t)-1 && errno==EILSEQ);
 memset(&st,0,sizeof(st)); CHECK(WRITE(out,0xf4,&st)==0); errno=0;
 CHECK(WRITE(out,0x90,&st)==(size_t)-1 && errno==EILSEQ);
 memset(&st,0,sizeof(st)); CHECK(WRITE(out,0xf0,&st)==0); errno=0;
 CHECK(WRITE(0,0,&st)==(size_t)-1 && errno==EILSEQ);
 memset(&st,0,sizeof(st)); errno=0; CHECK(WRITE(out,0x80,&st)==(size_t)-1 && errno==EILSEQ);
 pthread_t a,b; void *ra,*rb; CHECK(!pthread_barrier_init(&barrier,0,2));
 CHECK(!pthread_create(&a,0,worker,(void *)(uintptr_t)0x1f600));
 CHECK(!pthread_create(&b,0,worker,(void *)(uintptr_t)0x20ac));
 CHECK(!pthread_join(a,&ra) && !pthread_join(b,&rb) && !ra && !rb);
 CHECK(!pthread_barrier_destroy(&barrier));
 puts("uchar8: all Unicode scalar values, partial conversions, errors and pthread TLS passed");
 return 0;
}
''')
    r = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=20)
    assert r.returncode == 0 and not r.stderr, r.stderr
    extra = []
    if qbe:
        il.write_text(r.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True, timeout=20)
        extra = ['-DKCC_WRAPPERS', str(asm)]
    subprocess.run([host, '-std=c11', '-O2', '-pthread', *extra, str(native), str(runtime), *runtime_link_flags(), '-o', str(exe)], check=True, timeout=30)
    symbols = subprocess.check_output(['nm', str(exe)], text=True)
    assert ' T mbrtoc8' in symbols and ' T c8rtomb' in symbols, symbols
    subprocess.run([str(exe)], check=True, timeout=60)
    print('KCC/QBE native-wrapper interoperability passed' if qbe else 'KCC/QBE wrapper execution not run')

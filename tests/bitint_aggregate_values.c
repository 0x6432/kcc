#include <stdarg.h>
typedef _BitInt(5) S5;
typedef unsigned _BitInt(17) U17;
typedef _BitInt(33) S33;
typedef unsigned _BitInt(63) U63;
struct Small { S5 x; U17 y; };
struct Mixed { double d; S33 x; };
struct Large { U63 x[4]; S5 y; };
static struct Small initial = { -16, 131071 };
struct Small change(struct Small a) { a.x = -1; a.x++; a.x -= (S5)1; return a; }
struct Mixed mixed(long a,long b,long c,long d,long e,long f,struct Mixed x) {
 if (a+b+c+d+e+f!=21 || x.d!=1.5 || x.x!=(S33)-4294967296L) x.d=0;
 else { x.x=(S33)-1; x.d=2.5; } return x;
}
struct Large large(struct Large x) { x.x[2]--; x.y=-1; return x; }
int variadic(int n,...) {
 va_list ap,cp; va_start(ap,n); va_copy(cp,ap);
 struct Small a=va_arg(ap,struct Small), b=va_arg(cp,struct Small);
 struct Mixed m=va_arg(ap,struct Mixed); struct Large z=va_arg(ap,struct Large);
 va_end(cp); va_end(ap);
 return n!=7 || a.x!=-16 || a.y!=131071 || b.x!=-16 || m.d!=1.5 ||
 m.x!=(S33)-4294967296L || z.x[2]!=4 || z.y!=-16;
}
int main(void) {
 struct Small s=initial, t=change(s);
 struct Mixed m={1.5,(S33)-4294967296L}, n=mixed(1,2,3,4,5,6,m);
 struct Large z={{1,2,4,8},-16}, r=large(z);
 volatile S5 v=-16; v++; v-=1;
 if(s.x!=-16 || t.x!=-1 || t.y!=131071 || v!=-16) return 1;
 if(n.d!=2.5 || n.x!=-1 || r.x[2]!=3 || r.y!=-1) return 2;
 if(variadic(7,s,m,z)) return 3;
 return 0;
}

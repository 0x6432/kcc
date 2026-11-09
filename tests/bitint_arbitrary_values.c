typedef _BitInt(5) S; typedef unsigned _BitInt(5) U;
typedef _BitInt(33) L; typedef unsigned _BitInt(33) UL;
_Static_assert(_Generic(1wb, _BitInt(2):1, default:0), "literal");
_Static_assert((U)31+(U)1==0, "wrap");
_Static_assert((S)-7/(S)2==-3 && (S)-7%(S)2==-1, "signed division");
_Static_assert((L)-4294967296L < (L)0, "wide negative");
_Static_assert((UL)8589934591UL+(UL)1==0, "wide wrap");
enum E { A=1wb, B }; _Static_assert(B==2, "enum");
enum Wide { WA=-4294967296wb, WB }; _Static_assert(WB == -4294967295L, "wide enum");
static L wide=-4294967296L; static U vector[3]={(U)31,(U)3,(U)16};
static struct R { S a; UL b; } record = { (S)-5, (UL)8589934591UL };
int main(void) {
 volatile S x=(S)-7, y=(S)2; volatile U u=(U)31, one=(U)1;
 volatile L l=wide; volatile UL ul=(UL)8589934591UL;
 if ((long)wide!=-4294967296L || l>=0 || (unsigned long)ul!=8589934591UL) return 1;
 if (x/y!=-3 || x%y!=-1 || (x>>1)!=-4 || (x&(S)3)!=1) return 2;
 if ((U)(u+one)!=0 || (U)(u*one)!=31 || (U)~u!=0) return 3;
 if (u++!=31 || u!=0 || --u!=31 || (u+=one)!=0 || u!=0) return 4;
 if (l+ (L)1 != -4294967295L || (l>>1)!=-2147483648L || ((L)1 << (UL)2)!=4) return 5;
 if ((UL)(ul+(UL)1)!=0 || (UL)(ul*(UL)2)!=8589934590UL) return 6;
 if (vector[0]!=31 || vector[1]!=3 || vector[2]!=16 || record.a!=-5 || record.b!=8589934591UL) return 7;
 S a[3]={(S)-5,(S)3,(S)-1}; if (*(&a[1]+(L)-1)!=-5) return 8;
 if ((double)x!=-7.0 || (S)-7.0!=-7 || (UL)3.0!=3 || (double)(UL)7!=7.0) return 9;
 if ((double)l!=-4294967296.0 || (L)-123.0!=-123 || (UL)4294967296.0!=4294967296UL) return 12;
 L mixed=(L)-7; mixed+=2; mixed*=(L)2; mixed/=(L)2; if(mixed!=-5) return 13;
 S *p=&a[0]; p+=(L)1; if (*p!=3) return 14;
 if ((unsigned long)(S)-1!=18446744073709551615UL || (long)(U)31!=31) return 10;
 switch (l) { case (L)-4294967296L: break; default: return 11; }
 return 0;
}

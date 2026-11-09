typedef unsigned _BitInt(13) U13;
typedef _BitInt(47) I47;
struct S { unsigned before:3; U13 small:3; I47 large:39; unsigned after:2; char tail; };
static struct S global={5,7,-1,2,71};
static int calls;
static struct S *once(struct S *s) { calls++; return s; }
int main(void) {
 struct S x=global;
 if (x.before!=5 || x.small!=7 || x.large!=-1 || x.after!=2 || x.tail!=71) return 1;
 if (!_Generic((0,x.small),U13:1,default:0) || !_Generic((0,x.large),I47:1,default:0)) return 2;
 if (x.small+1!=8 || x.large+2!=1) return 3;
 if (once(&x)->small++!=7 || calls!=1 || x.small!=0) return 4;
 if (++x.small!=1 || (x.small+=3)!=4 || (x.small=9)!=1) return 5;
 if (x.large++!=-1 || x.large!=0 || --x.large!=-1) return 6;
 x.large=274877906943L; x.large++; if(x.large!=-274877906944L) return 7;
 if(x.before!=5 || x.after!=2 || x.tail!=71) return 8;
 return 0;
}

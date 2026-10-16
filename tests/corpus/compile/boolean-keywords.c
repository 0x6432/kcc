#define CAT(a,b) a##b
bool id(const _Bool x) { return x; }
int main(void) { const bool x=CAT(tr,ue); bool a[2]; a[0]=false; a[1]=id(x); return (a[0],+a[1])+41; }

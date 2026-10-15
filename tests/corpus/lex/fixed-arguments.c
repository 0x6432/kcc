#define ID(x) x
#define ADD(a,b) ((a)+(b))
#define CALL(f,x) f(x)
#define DROP(x) 7
int main(void) { return ADD(ID(ID(3)),CALL(ID,4))+DROP(BAD(1)); }

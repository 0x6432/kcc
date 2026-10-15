#define DROP(x) 42
#define V(x,...) DROP(#__VA_OPT__(x))
#define INNER(x,...) #__VA_OPT__(#x)
int main(void) { return V(INNER(a,1),1); }

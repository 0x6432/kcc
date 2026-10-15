#define A 7
#define BAD(a,b) a+b
#define V(x,...) #__VA_OPT__(x BAD(x) A)
#define RAW(x,...) #__VA_OPT__(#x)
#define E
V(A,1) V(BAD(1),E) RAW("text",1)

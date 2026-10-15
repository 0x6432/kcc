#define ID(x) x
#define f(x) x x
#define h(x) f(x)
#define g f
#define COMMA 1,2
#define ADD(a,b) a+b
#define CALL(x) ADD(x)
h(g)(7) ID() CALL(COMMA)
#define DROP(a,b) 7
DROP({1,2})

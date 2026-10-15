#define S(x) #x
#define X(x) S(x)
#define E
#define F(x) a+x+b
#define V(...) a+__VA_OPT__() b
S(a + b) X(F(7 E)) X(V()) X(S(S(a)))
S("quoted\\text") S('"')

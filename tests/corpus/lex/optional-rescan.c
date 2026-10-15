#define LP() (
#define G(x) 42
#define V(r,x,...) __VA_OPT__(G r x) )
#define SELF(...) __VA_OPT__(SELF(__VA_ARGS__))
int main(void) { return V(LP(),0,1); }
SELF(SELF(7))

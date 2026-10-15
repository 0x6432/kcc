#define F(x,...) #__VA_OPT__(x##x x##x)
#define G(x,...) __VA_OPT__(a x##x) ## b
#define DROP(x) 42
int main(void) { return DROP(F(,1)); }
G(,1)

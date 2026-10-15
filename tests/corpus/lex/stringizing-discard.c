#define DROP(x) 42
#define OUT(x,...) DROP(__VA_OPT__(#x))
#define RAW(...) DROP(#__VA_ARGS__)
int main(void) { return OUT(BAD(1),1)+RAW(a,b)-42; }

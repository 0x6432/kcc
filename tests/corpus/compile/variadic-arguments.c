#define EMPTY
#define FORWARD(...) __VA_ARGS__
#define CALL(f,...) f(__VA_ARGS__)
#define SUM(x,...) x __VA_OPT__(+ __VA_ARGS__)
int add(int x,int y) { return x+y; }
int main(void) { return SUM(FORWARD(CALL(add,20,22)),EMPTY); }

#define X not_expanded
%:warning X+12u /**/ .5
int main(void) { return 42; }
#error final

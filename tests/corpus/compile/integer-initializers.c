int exported;
extern int exported = 40 + 2;
static unsigned char byte = 258;
static _Bool flag = 256;
int main(void) { return exported == 42 && byte == 2 && flag ? 42 : 1; }

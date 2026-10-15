#define BYTE unsigned char
char f(char a) { return a+1; }
int main(void) { BYTE u=255; signed char c=128; u=u+1; if(!u && c<0) return f(41); return 0; }

#define HALF unsigned short
short f(short a) { return a+1; }
int main(void) { HALF u=65535; short c=32768; u=u+1; if(!u && c<0) return f(41); return 0; }

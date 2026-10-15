int main(void) { int x=1; { int y=x; int x=2; x=y+3; } return x; }

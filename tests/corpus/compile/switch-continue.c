int main(void) { int x=0; for(int i=0;i<6;i++) { goto inside; switch(1) { inside: x+=7; continue; } } return x; }

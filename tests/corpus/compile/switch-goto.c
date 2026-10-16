int main(void) { int x=0; goto inside; switch(x=1) { inside: x=42; break; } return x; }

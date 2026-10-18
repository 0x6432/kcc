struct O { union { int x; unsigned y; }; }; struct O o; int main(void) { o.x=42; return o.x; }

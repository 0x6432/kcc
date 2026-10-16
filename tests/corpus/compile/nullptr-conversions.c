typeof(nullptr) pick(typeof(nullptr) n) { return 0; }
int main(typeof(void)) { typeof(nullptr) n=0; n=(void *)0; return pick(0)==n?42:1; }

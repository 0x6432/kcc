int main(void) { int *p=(1?nullptr:(0,nullptr)); _Bool b=nullptr; return p==nullptr && !b; }

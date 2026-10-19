int *f(void){return &(static int){1};}int main(void){int *p=&(static thread_local int){2};return *p+*f();}

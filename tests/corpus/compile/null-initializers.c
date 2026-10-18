static int *p; extern int *p=(int *)0; int (*f)(void)=(void *)0; int main(void){return p==0 && f==0 ? 0 : 1;}

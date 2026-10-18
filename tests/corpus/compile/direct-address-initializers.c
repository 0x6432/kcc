extern int external; int *p=&external; static int cell; int *q=&cell; int function(void){return 42;} int (*fp)(void)=function; char *text="hello";

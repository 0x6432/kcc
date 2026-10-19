struct S{int x,y;};int *p=&((struct S){.x=1,.y=2}).y;int main(void){int *a=(int[]){1,2,3};return a[1]+*p;}

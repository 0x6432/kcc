int a[2][3]; int *p=&a[1][2]; char *bytes=(char *)&a+sizeof a;
int *q=(int *)((char *)a+sizeof(int))+1;

int main(void){int *p=0;int n=0;again:p=&(int){p?*p+1:1};if(++n<3)goto again;return *p;}

int g,h;int *p=(&g==&h)?&g:&h;int *q=1?&g:(0,&h);int main(void){return p==q;}

struct P{int a,b,c;};struct R{struct P p;};int main(void){struct P q={1,2,3};struct R r={.p=q,.p.b=4};return r.p.c;}

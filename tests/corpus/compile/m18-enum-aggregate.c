enum E{A=1,B=3}; struct S{enum E x; int a[B];}; struct S s={A,{1,2,3}}; int main(void){return s.a[s.x];}

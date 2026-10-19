struct S{int a[3];long b;};struct S x={.a[1]=2,3,.b=4};int main(void){struct S y={.a={1,2},.b=3};return y.a[1];}

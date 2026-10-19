typedef char T[sizeof((int*){&(int){1}})];int main(void){T x={};return x[0];}

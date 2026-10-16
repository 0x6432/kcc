int main(void) { int a[2][3]; for(int i=0;i<2;i=i+1) for(int j=0;j<3;j=j+1) a[i][j]=i*3+j+4; return a[0][0]+a[1][2]+29; }

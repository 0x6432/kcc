int main(void) { typedef int number,*pointer,pair[2]; pair a; pointer p=&a[1]; *p=40; { typedef number other; other x=2; *p+=x; } return *p; }

struct S{char a; _Alignas(16) int b;}; struct S s[2]; int main(void){return sizeof(s)+_Alignof(struct S);}

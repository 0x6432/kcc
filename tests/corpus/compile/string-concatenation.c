char *text(void) { return "a" "\0" "b"; }
int main(void) { char *p=text(); if(p[1]!=0 || p[2]!=98) return 1; return p[0]-55; }

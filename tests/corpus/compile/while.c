int main(void) { int i=0; while(i<4 && (i=i+1)) { if(i==2) continue; if(i==3) break; } return i; }

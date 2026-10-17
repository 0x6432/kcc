extern int a[],rows[][3],(*callbacks[])(int);
extern typeof(a) captured;
int *early(void) { return a; }
extern int a[3];
int run(int x) { rows[1][2]=callbacks[0](x); return rows[1][2]+sizeof a; }

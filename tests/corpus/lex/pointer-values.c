#define PTR int *
PTR identity(PTR p) { PTR q=p; return (int *)q; }
int **two(int **p) { return p; }
_Bool truth(int *p) { return p; }
int choose(int *p, int *q) { return p && !q; }

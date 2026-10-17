extern int cell;
int cell,(*callback)(int);
extern typeof(cell) cell;
int cell;
static int add(int x) { return x+2; }
int run(int x) { callback=add; cell=callback(x); return cell; }

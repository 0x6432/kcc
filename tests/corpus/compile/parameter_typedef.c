typedef long T;
int f(int T,typeof(T) x,int (*cb)(char T,typeof(T) y),typeof(T) z) {
	typeof(T) v=T;
	{ typedef char T; T x=2; v+=x; }
	return v+x+z;
}
int (*g(int T))[sizeof(T)];
T restored(T x);

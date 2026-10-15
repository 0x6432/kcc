#define F() G
#define G() F
#define A F
#define PREFIX F(
F()()() A()() PREFIX )
#define LP (
F LP )
#define SELF() SELF()
SELF()

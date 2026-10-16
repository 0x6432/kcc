_Static_assert(sizeof(nullptr)==8,"size"); int f(void) { int a[sizeof(nullptr)]; return sizeof a; }

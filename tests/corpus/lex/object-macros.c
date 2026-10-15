#define TYPE int
#define NAME main
#define VALUE ALIAS
#define ALIAS 7
#define EMPTY
TYPE NAME(void) { EMPTY return VALUE; }
#undef ALIAS
#define ALIAS 3

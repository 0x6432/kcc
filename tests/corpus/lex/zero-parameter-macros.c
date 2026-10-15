#define TYPE() int
#define NAME() main
#define VALUE() 7
#define ALIAS VALUE
#define E()
TYPE() NAME()(void) { E() int VALUE=3; return VALUE+ALIAS(/**/); }

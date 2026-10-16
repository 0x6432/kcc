#define YES true
#if defined(true) || false
#error incorrect
#elif YES
bool value=false;
#endif
#undef YES
#define bool _Bool
#define CAT(a,b) a##b
bool x=CAT(tr,ue);

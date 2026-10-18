_Thread_local int value=3;
int f(void) { static _Thread_local int count; extern _Thread_local int value; return ++count+value; }

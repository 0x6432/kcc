struct N { struct N *next; int value; }; struct N n; int *p=&n.value; int main(void) { n.next=&n; *p=42; return n.next->value; }

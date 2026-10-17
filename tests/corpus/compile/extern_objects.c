extern int value,(*row)[];
extern int (*row)[3];
extern int (*callback)(int);
int run(int value) { return callback(value)+(*row)[2]; }
int read(void) { return value; }

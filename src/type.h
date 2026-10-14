#ifndef KCC_TYPE_H
#define KCC_TYPE_H

enum type_kind {
	type_kind_int,
};

struct type {
	enum type_kind kind;
};

extern const struct type type_int;

#endif

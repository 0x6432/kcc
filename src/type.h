#ifndef KCC_TYPE_H
#define KCC_TYPE_H

enum type_kind {
	type_kind_int,
	type_kind_function,
};

struct type {
	enum type_kind kind;
};

struct function_type {
	struct type type;
	const struct type *return_type;
};

extern const struct type type_int;
extern const struct function_type type_function_int_void;

#endif

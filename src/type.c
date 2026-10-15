#include "type.h"

const struct type type_int = { type_kind_int };

const struct function_type type_function_int_void = {
	.type = { type_kind_function },
	.return_type = &type_int,
};

CC = cc
CPPFLAGS = -Isrc
CFLAGS = -std=c11 -O2 -g -Wall -Wextra -Wpedantic -Werror
LDFLAGS =
LDLIBS =
FUZZ_CC = clang
FUZZ_SECONDS = 10
QBE = qbe

LEX_SOURCES = src/lex.c src/source.c src/diagnostic.c
PREPROCESS_SOURCES = $(LEX_SOURCES) src/preprocess.c src/arena.c
COMPILER_SOURCES = $(PREPROCESS_SOURCES) src/ast.c src/type.c src/parse.c src/sema.c src/consteval.c src/codegen.c
HEADERS = $(wildcard src/*.h)

.PHONY: all test test-codegen clean fuzz-lex fuzz-compile

all: build/kcc

build:
	mkdir -p build

build/kcc: src/main.c $(COMPILER_SOURCES) $(HEADERS) | build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/main.c $(COMPILER_SOURCES) $(LDFLAGS) $(LDLIBS) -o $@

build/test_support: tests/test_support.c src/source.c src/arena.c src/diagnostic.c src/source.h src/arena.h src/diagnostic.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_support.c src/source.c src/arena.c src/diagnostic.c $(LDFLAGS) $(LDLIBS) -o $@

build/test_source: tests/test_source.c src/source.c src/source.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_source.c src/source.c $(LDFLAGS) $(LDLIBS) -o $@

build/test_lex: tests/test_lex.c $(PREPROCESS_SOURCES) $(HEADERS) | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_lex.c $(PREPROCESS_SOURCES) $(LDFLAGS) $(LDLIBS) -o $@

build/test_pp_lex: tests/test_pp_lex.c $(LEX_SOURCES) $(HEADERS) | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_pp_lex.c $(LEX_SOURCES) $(LDFLAGS) $(LDLIBS) -o $@

build/test_preprocess: tests/test_preprocess.c $(PREPROCESS_SOURCES) $(HEADERS) | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_preprocess.c $(PREPROCESS_SOURCES) $(LDFLAGS) $(LDLIBS) -o $@

build/fuzz_lex: tests/fuzz_lex.c $(PREPROCESS_SOURCES) $(HEADERS) | build
	$(FUZZ_CC) $(CPPFLAGS) -std=c11 -O1 -g -Wall -Wextra -Wpedantic -Werror -fsanitize=fuzzer,address,undefined -fno-omit-frame-pointer tests/fuzz_lex.c $(PREPROCESS_SOURCES) -o $@

fuzz-lex: build/fuzz_lex
	mkdir -p build/corpus-lex build/fuzz-artifacts
	cp tests/corpus/lex/* build/corpus-lex/
	./build/fuzz_lex build/corpus-lex -max_total_time=$(FUZZ_SECONDS) -max_len=4096 -timeout=5 -rss_limit_mb=512 -artifact_prefix=build/fuzz-artifacts/

build/fuzz_compile: tests/fuzz_compile.c $(COMPILER_SOURCES) $(HEADERS) | build
	$(FUZZ_CC) $(CPPFLAGS) -std=c11 -O1 -g -Wall -Wextra -Wpedantic -Werror -fsanitize=fuzzer,address,undefined -fno-omit-frame-pointer tests/fuzz_compile.c $(COMPILER_SOURCES) -o $@

fuzz-compile: build/fuzz_compile
	mkdir -p build/corpus-compile build/fuzz-artifacts
	cp tests/corpus/compile/* build/corpus-compile/
	./build/fuzz_compile build/corpus-compile -max_total_time=$(FUZZ_SECONDS) -max_len=4096 -timeout=5 -rss_limit_mb=512 -artifact_prefix=build/fuzz-artifacts/

test-codegen: export QBE := $(QBE)
test-codegen: build/kcc build/pp_oracle build/consteval_oracle build/test_static_array_ast
	./build/test_static_array_ast
	QBE="$(QBE)" python3 tests/test_compile.py
	QBE="$(QBE)" python3 tests/test_abi.py
	QBE="$(QBE)" python3 tests/test_diagnostics.py
	QBE="$(QBE)" python3 tests/test_conditions.py
	QBE="$(QBE)" python3 tests/test_condition_expressions.py
	QBE="$(QBE)" python3 tests/test_condition_literals.py
	QBE="$(QBE)" python3 tests/test_unsigned_conditions.py
	QBE="$(QBE)" python3 tests/test_character_conditions.py
	QBE="$(QBE)" python3 tests/test_includes.py
	QBE="$(QBE)" python3 tests/test_computed_includes.py
	QBE="$(QBE)" python3 tests/test_include_search.py
	QBE="$(QBE)" python3 tests/test_integer_operators.py
	QBE="$(QBE)" python3 tests/test_integer_spellings.py
	QBE="$(QBE)" python3 tests/test_unsigned_runtime.py
	QBE="$(QBE)" python3 tests/test_unsigned_abi.py
	QBE="$(QBE)" python3 tests/test_integer_casts.py
	QBE="$(QBE)" python3 tests/test_long_runtime.py
	QBE="$(QBE)" python3 tests/test_long_abi.py
	QBE="$(QBE)" python3 tests/test_long_long.py
	QBE="$(QBE)" python3 tests/test_character_runtime.py
	QBE="$(QBE)" python3 tests/test_char_types.py
	QBE="$(QBE)" python3 tests/test_char_abi.py
	QBE="$(QBE)" python3 tests/test_short_types.py
	QBE="$(QBE)" python3 tests/test_short_abi.py
	QBE="$(QBE)" python3 tests/test_bool_type.py
	QBE="$(QBE)" python3 tests/test_bool_abi.py
	QBE="$(QBE)" python3 tests/test_pointer_values.py
	QBE="$(QBE)" python3 tests/test_pointer_lvalues.py
	QBE="$(QBE)" python3 tests/test_pointer_equality.py
	QBE="$(QBE)" python3 tests/test_pointer_arithmetic.py
	QBE="$(QBE)" python3 tests/test_pointer_subscripts.py
	QBE="$(QBE)" python3 tests/test_local_arrays.py
	QBE="$(QBE)" python3 tests/test_multidimensional_arrays.py
	QBE="$(QBE)" python3 tests/test_string_literals.py
	QBE="$(QBE)" python3 tests/test_string_concatenation.py
	QBE="$(QBE)" python3 tests/test_array_parameters.py
	QBE="$(QBE)" python3 tests/test_incomplete_parameter_bounds.py
	QBE="$(QBE)" python3 tests/test_object_declarators.py
	QBE="$(QBE)" python3 tests/test_incomplete_object_pointers.py
	QBE="$(QBE)" python3 tests/test_local_declaration_lists.py
	QBE="$(QBE)" python3 tests/test_unnamed_definition_parameters.py
	QBE="$(QBE)" python3 tests/test_function_declarators.py
	QBE="$(QBE)" python3 tests/test_function_pointers.py
	QBE="$(QBE)" python3 tests/test_void_functions.py
	QBE="$(QBE)" python3 tests/test_object_void_conversions.py
	QBE="$(QBE)" python3 tests/test_explicit_pointer_casts.py
	QBE="$(QBE)" python3 tests/test_comma_expressions.py
	QBE="$(QBE)" python3 tests/test_const_qualification.py
	QBE="$(QBE)" python3 tests/test_boolean_keywords.py
	QBE="$(QBE)" python3 tests/test_conditional_expressions.py
	QBE="$(QBE)" python3 tests/test_sizeof_alignment.py
	python3 tests/test_constant_array_bounds.py
	python3 tests/test_null_pointer_constants.py
	python3 tests/test_nullptr.py
	python3 tests/test_prefix_updates.py
	python3 tests/test_postfix_updates.py
	python3 tests/test_additive_assignment.py
	python3 tests/test_integer_compound_assignment.py
	python3 tests/test_named_labels.py
	python3 tests/test_goto.py
	python3 tests/test_switch_foundation.py
	python3 tests/test_switch_cases.py
	python3 tests/test_typeof_types.py
	python3 tests/test_typeof_expressions.py
	python3 tests/test_void_parameter_queries.py
	python3 tests/test_nullptr_conversions.py
	python3 tests/test_queried_function_declarations.py
	python3 tests/test_typedef_foundation.py
	python3 tests/test_typedef_redeclarations.py
	python3 tests/test_typedef_declaration_lists.py
	python3 tests/test_block_typedefs.py
	python3 tests/test_for_typedefs.py
	python3 tests/test_typedef_shadowing.py
	python3 tests/test_typedef_function_shadowing.py
	python3 tests/test_typedef_object_shadowing.py
	python3 tests/test_object_typedef_shadowing.py
	python3 tests/test_parameter_typedef_shadowing.py
	python3 tests/test_typedef_specifier_placement.py
	python3 tests/test_register_scalars.py
	python3 tests/test_register_arrays.py
	python3 tests/test_register_parameters.py
	python3 tests/test_extern_functions.py
	python3 tests/test_extern_objects.py
	python3 tests/test_extern_arrays.py
	python3 tests/test_tentative_scalars.py
	python3 tests/test_tentative_arrays.py
	python3 tests/test_static_functions.py
	python3 tests/test_static_objects.py
	python3 tests/test_static_arrays.py
	python3 tests/test_function_declaration_lists.py
	python3 tests/test_auto_explicit.py
	python3 tests/test_local_binding_phases.py
	python3 tests/test_auto_inference.py
	python3 tests/test_register_auto_inference.py
	python3 tests/test_inferred_typedef_shadowing.py
	python3 tests/test_static_assertions.py
	python3 tests/test_consteval.py

build/consteval_oracle: tests/consteval_oracle.c $(COMPILER_SOURCES) $(HEADERS) | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/consteval_oracle.c $(COMPILER_SOURCES) $(LDFLAGS) $(LDLIBS) -o $@

build/test_type: tests/test_type.c src/type.c src/arena.c src/type.h src/arena.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_type.c src/type.c src/arena.c $(LDFLAGS) $(LDLIBS) -o $@

build/test_sema: tests/test_sema.c $(COMPILER_SOURCES) $(HEADERS) | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_sema.c $(COMPILER_SOURCES) $(LDFLAGS) $(LDLIBS) -o $@

build/test_static_array_ast: tests/test_static_array_ast.c $(COMPILER_SOURCES) $(HEADERS) | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_static_array_ast.c $(COMPILER_SOURCES) $(LDFLAGS) $(LDLIBS) -o $@

build/pp_oracle: tests/pp_oracle.c $(PREPROCESS_SOURCES) $(HEADERS) | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/pp_oracle.c $(PREPROCESS_SOURCES) $(LDFLAGS) $(LDLIBS) -o $@

test: build/pp_oracle build/kcc build/test_support build/test_source build/test_lex build/test_pp_lex build/test_preprocess build/test_type build/test_sema build/consteval_oracle build/test_static_array_ast
	python3 tests/test_cli.py
	./build/test_support
	./build/test_source
	./build/test_lex
	./build/test_pp_lex
	./build/test_preprocess
	python3 tests/test_macros.py
	./build/test_type
	./build/test_sema
	./build/test_static_array_ast
	python3 tests/test_compile.py
	python3 tests/test_diagnostics.py
	python3 tests/test_conditions.py
	python3 tests/test_condition_expressions.py
	python3 tests/test_condition_literals.py
	python3 tests/test_unsigned_conditions.py
	python3 tests/test_character_conditions.py
	python3 tests/test_includes.py
	python3 tests/test_computed_includes.py
	python3 tests/test_include_search.py
	python3 tests/test_integer_operators.py
	python3 tests/test_integer_spellings.py
	python3 tests/test_unsigned_runtime.py
	python3 tests/test_unsigned_abi.py
	python3 tests/test_integer_casts.py
	python3 tests/test_long_runtime.py
	python3 tests/test_long_abi.py
	python3 tests/test_long_long.py
	python3 tests/test_character_runtime.py
	python3 tests/test_char_types.py
	python3 tests/test_char_abi.py
	python3 tests/test_short_types.py
	python3 tests/test_short_abi.py
	python3 tests/test_bool_type.py
	python3 tests/test_bool_abi.py
	python3 tests/test_pointer_values.py
	python3 tests/test_pointer_lvalues.py
	python3 tests/test_pointer_equality.py
	python3 tests/test_pointer_arithmetic.py
	python3 tests/test_pointer_subscripts.py
	python3 tests/test_local_arrays.py
	python3 tests/test_multidimensional_arrays.py
	python3 tests/test_string_literals.py
	python3 tests/test_string_concatenation.py
	python3 tests/test_array_parameters.py
	python3 tests/test_incomplete_parameter_bounds.py
	python3 tests/test_object_declarators.py
	python3 tests/test_incomplete_object_pointers.py
	python3 tests/test_local_declaration_lists.py
	python3 tests/test_unnamed_definition_parameters.py
	python3 tests/test_function_declarators.py
	python3 tests/test_function_pointers.py
	python3 tests/test_void_functions.py
	python3 tests/test_object_void_conversions.py
	python3 tests/test_explicit_pointer_casts.py
	python3 tests/test_comma_expressions.py
	python3 tests/test_const_qualification.py
	python3 tests/test_boolean_keywords.py
	python3 tests/test_conditional_expressions.py
	python3 tests/test_sizeof_alignment.py
	python3 tests/test_constant_array_bounds.py
	python3 tests/test_null_pointer_constants.py
	python3 tests/test_nullptr.py
	python3 tests/test_prefix_updates.py
	python3 tests/test_postfix_updates.py
	python3 tests/test_additive_assignment.py
	python3 tests/test_integer_compound_assignment.py
	python3 tests/test_named_labels.py
	python3 tests/test_goto.py
	python3 tests/test_switch_foundation.py
	python3 tests/test_switch_cases.py
	python3 tests/test_typeof_types.py
	python3 tests/test_typeof_expressions.py
	python3 tests/test_void_parameter_queries.py
	python3 tests/test_nullptr_conversions.py
	python3 tests/test_queried_function_declarations.py
	python3 tests/test_typedef_foundation.py
	python3 tests/test_typedef_redeclarations.py
	python3 tests/test_typedef_declaration_lists.py
	python3 tests/test_block_typedefs.py
	python3 tests/test_for_typedefs.py
	python3 tests/test_typedef_shadowing.py
	python3 tests/test_typedef_function_shadowing.py
	python3 tests/test_typedef_object_shadowing.py
	python3 tests/test_object_typedef_shadowing.py
	python3 tests/test_parameter_typedef_shadowing.py
	python3 tests/test_typedef_specifier_placement.py
	python3 tests/test_register_scalars.py
	python3 tests/test_register_arrays.py
	python3 tests/test_register_parameters.py
	python3 tests/test_extern_functions.py
	python3 tests/test_extern_objects.py
	python3 tests/test_extern_arrays.py
	python3 tests/test_tentative_scalars.py
	python3 tests/test_tentative_arrays.py
	python3 tests/test_static_functions.py
	python3 tests/test_static_objects.py
	python3 tests/test_static_arrays.py
	python3 tests/test_function_declaration_lists.py
	python3 tests/test_auto_explicit.py
	python3 tests/test_local_binding_phases.py
	python3 tests/test_auto_inference.py
	python3 tests/test_register_auto_inference.py
	python3 tests/test_inferred_typedef_shadowing.py
	python3 tests/test_static_assertions.py
	python3 tests/test_consteval.py

clean:
	rm -rf build

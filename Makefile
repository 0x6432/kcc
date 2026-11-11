CC = cc
CPPFLAGS = -Isrc
CFLAGS = -std=c11 -O2 -g -Wall -Wextra -Wpedantic -Werror
LDFLAGS =
LDLIBS =
FUZZ_CC = clang
FUZZ_SECONDS = 10
QBE = qbe
CLANG = clang
.DEFAULT_GOAL := all

LEX_SOURCES = src/lex.c src/source.c src/diagnostic.c
PREPROCESS_SOURCES = $(LEX_SOURCES) src/preprocess.c src/arena.c
COMPILER_SOURCES = $(PREPROCESS_SOURCES) src/bitint.c src/ast.c src/type.c src/parse.c src/sema.c src/consteval.c src/codegen.c
HEADERS = $(wildcard src/*.h)

.PHONY: all test test-codegen test-bitint-native clean fuzz-lex fuzz-compile FORCE
.DELETE_ON_ERROR:

# A forced check updates each stamp only when its command-line configuration
# changes. This avoids reusing objects or executables built with different flags.
# Shell-quote values so flags containing spaces or quotes are recorded faithfully.
shell_quote = '$(subst ','"'"',$(1))'

FORCE:

build/compile.flags: FORCE | build
	@printf '%s\n' $(call shell_quote,$(CC)) $(call shell_quote,$(CPPFLAGS)) $(call shell_quote,$(CFLAGS)) > $@.tmp
	@cmp -s $@.tmp $@ && rm -f $@.tmp || mv -f $@.tmp $@

build/fuzz.flags: FORCE | build
	@printf '%s\n' $(call shell_quote,$(FUZZ_CC)) $(call shell_quote,$(CPPFLAGS)) > $@.tmp
	@cmp -s $@.tmp $@ && rm -f $@.tmp || mv -f $@.tmp $@

build/link.flags: FORCE | build
	@printf '%s\n' $(call shell_quote,$(CC)) $(call shell_quote,$(CPPFLAGS)) $(call shell_quote,$(CFLAGS)) $(call shell_quote,$(LDFLAGS)) $(call shell_quote,$(LDLIBS)) > $@.tmp
	@cmp -s $@.tmp $@ && rm -f $@.tmp || mv -f $@.tmp $@

# Keep paths in object names distinct, and record transitive header dependencies.
# A missing dependency file forces its object to be compiled again.
.SECONDEXPANSION:
build/obj/%.o: %.c build/compile.flags Makefile $$(if $$(wildcard build/obj/$$*.d),,FORCE)
	@mkdir -p $(@D)
	$(CC) $(CPPFLAGS) $(CFLAGS) -MD -MP -MF $(@:.o=.d) -MT $@ -c $< -o $@

-include $(wildcard build/obj/src/*.d build/obj/tests/*.d build/*.d)

all: build/kcc build/libkccrt.a

build:
	mkdir -p build

build/kcc: $(patsubst %.c,build/obj/%.o,src/main.c $(COMPILER_SOURCES)) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/volatile.o: runtime/volatile.c build/compile.flags Makefile $(if $(wildcard build/volatile.d),,FORCE) | build
	$(CC) $(CFLAGS) -fno-strict-aliasing -fno-lto -MD -MP -MF $(@:.o=.d) -MT $@ -c $< -o $@

build/checked.o: runtime/checked.c build/compile.flags Makefile $(if $(wildcard build/checked.d),,FORCE) | build
	$(CC) $(CFLAGS) -fno-strict-aliasing -fno-lto -MD -MP -MF $(@:.o=.d) -MT $@ -c $< -o $@

build/memset_explicit.o: runtime/memset_explicit.c build/compile.flags Makefile $(if $(wildcard build/memset_explicit.d),,FORCE) | build
	$(CC) $(CFLAGS) -fno-lto -fno-builtin -MD -MP -MF $(@:.o=.d) -MT $@ -c $< -o $@

build/free_sized.o: runtime/free_sized.c build/compile.flags Makefile $(if $(wildcard build/free_sized.d),,FORCE) | build
	$(CC) $(CFLAGS) -fno-lto -MD -MP -MF $(@:.o=.d) -MT $@ -c $< -o $@

build/unreachable.o: runtime/unreachable.c build/compile.flags Makefile $(if $(wildcard build/unreachable.d),,FORCE) | build
	$(CC) $(CFLAGS) -fno-lto -MD -MP -MF $(@:.o=.d) -MT $@ -c $< -o $@

build/math_compare.o: runtime/math_compare.c build/compile.flags Makefile $(if $(wildcard build/math_compare.d),,FORCE) | build
	$(CC) $(CFLAGS) -fno-fast-math -fno-lto -MD -MP -MF $(@:.o=.d) -MT $@ -c $< -o $@

build/libkccrt.a: build/math_compare.o build/volatile.o build/checked.o build/memset_explicit.o build/free_sized.o build/unreachable.o
	ar rcs $@ $^

build/test_support: $(patsubst %.c,build/obj/%.o,tests/test_support.c src/source.c src/arena.c src/diagnostic.c) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/test_source: $(patsubst %.c,build/obj/%.o,tests/test_source.c src/source.c) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/test_lex: $(patsubst %.c,build/obj/%.o,tests/test_lex.c $(PREPROCESS_SOURCES)) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/test_pp_lex: $(patsubst %.c,build/obj/%.o,tests/test_pp_lex.c $(LEX_SOURCES)) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/test_preprocess: $(patsubst %.c,build/obj/%.o,tests/test_preprocess.c $(PREPROCESS_SOURCES)) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/fuzz_lex: tests/fuzz_lex.c $(PREPROCESS_SOURCES) $(HEADERS) build/fuzz.flags Makefile | build
	$(FUZZ_CC) $(CPPFLAGS) -std=c11 -O1 -g -Wall -Wextra -Wpedantic -Werror -fsanitize=fuzzer,address,undefined -fno-omit-frame-pointer tests/fuzz_lex.c $(PREPROCESS_SOURCES) -o $@

fuzz-lex: build/fuzz_lex
	mkdir -p build/corpus-lex build/fuzz-artifacts
	cp tests/corpus/lex/* build/corpus-lex/
	./build/fuzz_lex build/corpus-lex -max_total_time=$(FUZZ_SECONDS) -max_len=4096 -timeout=5 -rss_limit_mb=512 -artifact_prefix=build/fuzz-artifacts/

build/fuzz_compile: tests/fuzz_compile.c $(COMPILER_SOURCES) $(HEADERS) build/fuzz.flags Makefile | build
	$(FUZZ_CC) $(CPPFLAGS) -std=c11 -O1 -g -Wall -Wextra -Wpedantic -Werror -fsanitize=fuzzer,address,undefined -fno-omit-frame-pointer tests/fuzz_compile.c $(COMPILER_SOURCES) -o $@

fuzz-compile: build/fuzz_compile
	mkdir -p build/corpus-compile build/fuzz-artifacts
	cp tests/corpus/compile/* build/corpus-compile/
	./build/fuzz_compile build/corpus-compile -max_total_time=$(FUZZ_SECONDS) -max_len=4096 -timeout=5 -rss_limit_mb=512 -artifact_prefix=build/fuzz-artifacts/

# Explicit native oracle: requires Clang with C2x _BitInt and x86-64 SysV QBE.
test-bitint-native: export KCC_RUNTIME_LDFLAGS := $(LDFLAGS)
test-bitint-native: build/kcc build/libkccrt.a
	QBE="$(QBE)" CLANG="$(CLANG)" python3 tests/test_bitint_fields_native.py
	QBE="$(QBE)" CLANG="$(CLANG)" python3 tests/test_bitint_aggregate_native.py
	QBE="$(QBE)" CLANG="$(CLANG)" python3 tests/test_bitint_variadic_native.py
	QBE="$(QBE)" CLANG="$(CLANG)" python3 tests/test_bitint_arbitrary.py
	QBE="$(QBE)" CLANG="$(CLANG)" python3 tests/test_bitint_conversions_native.py
	QBE="$(QBE)" CLANG="$(CLANG)" python3 tests/test_bitint_arithmetic_native.py
	CLANG="$(CLANG)" python3 tests/test_bitint_type_oracle.py

test-codegen: export QBE := $(QBE)
test-codegen: export KCC_SOURCE := $(CURDIR)
test-codegen: export KCC_RUNTIME_LDFLAGS := $(LDFLAGS)
test-codegen: build/kcc build/libkccrt.a build/pp_oracle build/consteval_oracle build/test_static_array_ast build/test_integer_initializer_ast build/test_null_initializer_ast build/test_direct_address_initializer_ast build/test_block_storage_ast build/test_thread_storage_ast build/test_inline_linkage_ast build/test_address_offset_ast build/test_record_layout_ast build/test_record_runtime_ast build/test_initialization_ast build/test_compound_literal_ast
	./build/test_static_array_ast
	./build/test_integer_initializer_ast
	./build/test_null_initializer_ast
	./build/test_direct_address_initializer_ast
	./build/test_block_storage_ast
	./build/test_thread_storage_ast
	./build/test_inline_linkage_ast
	./build/test_address_offset_ast
	./build/test_record_layout_ast
	./build/test_record_runtime_ast
	./build/test_initialization_ast
	./build/test_compound_literal_ast
	QBE="$(QBE)" python3 tests/test_float_foundation.py
	QBE="$(QBE)" python3 tests/test_compile.py
	QBE="$(QBE)" python3 tests/test_abi.py
	QBE="$(QBE)" python3 tests/test_aggregate_abi.py
	QBE="$(QBE)" python3 tests/test_aggregate_varargs.py
	QBE="$(QBE)" python3 tests/test_bitint_values.py
	QBE="$(QBE)" python3 tests/test_bitint_atomic_non_native.py
	QBE="$(QBE)" python3 tests/test_bitint_variadic.py
	QBE="$(QBE)" python3 tests/test_bitint_abi_atomics.py
	QBE="$(QBE)" python3 tests/test_bitint_literals.py
	QBE="$(QBE)" python3 tests/test_bitint_layout.py
	QBE="$(QBE)" python3 tests/test_variadic.py
	QBE="$(QBE)" python3 tests/test_builtin_headers.py
	QBE="$(QBE)" python3 tests/test_hosted_numeric.py
	QBE="$(QBE)" python3 tests/test_wide_library_declarations.py
	QBE="$(QBE)" python3 tests/test_embed.py
	QBE="$(QBE)" python3 tests/test_generic_selection.py
	QBE="$(QBE)" python3 tests/test_function_name.py
	QBE="$(QBE)" python3 tests/test_flexible_array.py
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
	QBE="$(QBE)" python3 tests/test_vla_outer.py
	QBE="$(QBE)" python3 tests/test_vla_pointer.py
	QBE="$(QBE)" python3 tests/test_vla_pointer_updates.py
	QBE="$(QBE)" python3 tests/test_multidimensional_arrays.py
	QBE="$(QBE)" python3 tests/test_string_literals.py
	QBE="$(QBE)" python3 tests/test_utf8_strings.py
	QBE="$(QBE)" python3 tests/test_wide_strings.py
	QBE="$(QBE)" python3 tests/test_stdbit.py
	QBE="$(QBE)" python3 tests/test_integer_pointer_casts.py
	QBE="$(QBE)" python3 tests/test_signal_header.py
	QBE="$(QBE)" python3 tests/test_fenv_header.py
	QBE="$(QBE)" python3 tests/test_threads_header.py
	QBE="$(QBE)" python3 tests/test_stdckdint_header.py
	QBE="$(QBE)" python3 tests/test_memset_explicit.py
	QBE="$(QBE)" python3 tests/test_free_sized.py
	QBE="$(QBE)" python3 tests/test_math_extended.py
	QBE="$(QBE)" python3 tests/test_header_budgets.py
	QBE="$(QBE)" python3 tests/test_unreachable.py
	QBE="$(QBE)" python3 tests/test_pragma_operator.py
	QBE="$(QBE)" python3 tests/test_volatile.py
	QBE="$(QBE)" python3 tests/test_string_concatenation.py
	QBE="$(QBE)" python3 tests/test_array_parameters.py
	QBE="$(QBE)" python3 tests/test_qualified_array_parameters.py
	QBE="$(QBE)" python3 tests/test_restrict.py
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
	QBE="$(QBE)" python3 tests/test_atomic_subset.py
	QBE="$(QBE)" python3 tests/test_boolean_keywords.py
	QBE="$(QBE)" python3 tests/test_conditional_expressions.py
	QBE="$(QBE)" python3 tests/test_sizeof_alignment.py
	QBE="$(QBE)" python3 tests/test_declaration_alignment.py
	QBE="$(QBE)" python3 tests/test_attributes.py
	QBE="$(QBE)" python3 tests/test_alignment_storage_records.py
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
	python3 tests/test_integer_initializers.py
	python3 tests/test_null_initializers.py
	python3 tests/test_direct_address_initializers.py
	python3 tests/test_block_storage.py
	python3 tests/test_thread_storage.py
	python3 tests/test_inline_linkage.py
	python3 tests/test_address_offsets.py
	python3 tests/test_storage_promotions.py
	python3 tests/test_enum_runtime.py
	python3 tests/test_ordinary_enum_wide.py
	python3 tests/test_enum_successor_types.py
	python3 tests/test_enum_compatibility.py
	python3 tests/test_enum_parameters.py
	python3 tests/test_fixed_enum_runtime.py
	python3 tests/test_boolean_enum.py
	python3 tests/test_record_promotions.py
	python3 tests/test_record_layout.py
	python3 tests/test_bit_fields.py
	python3 tests/test_bool_bit_fields.py
	python3 tests/test_char_bit_fields.py
	python3 tests/test_short_bit_fields.py
	python3 tests/test_legacy_clang_abi_warning.py
	python3 tests/test_legacy_clang_abi.py
	python3 tests/test_long_bit_fields.py
	python3 tests/test_named_wide_bit_fields.py
	python3 tests/test_wide_bit_field_ops.py
	python3 tests/test_unnamed_wide_bit_fields.py
	python3 tests/test_enum_bit_fields.py
	python3 tests/test_enum_extended_underlying.py
	python3 tests/test_narrow_bit_fields.py
	python3 tests/test_narrow_field_expressions.py
	python3 tests/test_packed_bit_fields.py
	python3 tests/test_bitfield_aggregate_abi.py
	python3 tests/test_unnamed_field_aggregate_abi.py
	python3 tests/test_unnamed_bit_fields.py
	python3 tests/test_zero_width_memory_abi.py
	python3 tests/test_zero_width_integer_abi.py
	python3 tests/test_zero_width_aligned_float_abi.py
	python3 tests/test_zero_width_legacy_float_abi.py
	python3 tests/test_zero_width_gcc12_abi.py
	python3 tests/test_record_runtime.py --frozen-hash "$$(git rev-parse HEAD)"
	python3 tests/test_initialization_promotions.py
	python3 tests/test_initialization.py --frozen-hash "$$(git rev-parse HEAD)"
	python3 tests/test_compound_literals.py --frozen-hash "$$(git rev-parse HEAD)"
	python3 tests/test_function_declaration_lists.py
	python3 tests/test_auto_explicit.py
	python3 tests/test_local_binding_phases.py
	python3 tests/test_auto_inference.py
	python3 tests/test_constexpr_integer.py
	python3 tests/test_constexpr_pointers.py
	python3 tests/test_constexpr_floating.py
	python3 tests/test_constexpr_aggregates.py
	python3 tests/test_constexpr_literals.py
	python3 tests/test_register_auto_inference.py
	python3 tests/test_inferred_typedef_shadowing.py
	python3 tests/test_static_assertions.py
	python3 tests/test_consteval.py

build/consteval_oracle: $(patsubst %.c,build/obj/%.o,tests/consteval_oracle.c $(COMPILER_SOURCES)) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/test_bitint: $(patsubst %.c,build/obj/%.o,tests/test_bitint.c src/bitint.c) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/test_type: $(patsubst %.c,build/obj/%.o,tests/test_type.c src/type.c src/arena.c) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/test_sema: $(patsubst %.c,build/obj/%.o,tests/test_sema.c $(COMPILER_SOURCES)) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/test_static_array_ast: $(patsubst %.c,build/obj/%.o,tests/test_static_array_ast.c $(COMPILER_SOURCES)) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/test_integer_initializer_ast: $(patsubst %.c,build/obj/%.o,tests/test_integer_initializer_ast.c $(COMPILER_SOURCES)) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/test_null_initializer_ast: $(patsubst %.c,build/obj/%.o,tests/test_null_initializer_ast.c $(COMPILER_SOURCES)) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/test_direct_address_initializer_ast: $(patsubst %.c,build/obj/%.o,tests/test_direct_address_initializer_ast.c $(COMPILER_SOURCES)) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/pp_oracle: $(patsubst %.c,build/obj/%.o,tests/pp_oracle.c $(PREPROCESS_SOURCES)) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

test: export QBE := $(QBE)
test: export KCC_SOURCE := $(CURDIR)
test: export KCC_RUNTIME_LDFLAGS := $(LDFLAGS)
test: build/test_bitint build/pp_oracle build/kcc build/libkccrt.a build/test_support build/test_source build/test_lex build/test_pp_lex build/test_preprocess build/test_type build/test_sema build/consteval_oracle build/test_static_array_ast build/test_integer_initializer_ast build/test_null_initializer_ast build/test_direct_address_initializer_ast build/test_block_storage_ast build/test_thread_storage_ast build/test_inline_linkage_ast build/test_address_offset_ast build/test_record_layout_ast build/test_record_runtime_ast build/test_initialization_ast build/test_compound_literal_ast
	python3 tests/test_cli.py
	./build/test_support
	./build/test_source
	./build/test_lex
	./build/test_pp_lex
	./build/test_preprocess
	python3 tests/test_macros.py
	./build/test_bitint
	python3 tests/test_bitint_rejection.py
	QBE="$(QBE)" python3 tests/test_bitint_values.py
	QBE="$(QBE)" python3 tests/test_bitint_atomic_non_native.py
	QBE="$(QBE)" python3 tests/test_bitint_variadic.py
	QBE="$(QBE)" python3 tests/test_bitint_abi_atomics.py
	QBE="$(QBE)" python3 tests/test_bitint_literals.py
	QBE="$(QBE)" python3 tests/test_bitint_layout.py
	./build/test_type
	./build/test_sema
	./build/test_static_array_ast
	./build/test_integer_initializer_ast
	./build/test_null_initializer_ast
	./build/test_direct_address_initializer_ast
	./build/test_block_storage_ast
	./build/test_thread_storage_ast
	./build/test_inline_linkage_ast
	./build/test_address_offset_ast
	./build/test_record_layout_ast
	./build/test_record_runtime_ast
	./build/test_initialization_ast
	./build/test_compound_literal_ast
	python3 tests/test_float_foundation.py
	python3 tests/test_compile.py
	QBE="$(QBE)" python3 tests/test_abi.py
	python3 tests/test_diagnostics.py
	QBE="$(QBE)" python3 tests/test_aggregate_abi.py
	QBE="$(QBE)" python3 tests/test_aggregate_varargs.py
	python3 tests/test_variadic.py
	python3 tests/test_builtin_headers.py
	python3 tests/test_hosted_numeric.py
	python3 tests/test_wide_library_declarations.py
	python3 tests/test_embed.py
	python3 tests/test_generic_selection.py
	python3 tests/test_function_name.py
	python3 tests/test_flexible_array.py
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
	python3 tests/test_vla_outer.py
	python3 tests/test_vla_pointer.py
	python3 tests/test_vla_pointer_updates.py
	python3 tests/test_multidimensional_arrays.py
	python3 tests/test_string_literals.py
	python3 tests/test_utf8_strings.py
	python3 tests/test_wide_strings.py
	python3 tests/test_stdbit.py
	python3 tests/test_integer_pointer_casts.py
	python3 tests/test_signal_header.py
	python3 tests/test_fenv_header.py
	python3 tests/test_threads_header.py
	python3 tests/test_stdckdint_header.py
	python3 tests/test_memset_explicit.py
	python3 tests/test_free_sized.py
	python3 tests/test_math_extended.py
	python3 tests/test_header_budgets.py
	python3 tests/test_unreachable.py
	python3 tests/test_pragma_operator.py
	python3 tests/test_volatile.py
	python3 tests/test_string_concatenation.py
	python3 tests/test_array_parameters.py
	python3 tests/test_qualified_array_parameters.py
	python3 tests/test_restrict.py
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
	python3 tests/test_atomic_subset.py
	python3 tests/test_boolean_keywords.py
	python3 tests/test_conditional_expressions.py
	python3 tests/test_sizeof_alignment.py
	python3 tests/test_declaration_alignment.py
	python3 tests/test_attributes.py
	python3 tests/test_alignment_storage_records.py
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
	python3 tests/test_integer_initializers.py
	python3 tests/test_null_initializers.py
	python3 tests/test_direct_address_initializers.py
	python3 tests/test_block_storage.py
	python3 tests/test_thread_storage.py
	python3 tests/test_inline_linkage.py
	python3 tests/test_address_offsets.py
	python3 tests/test_storage_promotions.py
	python3 tests/test_enum_runtime.py
	python3 tests/test_ordinary_enum_wide.py
	python3 tests/test_enum_successor_types.py
	python3 tests/test_enum_compatibility.py
	python3 tests/test_enum_parameters.py
	python3 tests/test_fixed_enum_runtime.py
	python3 tests/test_boolean_enum.py
	python3 tests/test_record_promotions.py
	python3 tests/test_record_layout.py
	python3 tests/test_bit_fields.py
	python3 tests/test_bool_bit_fields.py
	python3 tests/test_char_bit_fields.py
	python3 tests/test_short_bit_fields.py
	python3 tests/test_legacy_clang_abi_warning.py
	python3 tests/test_legacy_clang_abi.py
	python3 tests/test_long_bit_fields.py
	python3 tests/test_named_wide_bit_fields.py
	python3 tests/test_wide_bit_field_ops.py
	python3 tests/test_unnamed_wide_bit_fields.py
	python3 tests/test_enum_bit_fields.py
	python3 tests/test_enum_extended_underlying.py
	python3 tests/test_narrow_bit_fields.py
	python3 tests/test_narrow_field_expressions.py
	python3 tests/test_packed_bit_fields.py
	python3 tests/test_bitfield_aggregate_abi.py
	python3 tests/test_unnamed_field_aggregate_abi.py
	python3 tests/test_unnamed_bit_fields.py
	python3 tests/test_zero_width_memory_abi.py
	python3 tests/test_zero_width_integer_abi.py
	python3 tests/test_zero_width_aligned_float_abi.py
	python3 tests/test_zero_width_legacy_float_abi.py
	python3 tests/test_zero_width_gcc12_abi.py
	python3 tests/test_record_runtime.py --frozen-hash "$$(git rev-parse HEAD)"
	python3 tests/test_initialization_promotions.py
	python3 tests/test_initialization.py --frozen-hash "$$(git rev-parse HEAD)"
	python3 tests/test_compound_literals.py --frozen-hash "$$(git rev-parse HEAD)"
	python3 tests/test_function_declaration_lists.py
	python3 tests/test_auto_explicit.py
	python3 tests/test_local_binding_phases.py
	python3 tests/test_auto_inference.py
	python3 tests/test_constexpr_integer.py
	python3 tests/test_constexpr_pointers.py
	python3 tests/test_constexpr_floating.py
	python3 tests/test_constexpr_aggregates.py
	python3 tests/test_constexpr_literals.py
	python3 tests/test_register_auto_inference.py
	python3 tests/test_inferred_typedef_shadowing.py
	python3 tests/test_static_assertions.py
	python3 tests/test_consteval.py

clean:
	rm -rf build

build/test_block_storage_ast: $(patsubst %.c,build/obj/%.o,tests/test_block_storage_ast.c $(COMPILER_SOURCES)) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/test_thread_storage_ast: $(patsubst %.c,build/obj/%.o,tests/test_thread_storage_ast.c $(COMPILER_SOURCES)) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/test_inline_linkage_ast: $(patsubst %.c,build/obj/%.o,tests/test_inline_linkage_ast.c $(COMPILER_SOURCES)) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/test_address_offset_ast: $(patsubst %.c,build/obj/%.o,tests/test_address_offset_ast.c $(COMPILER_SOURCES)) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/test_record_layout_ast: $(patsubst %.c,build/obj/%.o,tests/test_record_layout_ast.c $(COMPILER_SOURCES)) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/test_record_runtime_ast: $(patsubst %.c,build/obj/%.o,tests/test_record_runtime_ast.c $(COMPILER_SOURCES)) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/test_initialization_ast: $(patsubst %.c,build/obj/%.o,tests/test_initialization_ast.c $(COMPILER_SOURCES)) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

build/test_compound_literal_ast: $(patsubst %.c,build/obj/%.o,tests/test_compound_literal_ast.c $(COMPILER_SOURCES)) build/link.flags Makefile | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.o,$^) $(LDFLAGS) $(LDLIBS) -o $@

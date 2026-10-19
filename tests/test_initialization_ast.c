/* Independent M17 syntax/plan/canonical-publication oracle.
 * Compile with selected frozen checkout source C files except main.c. No Makefile edits.
 * This suite never reads unspecified nonempty aggregate padding.
 */
#include "parse.h"
#include "sema.h"
#include "consteval.h"
#include "type.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct fixture {
	struct source source;
	struct arena arena;
	FILE *stream;
	struct diagnostics diagnostics;
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
};

static void open_fixture(struct fixture *f, const char *text, bool parsed)
{
	memset(f, 0, sizeof *f);
	f->stream = tmpfile(); assert(f->stream);
	f->diagnostics.stream = f->stream;
	assert(source_from_bytes(&f->source, "initialization-ast.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&f->source));
	preprocess_init(&f->preprocessor, &f->source, &f->diagnostics);
	f->unit = parse_translation_unit(&f->preprocessor, &f->arena, &f->diagnostics);
	if (parsed && (!f->unit || f->diagnostics.errors)) {
        char message[1024]; size_t n;
        rewind(f->stream); n=fread(message,1,sizeof message-1,f->stream); message[n]=0;
        fprintf(stderr,"unexpected parser failure for %.100s: %s",text,message);
    }
    if (parsed) assert(f->unit && !f->diagnostics.errors);
	else assert(!f->unit && f->diagnostics.errors == 1);
}

static void close_fixture(struct fixture *f)
{
	arena_destroy(&f->arena); preprocess_destroy(&f->preprocessor); source_destroy(&f->source);
	assert(fclose(f->stream) == 0);
}

static struct ast_external_declaration *declaration(struct fixture *f, unsigned n)
{
	struct ast_external_declaration *d = f->unit->declarations;
	while (n--) { assert(d); d = d->next; }
	assert(d); return d;
}

static struct ast_external_object_declaration *object(struct fixture *f, unsigned n)
{
	struct ast_external_declaration *d = declaration(f, n);
	assert(d->kind == external_object_declaration);
	return (struct ast_external_object_declaration *)d;
}

static uint64_t count(const struct type *type)
{
	assert(type && type->kind == type_kind_array);
	return ((const struct array_type *)type)->count;
}

static void analyze(struct fixture *f)
{
	assert(sema_translation_unit(f->unit, &f->arena, &f->diagnostics));
	assert(!f->diagnostics.errors);
}

static size_t writes(const struct ast_initializer_plan *p)
{
    size_t total=0, values=0;
    for (const struct ast_initializer_plan_entry *e=p->entries;e;e=e->next) {
        assert(e->length && e->offset <= p->size && e->length <= p->size-e->offset);
        for (const struct ast_initializer_plan_entry *other=e->next;other;other=other->next)
            assert(e->offset+e->length<=other->offset || other->offset+other->length<=e->offset);
        ++total;
        if(e->kind!=ast_initializer_write_zero) ++values;
    }
    assert(total==p->entry_count);
    return values;
}

static struct ast_initializer_plan_entry *write_at(struct ast_initializer_plan *p,uint64_t offset)
{
    struct ast_initializer_plan_entry *found=NULL;
    for(struct ast_initializer_plan_entry *e=p->entries;e;e=e->next)
        if(e->kind!=ast_initializer_write_zero && e->offset==offset) { assert(!found); found=e; }
    assert(found); return found;
}

static void check_constructors(void)
{
	struct arena arena = {0};
	struct source_location location = {0};
	struct ast_initializer *i = ast_new_initializer(&arena, ast_initializer_list, location);
	struct ast_initializer_entry *e = ast_new_initializer_entry(&arena, location, i);
	struct ast_designator *d = ast_new_designator(&arena, ast_designator_index, location);
	assert(i && e && d);
	assert(i->kind == ast_initializer_list && !i->expression && !i->entries && !i->entry_count);
	assert(e->value == i && !e->designators && !e->next);
	assert(d->kind == ast_designator_index && !d->index && !d->next);
	arena_destroy(&arena);
}

static void check_syntax_and_continuation(void)
{
	struct fixture f;
	struct ast_external_object_declaration *d;
	struct ast_initializer *syntax;
	struct ast_initializer_entry *first, *second;
	struct ast_designator *designation;
	open_fixture(&f, "int cell[2][3]={[0][1]=19,23,7};", true);
	d = object(&f, 0); syntax = d->initializer_syntax;
	assert(!d->initializer && syntax && syntax->kind == ast_initializer_list && syntax->entry_count == 3);
	first = syntax->entries; second = first->next;
	assert(first->value->kind == ast_initializer_expression && first->value->expression);
	designation = first->designators;
	assert(designation && designation->kind == ast_designator_index && designation->index);
	assert(designation->next && designation->next->kind == ast_designator_index && !designation->next->next);
	assert(second && !second->designators && second->next && !second->next->next);
	assert(!d->initializer_plan && !d->symbol && !d->type);
	analyze(&f);
	assert(d->initializer_syntax == syntax && syntax->entries == first && first->next == second);
	assert(first->designators == designation && syntax->entry_count == 3);
	assert(d->initializer_plan && d->initializer_plan == d->symbol->initializer_plan);
	assert(d->initializer_plan->type == d->type && d->initializer_plan->size == 24 && d->initializer_plan->zero_fill);
	assert(writes(d->initializer_plan) == 3);
	{
		const uint64_t offsets[] = {4,8,12}, bits[] = {19,23,7};
		struct ast_initializer_plan_entry *e;
		for (unsigned n = 0; n < 3; ++n) {
            e=write_at(d->initializer_plan,offsets[n]);
			assert(e && e->offset == offsets[n] && e->length == 4 && type_object_size(e->type) == 4);
			assert(e->kind == ast_initializer_write_expression && e->constant.kind == ast_initializer_constant_integer);
			assert(e->constant.bits == bits[n] && e->syntax);
		}
	}
	close_fixture(&f);
}

static void check_completion_and_canonical_definition(void)
{
	struct fixture f;
	struct ast_external_object_declaration *first, *definition, *last, *following;
	open_fixture(&f, "extern int cell[]; int cell[]={[4]=19,23}; extern int cell[]; int next[sizeof cell]={7};", true);
	first = object(&f,0); definition = object(&f,1); last = object(&f,2); following = object(&f,3);
	analyze(&f);
	assert(first->symbol == definition->symbol && first->symbol == last->symbol);
	assert(first->symbol->definition == &definition->external && !first->symbol->tentative_definition);
	assert(!first->initializer_plan && !last->initializer_plan);
	assert(first->symbol->initializer_plan == definition->initializer_plan);
	assert(count(first->type) == 0 && count(last->type) == 0); /* Captured syntax types, not later entity completion. */
	assert(count(definition->type) == 6 && count(first->symbol->type) == 6);
	assert(first->type != definition->type && definition->initializer_plan->type == definition->type);
	assert(count(following->type) == 24 && type_object_size(following->type) == 96);
	assert(writes(definition->initializer_plan) == 2);
	close_fixture(&f);
}

static void check_address_source_bound_capture(void)
{
    struct fixture f; struct ast_external_object_declaration *early,*pointer,*definition;
    struct address_initializer_result result;
    open_fixture(&f,"extern int cell[]; int (*before)[]=&cell; int cell[]={19,23};",true);
    analyze(&f); early=object(&f,0); pointer=object(&f,1); definition=object(&f,2);
    assert(count(early->type)==0 && count(definition->type)==2);
    result=evaluate_address_initializer(pointer->initializer);
    assert(result.status==constant_value && result.address.kind==static_address_object);
    assert(result.address.base.object==definition->symbol && !result.address.byte_addend);
    assert(result.origin_type && result.origin_type->kind==type_kind_pointer);
    assert(count(((const struct pointer_type *)result.origin_type)->referent)==0);
    close_fixture(&f);
}

static void check_static_and_block_storage(void)
{
    struct fixture f; struct ast_function *function; size_t locals=0,statics=0;
    open_fixture(&f,"static const int private[2]={19,23}; _Thread_local int tls[2]={19,23}; "
        "int test(void) { static int block[2]={19,23}; static _Thread_local int bt[2]={19,23}; "
        "const int automatic[2]={19,23}; return block[0]+bt[0]+automatic[0]+private[0]+tls[0]; }",true);
    analyze(&f);
    assert(object(&f,0)->symbol->is_internal && !object(&f,0)->symbol->is_thread_local);
    assert(object(&f,1)->symbol->is_thread_local && !object(&f,1)->symbol->is_internal);
    function=(struct ast_function *)declaration(&f,2);
    assert(function->external.kind==external_function_definition);
    for(struct ast_block_item *item=function->body->items;item;item=item->next) {
        if(item->kind!=block_item_declaration) continue;
        struct ast_local_declaration *d=(struct ast_local_declaration *)item;
        ++locals; assert(d->initializer_plan && d->initializer_plan->size==8);
        if(d->is_static) {
            ++statics; assert(d->object_symbol && d->object_symbol->is_block_static);
            assert(d->object_symbol->is_internal && d->object_symbol->is_thread_local==d->is_thread_local);
            assert(d->object_symbol->initializer_plan==d->initializer_plan);
        } else assert(!d->object_symbol);
    }
    assert(locals==3 && statics==2 && f.unit->static_declarations);
    close_fixture(&f);
}

static void check_alias_capture(void)
{
	struct fixture f;
	struct ast_external_typedef_declaration *alias;
	struct ast_external_type_declaration *definition;
	open_fixture(&f,"typedef int Unknown[]; static Unknown cell={[3]=42};",true);
	analyze(&f);
	alias=(struct ast_external_typedef_declaration *)declaration(&f,0);
	definition=(struct ast_external_type_declaration *)declaration(&f,1);
	assert(alias->external.kind == external_typedef_declaration && definition->external.kind == external_type_declaration);
	assert(count(alias->declaration->type) == 0 && count(definition->type) == 4);
	assert(definition->object_symbol && definition->object_symbol->is_internal && !definition->symbol);
	assert(definition->object_symbol->definition == &definition->external);
	assert(definition->object_symbol->initializer_plan == definition->initializer_plan);
	close_fixture(&f);
}

static void check_override_plan(void)
{
	struct fixture f;
	struct ast_external_object_declaration *d;
	open_fixture(&f,"int cell[4]={[1]=5,[1]=42,[3]=7};",true);
	d=object(&f,0); analyze(&f);
	assert(d->initializer_syntax->entry_count == 3 && writes(d->initializer_plan) == 2);
	assert(write_at(d->initializer_plan,4)->constant.bits == 42);
    assert(write_at(d->initializer_plan,12)->constant.bits == 7);
	close_fixture(&f);
}

static void check_cached_tags_and_pure_queries(void)
{
	struct fixture f;
	struct ast_external_object_declaration *target, *d;
	struct ast_initializer_plan_entry *e;
	struct ast_initializer_plan snapshot;
	struct ast_translation_unit unit;
	unsigned errors;
	open_fixture(&f,"int target[3]; int fn(void); struct R { int x; int *p; int *z; int (*f)(void); char *s; typeof(nullptr) n; }; struct R cell={42,target+2,0,fn,\"a\\0b\",nullptr};",true);
	analyze(&f); target=object(&f,0); d=object(&f,3);
	assert(d->initializer_plan && writes(d->initializer_plan) == 6);
	e=write_at(d->initializer_plan,0);
	assert(e->constant.kind == ast_initializer_constant_integer && e->constant.bits == 42);
	e=write_at(d->initializer_plan,8);
    assert(e->constant.kind == ast_initializer_constant_address && e->constant.address_kind == ast_initializer_address_object);
    assert(e->constant.base.object == target->symbol && e->constant.byte_addend == 8);
    assert(write_at(d->initializer_plan,16)->constant.kind == ast_initializer_constant_null);
    e=write_at(d->initializer_plan,24);
    assert(e->constant.kind == ast_initializer_constant_address && e->constant.address_kind == ast_initializer_address_function);
    assert(e->constant.base.function == ((struct ast_function_declaration *)declaration(&f,1))->symbol && !e->constant.byte_addend);
    e=write_at(d->initializer_plan,32);
    assert(e->constant.kind == ast_initializer_constant_address && e->constant.address_kind == ast_initializer_address_string);
    assert(e->constant.base.string && !e->constant.byte_addend);
    assert(write_at(d->initializer_plan,40)->constant.kind == ast_initializer_constant_null);
	snapshot=*d->initializer_plan; unit=*f.unit; errors=f.diagnostics.errors;
	for (e=d->initializer_plan->entries; e; e=e->next) {
        if(e->kind==ast_initializer_write_zero) continue;
		struct ast_initializer_plan_entry before=*e;
		struct ast_expression expression=*e->expression;
		for (unsigned n=0;n<16;++n) {
			(void)evaluate_integer_constant(e->expression);
			(void)evaluate_null_initializer(e->expression);
			(void)evaluate_address_initializer(e->expression);
		}
		assert(!memcmp(&before,e,sizeof before));
		assert(!memcmp(&expression,e->expression,sizeof expression));
	}
	assert(!memcmp(&snapshot,d->initializer_plan,sizeof snapshot));
	assert(!memcmp(&unit,f.unit,sizeof unit) && errors == f.diagnostics.errors);
	close_fixture(&f);
}

static void check_string_extent_and_compact_plan(void)
{
	struct fixture f;
	struct ast_external_object_declaration *d;
	struct ast_initializer_plan_entry *e;
	open_fixture(&f,"char cell[3]={\"a\\0b\"};",true); analyze(&f); d=object(&f,0); e=d->initializer_plan->entries;
	assert(writes(d->initializer_plan) == 1 && e->kind == ast_initializer_write_string && e->length == 3);
	assert(!memcmp(e->bytes,"a\0b",3) && !e->next); close_fixture(&f);
	open_fixture(&f,"unsigned char cell[1048576]={[1048575]=42};",true); analyze(&f); d=object(&f,0);
	assert(type_object_size(d->type) == 1048576 && d->initializer_plan->size == 1048576);
	assert(d->initializer_plan->zero_fill && writes(d->initializer_plan) == 1);
	e=write_at(d->initializer_plan,1048575); assert(e->length == 1 && e->constant.bits == 42);
    assert(d->initializer_plan->entry_count<=3);
	close_fixture(&f);
}

static void check_failed_publication(void)
{
	const char *sources[]={
		"extern int cell[]; int cell[]={[3]=42,[4]=missing};",
		"extern int cell[]; int cell[]={sizeof cell};",
		"extern int cell[]; int cell[]={};",
		"extern int cell[]; int cell[]={[262144]=42};",
		"extern int cell[]; int cell[]={[18446744073709551615ULL]=42};",
	};
	for(unsigned n=0;n<sizeof sources/sizeof *sources;++n) {
		struct fixture f; struct ast_external_object_declaration *first,*bad;
		open_fixture(&f,sources[n],true); first=object(&f,0); bad=object(&f,1);
		assert(!sema_translation_unit(f.unit,&f.arena,&f.diagnostics) && f.diagnostics.errors == 1);
		assert(first->symbol && count(first->type) == 0 && count(first->symbol->type) == 0);
		assert(!first->symbol->definition && !first->symbol->initializer_plan && !first->symbol->tentative_definition);
		assert(!bad->symbol && !bad->type && !bad->initializer_plan);
		assert(!f.unit->strings && !f.unit->static_declarations);
		close_fixture(&f);
	}
}

static void check_prior_definition_failure(void)
{
    struct fixture f; struct ast_external_object_declaration *first,*bad;
    open_fixture(&f,"int cell[2]={19,23}; int cell[2]={42};",true);
    assert(!sema_translation_unit(f.unit,&f.arena,&f.diagnostics) && f.diagnostics.errors==1);
    first=object(&f,0); bad=object(&f,1);
    assert(first->symbol && first->symbol->definition==&first->external);
    assert(first->symbol->initializer_plan==first->initializer_plan && writes(first->initializer_plan)==2);
    assert(write_at(first->initializer_plan,0)->constant.bits==19 && write_at(first->initializer_plan,4)->constant.bits==23);
    assert(!bad->symbol && !bad->initializer_plan && !bad->type);
    close_fixture(&f);
    open_fixture(&f,"struct R { char *s; int n; }; extern struct R cell; struct R cell={\"failed\",missing};",true);
    assert(!sema_translation_unit(f.unit,&f.arena,&f.diagnostics) && f.diagnostics.errors==1);
    first=object(&f,1); bad=object(&f,2);
    assert(first->symbol && !first->symbol->definition && !first->symbol->initializer_plan);
    assert(!bad->symbol && !bad->initializer_plan && !bad->type);
    assert(!f.unit->strings && !f.unit->static_declarations);
    close_fixture(&f);
}

static void check_promoted_exact_conditional_null(void)
{
    /* Exact original formerly refused by the legacy null AST suite. */
    struct fixture f; struct ast_external_object_declaration *d;
    struct static_data_value cache; struct ast_expression expression;
    const struct type *captured; struct ast_translation_unit unit;
    open_fixture(&f,"int *cell=1?(int *)0:(int *)0;",true);
    d=object(&f,0); assert(d->initializer && d->initializer_syntax);
    analyze(&f);
    assert(d->symbol && d->symbol->definition==&d->external && !d->symbol->tentative_definition);
    assert(d->symbol->type==d->type && !d->symbol->is_internal);
    assert(d->symbol->initializer_value.kind==static_data_null_pointer);
    assert(!d->symbol->initializer_plan && !d->initializer_plan);
    captured=d->initializer->type; expression=*d->initializer; cache=d->symbol->initializer_value; unit=*f.unit;
    for(unsigned n=0;n<32;++n) {
        struct null_initializer_result null=evaluate_null_initializer(d->initializer);
        struct address_initializer_result address=evaluate_address_initializer(d->initializer);
        assert(null.status==constant_value && address.status==constant_not_constant);
        assert(d->initializer->type==captured && !memcmp(&expression,d->initializer,sizeof expression));
        assert(!memcmp(&cache,&d->symbol->initializer_value,sizeof cache));
        assert(!memcmp(&unit,f.unit,sizeof unit) && !f.diagnostics.errors);
    }
    /* Null's dedicated cache tag, never an address relocation/sentinel. */
    assert(!f.unit->strings && !f.unit->static_declarations);
    close_fixture(&f);
}

static void check_difference_condition_private_address_not_public_ice(void)
{
    struct fixture f; struct ast_external_object_declaration *a,*g,*h,*p;
    struct ast_conditional_expression *conditional, conditional_before;
    struct ast_binary_expression *condition, condition_before;
    struct ast_pointer_difference_expression *difference, difference_before;
    struct static_data_value cache; struct ast_translation_unit unit;
    struct external_object_symbol a_before,g_before,h_before,p_before;
    /* Exact original: the whole expression is an address initializer. Its
     * same-array difference is defined, but never gains public ICE status. */
    open_fixture(&f,"int a[2],g,h;int*p=((&a[1]-&a[0])==1)?&g:&h;",true);
    analyze(&f); a=object(&f,0); g=object(&f,1); h=object(&f,2); p=object(&f,3);
    assert(count(a->type)==2 && p->symbol->definition==&p->external);
    assert(p->initializer->kind==expression_conditional);
    conditional=(struct ast_conditional_expression *)p->initializer;
    assert(conditional->condition->kind==expression_binary);
    condition=(struct ast_binary_expression *)conditional->condition;
    assert(condition->operation==binary_equal && condition->left->kind==expression_pointer_difference);
    difference=(struct ast_pointer_difference_expression *)condition->left;
    assert(difference->element_size==4);
    assert(p->symbol->initializer_value.kind==static_data_address);
    assert(p->symbol->initializer_value.address.kind==static_address_object);
    assert(p->symbol->initializer_value.address.base.object==g->symbol);
    assert(!p->symbol->initializer_value.address.byte_addend && !p->initializer_plan && !p->symbol->initializer_plan);
    conditional_before=*conditional; condition_before=*condition; difference_before=*difference;
    cache=p->symbol->initializer_value; unit=*f.unit;
    a_before=*a->symbol; g_before=*g->symbol; h_before=*h->symbol; p_before=*p->symbol;
    for(unsigned query=0;query<32;++query) {
        struct address_initializer_result address=evaluate_address_initializer(p->initializer);
        assert(address.status==constant_value && address.address.kind==static_address_object);
        assert(address.address.base.object==g->symbol && !address.address.byte_addend);
        assert(evaluate_integer_constant(&difference->expression).status==constant_not_constant);
        assert(evaluate_integer_constant(&condition->expression).status==constant_not_constant);
        assert(evaluate_integer_constant(p->initializer).status==constant_not_constant);
        assert(evaluate_null_initializer(p->initializer).status==constant_not_constant);
        assert(!memcmp(&conditional_before,conditional,sizeof conditional_before));
        assert(!memcmp(&condition_before,condition,sizeof condition_before));
        assert(!memcmp(&difference_before,difference,sizeof difference_before));
        assert(!memcmp(&cache,&p->symbol->initializer_value,sizeof cache));
        assert(!memcmp(&a_before,a->symbol,sizeof a_before) && !memcmp(&g_before,g->symbol,sizeof g_before));
        assert(!memcmp(&h_before,h->symbol,sizeof h_before) && !memcmp(&p_before,p->symbol,sizeof p_before));
        assert(!memcmp(&unit,f.unit,sizeof unit) && !f.diagnostics.errors);
    }
    assert(!f.unit->strings && !f.unit->static_declarations);
    close_fixture(&f);
}

static void check_nominal_difference_paths_and_unknown_bound_purity(void)
{
    const char *sources[]={
        "typedef int A[2];union U{A a,b;}u;int g,h;int*p=((&u.a[1]-&u.a[0])==1)?&g:&h;",
        "typedef int A[2];union V{A a,b;};struct S{union V v;};union U{struct S a,b;}u;int g,h;int*p=((&u.a.v.a[1]-&u.a.v.a[0])==1)?&g:&h;",
        "extern int a[];int g,h;int*p=((&a[1]-&a[0])==1)?&g:&h;",
    };
    for(unsigned n=0;n<3;++n) {
        struct fixture f; struct ast_external_object_declaration *objects[4],*p;
        struct ast_conditional_expression *conditional, before;
        struct ast_binary_expression *comparison;
        struct static_data_value cache; struct ast_translation_unit unit;
        struct external_object_symbol root_before,p_before;
        unsigned count_objects=0;
        open_fixture(&f,sources[n],true); analyze(&f);
        for(struct ast_external_declaration *d=f.unit->declarations;d;d=d->next) {
            if(d->kind!=external_object_declaration) continue;
            assert(count_objects<4); objects[count_objects++]=(struct ast_external_object_declaration *)d;
        }
        assert(count_objects==4); p=objects[3];
        assert(p->initializer->kind==expression_conditional);
        conditional=(struct ast_conditional_expression *)p->initializer;
        assert(conditional->condition->kind==expression_binary);
        comparison=(struct ast_binary_expression *)conditional->condition;
        assert(comparison->operation==binary_equal && comparison->left->kind==expression_pointer_difference);
        assert(p->symbol->initializer_value.kind==static_data_address);
        assert(p->symbol->initializer_value.address.base.object==objects[1]->symbol);
        assert(!p->symbol->initializer_value.address.byte_addend);
        if(n==2) assert(objects[0]->is_extern && count(objects[0]->type)==0);
        before=*conditional; cache=p->symbol->initializer_value; unit=*f.unit;
        root_before=*objects[0]->symbol; p_before=*p->symbol;
        for(unsigned query=0;query<32;++query) {
            struct address_initializer_result address=evaluate_address_initializer(p->initializer);
            assert(address.status==constant_value && address.address.kind==static_address_object);
            assert(address.address.base.object==objects[1]->symbol && !address.address.byte_addend);
            assert(evaluate_integer_constant(comparison->left).status==constant_not_constant);
            assert(evaluate_integer_constant(conditional->condition).status==constant_not_constant);
            assert(!memcmp(&before,conditional,sizeof before));
            assert(!memcmp(&cache,&p->symbol->initializer_value,sizeof cache));
            assert(!memcmp(&root_before,objects[0]->symbol,sizeof root_before));
            assert(!memcmp(&p_before,p->symbol,sizeof p_before));
            assert(!memcmp(&unit,f.unit,sizeof unit) && !f.diagnostics.errors);
            if(n==2) assert(count(objects[0]->type)==0);
        }
        assert(!f.unit->strings && !f.unit->static_declarations);
        close_fixture(&f);
    }
}

static void check_source_constant_bool_is_not_integer_ice(void)
{
    const char *sources[]={"int target; _Bool cell=&target;","_Bool cell=(int *)0;"};
    for(unsigned n=0;n<2;++n) {
        struct fixture f; struct ast_external_object_declaration *d;
        struct static_data_value cache; struct ast_expression expression;
        open_fixture(&f,sources[n],true); analyze(&f); d=object(&f,n==0?1:0);
        assert(d->symbol && d->symbol->definition==&d->external);
        assert(d->symbol->initializer_value.kind==static_data_integer && d->symbol->initializer_value.integer_bits==(n==0));
        cache=d->symbol->initializer_value; expression=*d->initializer;
        for(unsigned query=0;query<16;++query) {
            struct constant_result result=evaluate_integer_constant(d->initializer);
            assert(result.status==constant_not_constant); /* Conversion does not grant ICE source operands. */
            assert(!memcmp(&cache,&d->symbol->initializer_value,sizeof cache));
            assert(!memcmp(&expression,d->initializer,sizeof expression) && !f.diagnostics.errors);
        }
        close_fixture(&f);
    }
}

static void check_union_copy_fragments_and_capture_once(void)
{
    struct fixture f; struct ast_function *fn; struct ast_local_declaration *r=NULL;
    struct ast_expression *capture=NULL; unsigned locals=0,copies=0,scalars=0;
    open_fixture(&f,"union U{struct S{int x,y,z;}s;long l;};struct R{union U u;};"
        "int main(void){int n=0;union U seed={.s={3,4,5}};"
        "struct R r={.u=(++n,seed),.u.s.y=9};"
        "return n==1&&r.u.s.x==3&&r.u.s.y==9&&r.u.s.z==5?0:1;}",true);
    analyze(&f); fn=(struct ast_function *)declaration(&f,2);
    assert(fn->external.kind==external_function_definition);
    for(struct ast_block_item *item=fn->body->items;item;item=item->next) {
        if(item->kind==block_item_declaration) {
            if(locals++==2) r=(struct ast_local_declaration *)item;
        }
    }
    assert(r && locals==3 && r->initializer_plan && writes(r->initializer_plan)==3);
    assert(r->initializer_syntax->entry_count==2 && r->initializer_plan->size==16);
    for(struct ast_initializer_plan_entry *e=r->initializer_plan->entries;e;e=e->next) {
        if(e->kind==ast_initializer_write_copy) {
            ++copies;
            assert((e->offset==0 && e->length==4) || (e->offset==8 && e->length==8));
            assert(e->source_offset==e->offset && e->expression);
            if(capture) assert(capture==e->expression); else capture=e->expression;
        } else if(e->kind==ast_initializer_write_expression) {
            struct constant_result result=evaluate_integer_constant(e->expression);
            ++scalars; assert(e->offset==4 && e->length==4 && result.status==constant_value && result.bits==9);
        } else assert(e->kind==ast_initializer_write_zero);
    }
    /* One checked source expression is the backend's capture key for both
     * disjoint slices: ++n must run once, not once per retained copy fragment. */
    assert(copies==2 && scalars==1 && capture);
    {
        struct ast_expression before=*capture;
        assert(evaluate_integer_constant(capture).status==constant_not_constant);
        assert(!memcmp(&before,capture,sizeof before) && !f.diagnostics.errors);
    }
    close_fixture(&f);
}

static void check_parser_budgets(void)
{
	/* All generated input is bounded (<100 KiB); no timeout/source explosion. */
	for (unsigned over=0;over<2;++over) {
		/* The terminal expression also consumes one nesting level. */
        unsigned depth=ast_max_initializer_nesting-1+over;
		size_t capacity=128+2*depth; char *text=calloc(capacity,1); struct fixture f;
		assert(text); strcpy(text,"int cell=");
		for(unsigned n=0;n<depth;++n) strcat(text,"{");
		strcat(text,"42"); for(unsigned n=0;n<depth;++n) strcat(text,"}"); strcat(text,";");
		open_fixture(&f,text,!over); if(!over) analyze(&f); close_fixture(&f); free(text);
	}
	for (unsigned over=0;over<2;++over) {
		/* Root list consumes one initializer node; each leaf one more. */
		unsigned leaves=ast_max_initializer_nodes-1+over;
		size_t capacity=128+2*(size_t)leaves; char *text=calloc(capacity,1); struct fixture f;
		assert(text); strcpy(text,"unsigned char cell[]={");
		for(unsigned n=0;n<leaves;++n) strcat(text,n?",0":"0");
		strcat(text,"};");
		open_fixture(&f,text,!over); if(!over) analyze(&f); close_fixture(&f); free(text);
	}
    for(unsigned over=0;over<2;++over) {
        char text[512]="int cell[1]={[0]"; struct fixture f;
        for(unsigned n=1;n<ast_max_designator_depth+over;++n) strcat(text,"[0]");
        strcat(text,"=0};"); open_fixture(&f,text,!over); close_fixture(&f);
    }
    for(unsigned over=0;over<2;++over) {
        size_t capacity=128+4*(size_t)ast_max_designators;
        char *text=calloc(capacity,1),*out; struct fixture f; unsigned emitted=0;
        assert(text); strcpy(text,"int cell[1]={"); out=text+strlen(text);
        while(emitted<ast_max_designators+over) {
            if(emitted) *out++=',';
            unsigned remaining=ast_max_designators+over-emitted;
            unsigned chain=remaining<ast_max_designator_depth?remaining:ast_max_designator_depth;
            for(unsigned n=0;n<chain;++n) { memcpy(out,"[0]",3); out+=3; }
            memcpy(out,"=0",2); out+=2; emitted+=chain;
        }
        memcpy(out,"};",3); open_fixture(&f,text,!over); close_fixture(&f); free(text);
    }

}

int main(void)
{
	check_constructors(); check_syntax_and_continuation(); check_completion_and_canonical_definition();
	check_address_source_bound_capture(); check_static_and_block_storage();
    check_alias_capture(); check_override_plan(); check_cached_tags_and_pure_queries();
	check_string_extent_and_compact_plan(); check_failed_publication(); check_prior_definition_failure(); check_promoted_exact_conditional_null(); check_source_constant_bool_is_not_integer_ice(); check_difference_condition_private_address_not_public_ice(); check_nominal_difference_paths_and_unknown_bound_purity(); check_union_copy_fragments_and_capture_once(); check_parser_budgets();
	puts("M17 initialization AST: syntax/capture/canonical plans/static tags/purity/failure/budgets");
	return 0;
}

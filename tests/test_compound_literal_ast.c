/* Independent M17 compound-literal ownership, plan, capture and pure-query
 * oracle. Compile against selected frozen sources excluding main.c. No Makefile
 * integration required. Strict and ASan/UBSan runs are separate release gates.
 * Snapshot walker adapted from the hardened M16 record runtime oracle. */
#include "parse.h"
#include "sema.h"
#include "consteval.h"
#include "type.h"

#include <assert.h>
#include <limits.h>
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

static void open_fixture_mode(struct fixture *f, const char *text, bool success)
{
	memset(f, 0, sizeof *f);
	f->stream = tmpfile();
	assert(f->stream);
	f->diagnostics.stream = f->stream;
	assert(source_from_bytes(&f->source, "literal-ast.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&f->source));
	preprocess_init(&f->preprocessor, &f->source, &f->diagnostics);
	f->unit = parse_translation_unit(&f->preprocessor, &f->arena, &f->diagnostics);
	if (success) assert(f->unit && !f->diagnostics.errors);
    else assert(!f->unit && f->diagnostics.errors==1);
}

static void open_fixture(struct fixture *f, const char *text)
{
    open_fixture_mode(f,text,true);
}

static void close_fixture(struct fixture *f)
{
	arena_destroy(&f->arena);
	preprocess_destroy(&f->preprocessor);
	source_destroy(&f->source);
	assert(fclose(f->stream) == 0);
}

static struct ast_external_declaration *declaration(struct fixture *f, unsigned index)
{
	struct ast_external_declaration *d = f->unit->declarations;
	while (index--) {
		assert(d);
		d = d->next;
	}
	assert(d);
	return d;
}

static struct ast_external_object_declaration *object(struct fixture *f, unsigned index)
{
	struct ast_external_declaration *d = declaration(f, index);
	assert(d->kind == external_object_declaration);
	return (struct ast_external_object_declaration *)d;
}

/* Copy object representations, not hashes: even shared captures, pointer links,
 * padding and ownership fields must remain byte-for-byte unchanged by queries.
 * Deduplication makes this a bounded DAG walk rather than expanding sharing. */
struct saved_bytes { const void *address; size_t size; unsigned char bytes[512]; };
struct snapshot { size_t count; struct saved_bytes entries[2048];
 size_t literal_count; const struct ast_compound_literal_expression *literals[256]; };

static bool save(struct snapshot *s, const void *address, size_t size)
{
	for (size_t i = 0; i < s->count; ++i)
		if (s->entries[i].address == address)
			return false;
	assert(address && s->count < 2048 && size <= sizeof s->entries[0].bytes);
	s->entries[s->count].address = address;
	s->entries[s->count].size = size;
	memcpy(s->entries[s->count++].bytes, address, size);
	return true;
}

static void save_type(struct snapshot *s, const struct type *t)
{
	if (!t) return;
	if (type_is_record(t)) {
		const struct record_type *r = (const struct record_type *)t;
		if (!save(s, r, sizeof *r)) return;
		const struct record_definition *d = r->definition;
		if (!save(s, d, sizeof *d)) return;
		for (const struct record_member *m = d->members; m; m = m->next) {
			if (!save(s, m, sizeof *m)) break;
			save_type(s, m->type);
		}
	} else if (t->kind == type_kind_pointer) {
		if (save(s, t, sizeof(struct pointer_type)))
			save_type(s, ((const struct pointer_type *)t)->referent);
	} else if (t->kind == type_kind_array) {
		if (save(s, t, sizeof(struct array_type)))
			save_type(s, ((const struct array_type *)t)->element);
	} else if (t->kind == type_kind_function) {
		if (!save(s, t, sizeof(struct function_type))) return;
		const struct function_type *fn = (const struct function_type *)t;
		save_type(s, fn->return_type);
		for (const struct function_parameter_type *p = fn->parameters; p; p = p->next) {
			if (!save(s, p, sizeof *p)) break;
			save_type(s, p->type);
		}
	} else {
		(void)save(s, t, sizeof *t);
	}
}

static void save_expression(struct snapshot *, const struct ast_expression *);
static void save_syntax(struct snapshot *, const struct ast_type_syntax *);
static void save_initializer(struct snapshot *, const struct ast_initializer *);
static void save_plan(struct snapshot *, const struct ast_initializer_plan *);
static void save_object(struct snapshot *, const struct external_object_symbol *);
static void save_local(struct snapshot *, const struct ast_local_declaration *);

#define SAVE_NODE(T) const struct T *n = (const struct T *)e; \
	if (!save(s, n, sizeof *n)) return

static void save_expression(struct snapshot *s, const struct ast_expression *e)
{
	assert(e);
	/* Unevaluated ICE arms can intentionally retain untyped parsed nodes. */
	if (e->type) save_type(s, e->type);
	switch (e->kind) {
	case expression_member: {
		SAVE_NODE(ast_member_expression);
		save_expression(s, n->operand);
		if (n->member) {
			(void)save(s, n->member, sizeof *n->member);
			save_type(s, n->member->type);
		}
		break;
	}
	case expression_assignment: {
		SAVE_NODE(ast_assignment_expression);
		save_expression(s, n->left); save_expression(s, n->right); break;
	}
	case expression_comma: {
		SAVE_NODE(ast_comma_expression);
		save_expression(s, n->left); save_expression(s, n->right); break;
	}
	case expression_pointer_offset: {
		SAVE_NODE(ast_pointer_offset_expression);
		save_expression(s, n->base); save_expression(s, n->index); break;
	}
	case expression_address: {
		SAVE_NODE(ast_address_expression); save_expression(s, n->operand); break;
	}
	case expression_subscript: {
		SAVE_NODE(ast_subscript_expression);
		save_expression(s, n->left); save_expression(s, n->right); break;
	}
	case expression_indirection: {
		SAVE_NODE(ast_indirection_expression); save_expression(s, n->operand); break;
	}
	case expression_load: {
		SAVE_NODE(ast_load_expression); save_expression(s, n->operand); break;
	}
	case expression_array_decay: {
		SAVE_NODE(ast_array_decay_expression); save_expression(s, n->operand); break;
	}
	case expression_function_decay: {
		SAVE_NODE(ast_function_decay_expression); save_expression(s, n->operand); break;
	}
	case expression_cast: {
		SAVE_NODE(ast_cast_expression); save_syntax(s,n->type_syntax); save_expression(s, n->operand); break;
	}
	case expression_conversion: {
		SAVE_NODE(ast_conversion_expression); save_expression(s, n->operand); break;
	}
	case expression_unary: {
		SAVE_NODE(ast_unary_expression); save_expression(s, n->operand); break;
	}
	case expression_binary: {
		SAVE_NODE(ast_binary_expression);
		save_expression(s, n->left); save_expression(s, n->right); break;
	}
	case expression_conditional: {
		SAVE_NODE(ast_conditional_expression);
		save_expression(s, n->condition); save_expression(s, n->then_value);
		save_expression(s, n->else_value); break;
	}
	case expression_external_object: {
		SAVE_NODE(ast_external_object_expression);
		save_object(s, n->object); break;
	}
	case expression_function_designator: {
		SAVE_NODE(ast_function_designator_expression);
		(void)save(s, n->function, sizeof *n->function); break;
	}
	case expression_string: {
		SAVE_NODE(ast_string_expression);
		(void)save(s, n->bytes, n->length+1); break;
	}
	case expression_name: {
		SAVE_NODE(ast_name_expression);
		if (n->declaration) {
			save_local(s, n->declaration);
		}
		break;
	}
	case expression_integer: (void)save(s, e, sizeof(struct ast_integer_expression)); break;
	case expression_nullptr: (void)save(s, e, sizeof(struct ast_nullptr_expression)); break;
	case expression_sizeof_type: {
        SAVE_NODE(ast_sizeof_type_expression); save_syntax(s, n->type_syntax); break;
    }
    case expression_compound_literal: {
        SAVE_NODE(ast_compound_literal_expression);
        assert(s->literal_count < 256); s->literals[s->literal_count++] = n;
        save_syntax(s, n->type_syntax); save_initializer(s, n->initializer_syntax);
        save_plan(s, n->initializer_plan); save_local(s, n->local); save_object(s, n->object); break;
    }
    case expression_sizeof: { SAVE_NODE(ast_sizeof_expression); save_expression(s,n->operand); break; }
    case expression_prefix_update: { SAVE_NODE(ast_prefix_update_expression); save_expression(s,n->operand); save_type(s,n->calculation_type); break; }
    case expression_postfix_update: { SAVE_NODE(ast_postfix_update_expression); save_expression(s,n->operand); save_type(s,n->calculation_type); break; }
    case expression_logical: { SAVE_NODE(ast_logical_expression); save_expression(s,n->left); save_expression(s,n->right); break; }
    case expression_compound_assignment: { SAVE_NODE(ast_compound_assignment_expression); save_expression(s,n->left); save_expression(s,n->right); break; }
    case expression_pointer_difference: { SAVE_NODE(ast_pointer_difference_expression); save_expression(s,n->left); save_expression(s,n->right); break; }
    case expression_boolean: (void)save(s,e,sizeof(struct ast_boolean_expression)); break;
    case expression_character: (void)save(s,e,sizeof(struct ast_character_expression)); break;
    case expression_call: {
        SAVE_NODE(ast_call_expression); save_expression(s,n->callee);
        for (const struct ast_argument *a=n->arguments; a; a=a->next) {
            if (!save(s,a,sizeof *a)) break;
            save_expression(s,a->value);
        } break;
    }
	default: fprintf(stderr, "purity walker missing expression kind %d\n", (int)e->kind);
		assert(!"extend the explicit purity walker for this AST kind");
	}
}

static void save_initializer(struct snapshot *s, const struct ast_initializer *n)
{
    if (!n || !save(s,n,sizeof *n)) return;
    if (n->expression) save_expression(s,n->expression);
    for (const struct ast_initializer_entry *e=n->entries; e; e=e->next) {
        if (!save(s,e,sizeof *e)) break;
        for (const struct ast_designator *d=e->designators; d; d=d->next) {
            if (!save(s,d,sizeof *d)) break;
            if (d->index) save_expression(s,d->index);
        }
        save_initializer(s,e->value);
    }
}

static void save_syntax(struct snapshot *s, const struct ast_type_syntax *t)
{
    if (!t) return;
    save_type(s,t->type);
#define SYNTAX(T) const struct T *n=(const struct T *)t; if (!save(s,n,sizeof *n)) return
    switch (t->kind) {
    case type_syntax_pointer: { SYNTAX(ast_pointer_type_syntax); save_syntax(s,n->referent); break; }
    case type_syntax_array: { SYNTAX(ast_array_type_syntax); save_syntax(s,n->element); if(n->bound) save_expression(s,n->bound); break; }
    case type_syntax_qualified: { SYNTAX(ast_qualified_type_syntax); save_syntax(s,n->base); break; }
    case type_syntax_typeof_type: { SYNTAX(ast_typeof_type_syntax); save_syntax(s,n->operand); break; }
    case type_syntax_typeof_expression: { SYNTAX(ast_typeof_expression_syntax); save_expression(s,n->operand); break; }
    case type_syntax_record: {
        SYNTAX(ast_record_type_syntax);
        for (const struct ast_record_member_declaration *m=n->members; m; m=m->next) {
            if (!save(s,m,sizeof *m)) break;
            save_syntax(s,m->type_syntax);
        } break;
    }
    case type_syntax_function: {
        SYNTAX(ast_function_type_syntax); save_syntax(s,n->return_syntax);
        for (const struct ast_parameter *p=n->parameters; p; p=p->next) {
            if (!save(s,p,sizeof *p)) break;
            save_syntax(s,p->type_syntax); save_type(s,p->type); save_local(s,p->local);
        } break;
    }
    case type_syntax_integer: { SYNTAX(ast_integer_type_syntax); break; }
    case type_syntax_void: { SYNTAX(ast_void_type_syntax); break; }
    case type_syntax_typedef_name: { SYNTAX(ast_typedef_name_type_syntax); break; }
    case type_syntax_inferred: { SYNTAX(ast_inferred_type_syntax); break; }
    }
#undef SYNTAX
}

static void save_plan(struct snapshot *s, const struct ast_initializer_plan *p)
{
    if (!p || !save(s,p,sizeof *p)) return;
    save_type(s,p->type);
    for (const struct ast_initializer_plan_entry *e=p->entries; e; e=e->next) {
        if (!save(s,e,sizeof *e)) break;
        save_type(s,e->type); save_initializer(s,e->syntax);
        if (e->expression) save_expression(s,e->expression);
        if (e->bytes && e->length) (void)save(s,e->bytes,e->length);
        if (e->constant.kind != ast_initializer_constant_address) continue;
        switch (e->constant.address_kind) {
        case ast_initializer_address_object: save_object(s,e->constant.base.object); break;
        case ast_initializer_address_compound_literal: save_expression(s,&e->constant.base.compound_literal->expression); break;
        case ast_initializer_address_string: save_expression(s,&e->constant.base.string->expression); break;
        case ast_initializer_address_function: (void)save(s,e->constant.base.function,sizeof *e->constant.base.function); break;
        }
    }
}

static void save_object(struct snapshot *s, const struct external_object_symbol *o)
{
    if (!o || !save(s,o,sizeof *o)) return;
    save_type(s,o->type); save_type(s,o->file_type); save_plan(s,o->initializer_plan);
    if (o->definition) (void)save(s,o->definition,sizeof(struct ast_external_object_declaration));
}

static void save_local(struct snapshot *s, const struct ast_local_declaration *l)
{
    if (!l || !save(s,l,sizeof *l)) return;
    save_type(s,l->type); save_syntax(s,l->type_syntax);
    save_initializer(s,l->initializer_syntax); save_plan(s,l->initializer_plan);
    if (l->initializer) save_expression(s,l->initializer);
    save_object(s,l->object_symbol);
}

static void save_statement(struct snapshot *s, const struct ast_statement *v)
{
    if (!v) return;
    switch (v->kind) {
    case statement_return: {
        const struct ast_return_statement *n=(const struct ast_return_statement *)v;
        if (save(s,n,sizeof *n) && n->value) save_expression(s,n->value);
        break;
    }
    case statement_expression: {
        const struct ast_expression_statement *n=(const struct ast_expression_statement *)v;
        if (save(s,n,sizeof *n) && n->value) save_expression(s,n->value);
        break;
    }
    case statement_compound: {
        const struct ast_compound_statement *n=(const struct ast_compound_statement *)v;
        if (!save(s,n,sizeof *n)) break;
        for (const struct ast_block_item *i=n->items; i; i=i->next) {
            if (i->kind==block_item_declaration) save_local(s,(const struct ast_local_declaration *)i);
            else {
                assert(i->kind==block_item_statement);
                const struct ast_statement_item *item=(const struct ast_statement_item *)i;
                (void)save(s,item,sizeof *item); save_statement(s,item->statement);
            }
        } break;
    }
    default: assert(!"extend explicit statement snapshot walker");
    }
}

static struct snapshot *capture(struct fixture *f)
{
    struct snapshot *s=calloc(1,sizeof *s); assert(s);
    (void)save(s,f->unit,sizeof *f->unit); (void)save(s,&f->arena,sizeof f->arena);
    (void)save(s,&f->diagnostics,sizeof f->diagnostics);
    for (const struct ast_external_declaration *d=f->unit->declarations; d; d=d->next) {
        switch (d->kind) {
        case external_object_declaration: {
            const struct ast_external_object_declaration *o=(const struct ast_external_object_declaration *)d;
            (void)save(s,o,sizeof *o); save_type(s,o->type); save_syntax(s,o->type_syntax);
            save_initializer(s,o->initializer_syntax); save_plan(s,o->initializer_plan);
            if (o->initializer) save_expression(s,o->initializer);
            save_object(s,o->symbol); break;
        }
        case external_function_definition: {
            const struct ast_function *fn=(const struct ast_function *)d;
            (void)save(s,fn,sizeof *fn); (void)save(s,fn->declaration,sizeof *fn->declaration);
            save_syntax(s,(const struct ast_type_syntax *)fn->declaration->type_syntax);
            save_statement(s,&fn->body->statement);
            for (const struct ast_local_declaration *l=fn->locals; l; l=l->next_local) save_local(s,l);
            for (const struct ast_load_expression *l=fn->record_temporaries; l; l=l->next_record_temporary) save_expression(s,&l->expression);
            break;
        }
        case external_declaration_tag: {
            const struct ast_external_tag_declaration *n=(const struct ast_external_tag_declaration *)d;
            (void)save(s,n,sizeof *n); (void)save(s,n->declaration,sizeof *n->declaration);
            save_syntax(s,n->declaration->type_syntax); break;
        }
        default: assert(!"extend explicit external snapshot walker");
        }
    }
    for (const struct ast_external_declaration *d=f->unit->static_declarations; d; d=d->next) {
        assert(d->kind==external_object_declaration);
        const struct ast_external_object_declaration *o=(const struct ast_external_object_declaration *)d;
        (void)save(s,o,sizeof *o); save_object(s,o->symbol);
        save_initializer(s,o->initializer_syntax); save_plan(s,o->initializer_plan);
    }
    return s;
}

static void unchanged(const struct snapshot *s)
{
    for (size_t i=0;i<s->count;++i)
        assert(memcmp(s->entries[i].address,s->entries[i].bytes,s->entries[i].size)==0);
}

static struct address_initializer_result pure_queries(struct fixture *f, const struct ast_expression *e)
{
    struct snapshot *s=capture(f);
    long position=ftell(f->stream); assert(position>=0);
    struct address_initializer_result first=evaluate_address_initializer(e);
    struct constant_result integer=evaluate_integer_constant(e);
    struct null_initializer_result null=evaluate_null_initializer(e);
    for (unsigned i=0;i<4;++i) {
        struct address_initializer_result a=evaluate_address_initializer(e);
        struct constant_result c=evaluate_integer_constant(e);
        struct null_initializer_result n=evaluate_null_initializer(e);
        assert(a.status==first.status && a.message==first.message && a.origin_type==first.origin_type);
        assert(a.location.source==first.location.source && a.location.offset==first.location.offset);
        assert(c.status==integer.status && c.type==integer.type && c.bits==integer.bits && c.message==integer.message);
        assert(n.status==null.status && n.message==null.message);
        if (a.status==constant_value) {
            assert(a.address.kind==first.address.kind && a.address.byte_addend==first.address.byte_addend);
            if (a.address.kind==static_address_object) assert(a.address.base.object==first.address.base.object);
            else if (a.address.kind==static_address_string) assert(a.address.base.string==first.address.base.string);
            else if (a.address.kind==static_address_function) assert(a.address.base.function==first.address.base.function);
            else {
                assert(a.address.kind==static_address_compound_literal);
                assert(a.address.base.compound_literal==first.address.base.compound_literal);
            }
        }
        unchanged(s); assert(ftell(f->stream)==position);
    }
    free(s); return first;
}

static struct ast_function *function(struct fixture *f, unsigned index)
{
    struct ast_external_declaration *d=declaration(f,index);
    assert(d->kind==external_function_definition); return (struct ast_function *)d;
}

static size_t local_count(const struct ast_function *fn)
{
    size_t count=0; for (const struct ast_local_declaration *l=fn->locals;l;l=l->next_local) ++count;
    return count;
}

static void check_plan(const struct ast_compound_literal_expression *n, uint64_t size)
{
    assert(n->expression.type && n->expression.is_lvalue);
    const struct ast_initializer_plan *p=n->initializer_plan;
    assert(p && p->type==n->expression.type && p->size==size && p->zero_fill);
    size_t count=0;
    const struct ast_initializer_plan_entry *last=NULL;
    for (const struct ast_initializer_plan_entry *e=p->entries;e;e=e->next) {
        ++count; assert(e->type && e->syntax && e->length>0);
        assert(e->offset<=size && e->length<=size-e->offset);
        if (e->kind==ast_initializer_write_expression) assert(e->expression);
        last=e;
    }
    assert(count==p->entry_count && last==p->tail);
}

static void check_static_owners(void)
{
    struct fixture f;
    open_fixture(&f,"int *first=&(int){42}; int *second=(int[]){19,23}+1; "
        "struct N { int *p; int x; }; struct N *third=&(struct N){.p=&(int){7},.x=40};");
    assert(sema_translation_unit(f.unit,&f.arena,&f.diagnostics));
    assert(!f.diagnostics.errors && !f.diagnostics.warnings);
    struct snapshot *s=capture(&f); assert(s->literal_count==4);
    size_t definitions=0;
    for (struct ast_external_declaration *d=f.unit->static_declarations;d;d=d->next) ++definitions;
    assert(definitions==4);
    for (size_t i=0;i<s->literal_count;++i) {
        const struct ast_compound_literal_expression *n=s->literals[i];
        assert(n->object_id && n->file_scope && n->storage==ast_compound_literal_static);
        assert(!n->local && n->object && n->object->is_internal && n->object->is_block_static);
        assert(!n->object->is_thread_local && n->object->initializer_plan==n->initializer_plan);
        assert(n->object->definition && n->object->definition->kind==external_object_declaration);
        const struct ast_external_object_declaration *d=(const struct ast_external_object_declaration *)n->object->definition;
        assert(d->symbol==n->object && d->initializer_syntax==n->initializer_syntax);
        assert(d->initializer_plan==n->initializer_plan && d->type==n->expression.type);
        check_plan(n,type_object_size(n->expression.type));
        if (n->expression.type->kind==type_kind_array) {
            assert(((const struct array_type *)n->expression.type)->count==2);
            assert(n->type_syntax->type->kind==type_kind_array);
            assert(((const struct array_type *)n->type_syntax->type)->count==0);
            assert(n->type_syntax->type!=n->expression.type);
        }
        for (size_t j=0;j<i;++j) assert(n->object_id!=s->literals[j]->object_id && n->object!=s->literals[j]->object);
        assert(pure_queries(&f,&n->expression).status==constant_not_constant);
    }
    const unsigned indices[]={0,1,3}; const int64_t offsets[]={0,4,0};
    for (unsigned i=0;i<3;++i) {
        struct ast_external_object_declaration *o=object(&f,indices[i]);
        struct address_initializer_result a=pure_queries(&f,o->initializer);
        assert(a.status==constant_value && a.address.kind==static_address_object && a.address.byte_addend==offsets[i]);
        bool found=false;
        for (size_t j=0;j<s->literal_count;++j) found|=a.address.base.object==s->literals[j]->object;
        assert(found);
    }
    unchanged(s); free(s); close_fixture(&f);
}

static void check_automatic_owners(void)
{
    struct fixture f;
    open_fixture(&f,"struct S { int x; int a[2]; }; int f(int n) { "
        "int *p=&(int){n}; struct S copy=(struct S){.x=40,.a={2}}; "
        "int *q=(int[]){19,23}; return *p+q[0]+copy.a[0]; }");
    assert(sema_translation_unit(f.unit,&f.arena,&f.diagnostics));
    struct ast_function *fn=function(&f,1); struct snapshot *s=capture(&f);
    assert(s->literal_count==3 && local_count(fn)==7 && !f.unit->static_declarations);
    for (size_t i=0;i<s->literal_count;++i) {
        const struct ast_compound_literal_expression *n=s->literals[i];
        assert(!n->file_scope && n->storage==ast_compound_literal_automatic && n->local && !n->object);
        assert(n->local->type==n->expression.type && !n->local->initializer && !n->local->initializer_plan);
        assert(!n->local->object_symbol);
        check_plan(n,type_object_size(n->expression.type));
        for (size_t j=0;j<i;++j) assert(n->local!=s->literals[j]->local && n->local->slot!=s->literals[j]->local->slot);
        assert(pure_queries(&f,&n->expression).status==constant_not_constant);
    }
    unchanged(s); free(s); close_fixture(&f);
}

static void check_unevaluated_and_storage(void)
{
    struct fixture f;
    open_fixture(&f,"unsigned long size=sizeof((int[]){1,2}); "
        "unsigned long tls_size=sizeof((thread_local int){42}); "
        "unsigned long ptr_size=sizeof((int *){&(int){1}}); "
        "int f(void) { int n=0; sizeof((int[]){++n,++n}); sizeof((char[]){\"abc\"}); "
        "typeof((int){++n}) value=42; sizeof((static int){42}); "
        "sizeof((static thread_local int){42}); return value; }");
    assert(sema_translation_unit(f.unit,&f.arena,&f.diagnostics));
    struct ast_function *fn=function(&f,3); struct snapshot *s=capture(&f);
    assert(s->literal_count==9 && local_count(fn)==2);
    assert(!fn->record_temporaries && !fn->record_temporary_count && !f.unit->static_declarations && !f.unit->strings);
    unsigned query_address_proofs=0;
    for (size_t i=0;i<s->literal_count;++i) {
        const struct ast_compound_literal_expression *n=s->literals[i];
        assert(n->initializer_plan && !n->local && !n->object);
        (void)pure_queries(&f,&n->expression);
        for (const struct ast_initializer_plan_entry *e=n->initializer_plan->entries;e;e=e->next) {
            if (e->constant.kind!=ast_initializer_constant_address) continue;
            ++query_address_proofs;
            struct address_initializer_result a=pure_queries(&f,e->expression);
            assert(a.status==constant_value && a.address.kind==static_address_compound_literal);
            assert(a.address.base.compound_literal && !a.address.base.compound_literal->object && !a.address.base.compound_literal->local);
            assert(e->constant.address_kind==ast_initializer_address_compound_literal);
            assert(e->constant.base.compound_literal==a.address.base.compound_literal && !a.address.byte_addend);
        }
    }
    assert(query_address_proofs==1);
    unchanged(s); free(s); close_fixture(&f);

    open_fixture(&f,"int f(void) { int a=(register int){42}; "
        "int *b=&(static int){40}; int *c=&(static thread_local int){7}; return a; }");
    assert(sema_translation_unit(f.unit,&f.arena,&f.diagnostics));
    s=capture(&f); assert(s->literal_count==3);
    unsigned registers=0,statics=0,threads=0;
    for (size_t i=0;i<s->literal_count;++i) {
        const struct ast_compound_literal_expression *n=s->literals[i];
        if (n->is_register) { ++registers; assert(n->local && n->local->is_register && !n->object); }
        else if (n->is_thread_local) { ++threads; assert(n->object && n->object->is_thread_local && n->storage==ast_compound_literal_thread); }
        else { ++statics; assert(n->is_static && n->object && n->storage==ast_compound_literal_static); }
    }
    assert(registers==1 && statics==1 && threads==1);
    free(s); close_fixture(&f);
}

static void check_rollback(void)
{
    struct fixture f;
    open_fixture(&f,"struct N { int *p; int x; }; "
        "struct N *p=&(struct N){.p=&(int){7},.x=missing};");
    struct snapshot *before=capture(&f); assert(before->literal_count==2);
    struct ast_compound_literal_expression saved[2];
    for (unsigned i=0;i<2;++i) saved[i]=*before->literals[i];
    assert(!sema_translation_unit(f.unit,&f.arena,&f.diagnostics) && f.diagnostics.errors==1);
    assert(!f.unit->static_declarations && !f.unit->strings);
    for (unsigned i=0;i<2;++i) assert(memcmp(before->literals[i],&saved[i],sizeof saved[i])==0);
    struct ast_external_object_declaration *o=object(&f,1);
    assert(!o->initializer_plan && !o->symbol);
    free(before); close_fixture(&f);

    open_fixture(&f,"extern int a[]; int a[]={1,missing};");
    assert(!sema_translation_unit(f.unit,&f.arena,&f.diagnostics));
    struct ast_external_object_declaration *prior=object(&f,0), *failed=object(&f,1);
    assert(prior->symbol && !prior->symbol->definition && !prior->symbol->initializer_plan);
    assert(prior->symbol->type->kind==type_kind_array && ((const struct array_type *)prior->symbol->type)->count==0);
    assert(!failed->initializer_plan);
    close_fixture(&f);
}

static void check_local_budget(bool unevaluated, unsigned count, bool success)
{
    char *text=calloc(1,128+(size_t)count*64); assert(text);
    strcpy(text,"int f(void) { ");
    for (unsigned i=0;i<count;++i) strcat(text,unevaluated?"sizeof((int){42}); ":"(void)&(int){42}; ");
    strcat(text,"return 42; }");
    struct fixture f; open_fixture(&f,text); free(text);
    assert(sema_translation_unit(f.unit,&f.arena,&f.diagnostics)==success);
    struct ast_function *fn=function(&f,0);
    if (success) assert(local_count(fn)==(unevaluated?0:count));
    else assert(f.diagnostics.errors==1 && local_count(fn)==ast_max_locals);
    assert(!f.unit->static_declarations); close_fixture(&f);
}

static void check_storage_budget(void)
{
    struct fixture f;
    open_fixture(&f,"int f(void) { (void)&(int[262144]){1}; return 42; }");
    assert(sema_translation_unit(f.unit,&f.arena,&f.diagnostics));
    struct ast_function *fn=function(&f,0); assert(local_count(fn)==1);
    assert(type_object_size(fn->locals->type)==ast_max_local_storage);
    close_fixture(&f);
    open_fixture(&f,"int f(void) { (void)&(int[262144]){1}; (void)&(int){1}; return 42; }");
    assert(!sema_translation_unit(f.unit,&f.arena,&f.diagnostics) && f.diagnostics.errors==1);
    assert(local_count(function(&f,0))==1); close_fixture(&f);
}

static void check_prototype_literal(void)
{
    struct fixture f;
    open_fixture(&f,"int g(int a[sizeof((int[]){1,2})]);");
    assert(sema_translation_unit(f.unit,&f.arena,&f.diagnostics));
    struct ast_external_declaration *d=declaration(&f,0);
    assert(d->kind==external_function_declaration);
    struct ast_function_declaration *fn=(struct ast_function_declaration *)d;
    const struct ast_array_type_syntax *array=(const struct ast_array_type_syntax *)fn->parameters->type_syntax;
    assert(array->syntax.kind==type_syntax_array && array->bound->kind==expression_sizeof);
    const struct ast_sizeof_expression *query=(const struct ast_sizeof_expression *)array->bound;
    assert(query->operand->kind==expression_compound_literal && query->size==8);
    const struct ast_compound_literal_expression *n=(const struct ast_compound_literal_expression *)query->operand;
    assert(n->initializer_plan && !n->local && !n->object && !f.unit->static_declarations);
    close_fixture(&f);
}

static void check_literal_parser_budget(unsigned count, bool success)
{
    char *text=calloc(1,256+(size_t)count*32); assert(text);
    strcpy(text,"int f(void) { ");
    for (unsigned i=0;i<count;++i) {
        if (i==count/2) strcat(text,"return 42; } int g(void) { ");
        strcat(text,"sizeof((int){42}); ");
    }
    strcat(text,"return 42; }");
    struct fixture f; open_fixture_mode(&f,text,success); free(text);
    if (success) {
        assert(sema_translation_unit(f.unit,&f.arena,&f.diagnostics));
        assert(local_count(function(&f,0))==0 && local_count(function(&f,1))==0);
        assert(!f.unit->static_declarations);
    }
    close_fixture(&f);
}

int main(void)
{
    check_static_owners(); check_automatic_owners(); check_unevaluated_and_storage();
    check_rollback(); check_local_budget(false,ast_max_locals,true);
    check_local_budget(false,ast_max_locals+1,false);
    check_local_budget(true,ast_max_locals+1,true); check_storage_budget();
    check_prototype_literal(); check_literal_parser_budget(ast_max_compound_literals,true);
    check_literal_parser_budget(ast_max_compound_literals+1,false);
    puts("M17 literal AST: owners/types/captures/plans pure; unevaluated storage absent; rollback/budgets");
    return 0;
}

/* M18 independent alignment syntax, metadata, layout and rollback oracle.
 * Link with all frozen source files except main.c. No host-ABI alignment guesses.
 */
#include "parse.h"
#include "sema.h"
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
    memset(f,0,sizeof *f);
    f->stream=tmpfile(); assert(f->stream);
    f->diagnostics.stream=f->stream;
    assert(source_from_bytes(&f->source,"alignment-ast.c",(const unsigned char *)text,strlen(text)));
    assert(source_prepare(&f->source));
    preprocess_init(&f->preprocessor,&f->source,&f->diagnostics);
    f->unit=parse_translation_unit(&f->preprocessor,&f->arena,&f->diagnostics);
    if(parsed && (!f->unit || f->diagnostics.errors)) {
        char message[1024]; size_t n;
        rewind(f->stream); n=fread(message,1,sizeof message-1,f->stream); message[n]=0;
        fprintf(stderr,"unexpected parse failure: %.100s: %s",text,message);
    }
    if(parsed) assert(f->unit && !f->diagnostics.errors);
    else assert(!f->unit && f->diagnostics.errors==1);
}

static void close_fixture(struct fixture *f)
{
    arena_destroy(&f->arena); preprocess_destroy(&f->preprocessor); source_destroy(&f->source);
    assert(fclose(f->stream)==0);
}

static struct ast_external_declaration *declaration(struct fixture *f,unsigned n)
{
    struct ast_external_declaration *d=f->unit->declarations;
    while(n--) { assert(d); d=d->next; } assert(d); return d;
}

static struct ast_external_object_declaration *object(struct fixture *f,unsigned n)
{
    struct ast_external_declaration *d=declaration(f,n);
    assert(d->kind==external_object_declaration);
    return (struct ast_external_object_declaration *)d;
}

static struct ast_function *function(struct fixture *f,unsigned n)
{
    struct ast_external_declaration *d=declaration(f,n);
    assert(d->kind==external_function_definition); return (struct ast_function *)d;
}

static void analyze(struct fixture *f)
{
    if(!sema_translation_unit(f->unit,&f->arena,&f->diagnostics)) {
        char message[1024]; size_t n;
        rewind(f->stream); n=fread(message,1,sizeof message-1,f->stream); message[n]=0;
        fprintf(stderr,"unexpected sema failure: %s",message); assert(0);
    }
    assert(!f->diagnostics.errors);
}

static void check_constructors_and_shared_syntax(void)
{
    struct arena arena={0}; struct source_location location={0};
    struct ast_alignment_specifier *node=ast_new_alignment_specifier(&arena,location,NULL,NULL);
    assert(node && !node->type_syntax && !node->expression && !node->next && !node->after_type_specifier);
    arena_destroy(&arena);
    struct fixture f;
    open_fixture(&f,"_Alignas(1) alignas(8) _Alignas(0) int x, *p;",true);
    struct ast_external_object_declaration *x=object(&f,0),*p=object(&f,1);
    struct ast_alignment_specifier *a=x->alignment_specifiers;
    assert(a && a==p->alignment_specifiers && a->expression && !a->type_syntax);
    assert(a->next && a->next->expression && a->next->next && !a->next->next->next);
    assert(a->location.offset<a->next->location.offset);
    assert(!x->alignment && !p->alignment);
    struct ast_alignment_specifier *second=a->next,*third=a->next->next;
    struct ast_expression *first_expression=a->expression;
    analyze(&f);
    assert(x->alignment==8 && p->alignment==8 && x->symbol->alignment==8 && p->symbol->alignment==8);
    assert(type_object_alignment(x->type)==4 && type_object_size(x->type)==4);
    assert(type_object_alignment(p->type)==8 && type_object_size(p->type)==8);
    assert(a==x->alignment_specifiers && a==p->alignment_specifiers && a->next==second && second->next==third);
    assert(a->expression==first_expression); /* Shared syntax not relowered twice. */
    close_fixture(&f);
    open_fixture(&f,"typedef long L; _Alignas(L) int cell;",true);
    x=object(&f,1); assert(x->alignment_specifiers->type_syntax && !x->alignment_specifiers->expression);
    analyze(&f); assert(x->alignment==8 && type_object_alignment(x->type)==4);
    close_fixture(&f);
}

static void check_alias_root_alignment(void)
{
    struct fixture f;
    open_fixture(&f,"typedef int I; _Alignas(16) I x,y;",true);
    struct ast_external_declaration *dx=declaration(&f,1),*dy=declaration(&f,2);
    assert(dx->kind==external_type_declaration && dy->kind==external_type_declaration);
    struct ast_external_type_declaration *x=(struct ast_external_type_declaration *)dx;
    struct ast_external_type_declaration *y=(struct ast_external_type_declaration *)dy;
    struct ast_alignment_specifier *a=x->alignment_specifiers;
    assert(a && a==y->alignment_specifiers && !x->alignment && !y->alignment);
    analyze(&f);
    assert(x->alignment==16 && y->alignment==16 && x->object_symbol->alignment==16 && y->object_symbol->alignment==16);
    assert(x->alignment_specifiers==a && y->alignment_specifiers==a);
    assert(type_object_size(x->type)==4 && type_object_alignment(x->type)==4);
    assert(type_object_size(y->type)==4 && type_object_alignment(y->type)==4);
    close_fixture(&f);
}

static void check_canonical_redeclarations(void)
{
    const char *texts[]={
        "_Alignas(16) int cell; int cell;",
        "int cell; _Alignas(16) int cell;",
        "_Alignas(0) int cell; _Alignas(16) int cell;",
        "_Alignas(16) extern int cell; int cell; _Alignas(16) int cell;",
        "_Alignas(0) extern int cell; _Alignas(16) int cell=42;",
        "_Alignas(4) _Alignas(16) extern int cell; _Alignas(16) int cell=42;",
    };
    for(unsigned n=0;n<sizeof texts/sizeof *texts;++n) {
        struct fixture f; open_fixture(&f,texts[n],true); analyze(&f);
        struct ast_external_object_declaration *first=object(&f,0),*last=first;
        for(struct ast_external_declaration *d=first->external.next;d;d=d->next) {
            assert(d->kind==external_object_declaration); last=(struct ast_external_object_declaration *)d;
            assert(last->symbol==first->symbol && type_object_alignment(last->type)==4);
        }
        assert(first->symbol && first->symbol->alignment==16 && first->symbol->requested_alignment==16);
        assert(type_object_size(first->symbol->type)==4 && type_object_alignment(first->symbol->type)==4);
        assert(first->symbol->definition || first->symbol->tentative_definition);
        close_fixture(&f);
    }
    struct fixture f;
    open_fixture(&f,"_Alignas(0) int cell; int cell;",true); analyze(&f);
    assert(object(&f,0)->symbol==object(&f,1)->symbol && object(&f,0)->symbol->alignment==4);
    assert(!object(&f,0)->symbol->requested_alignment);
    close_fixture(&f);
}

static void check_record_layout(void)
{
    struct fixture f;
    open_fixture(&f,"struct R { char a; _Alignas(16) int n; char b; }; struct R cell[2];",true);
    analyze(&f);
    const struct type *array=object(&f,1)->type;
    assert(array->kind==type_kind_array);
    const struct type *record=((const struct array_type *)array)->element;
    struct record_definition *r=type_record_definition(record);
    assert(r && r->complete && r->alignment==16 && r->size==32 && r->member_count==3);
    struct record_member *a=r->members,*n=a->next,*b=n->next;
    assert(a->offset==0 && n->offset==16 && b->offset==20);
    assert(n->alignment==16 && type_object_alignment(n->type)==4 && type_object_size(n->type)==4);
    assert(type_object_size(array)==64 && type_object_alignment(array)==16);
    assert(object(&f,1)->alignment==16);
    close_fixture(&f);
    open_fixture(&f,"union U { char c; _Alignas(16) int n; }; union U cell;",true); analyze(&f);
    r=type_record_definition(object(&f,1)->type);
    assert(r && r->complete && r->size==16 && r->alignment==16);
    assert(r->members->offset==0 && r->members->next->offset==0);
    close_fixture(&f);
}

static void check_parameter_adjustment(void)
{
    struct fixture f;
    open_fixture(&f,"int f(int *); int f(_Alignas(16) int a[2]) { return a[0]; }",true);
    struct ast_function *fn=function(&f,1);
    struct ast_parameter *p=fn->declaration->parameters;
    assert(p && p->alignment_specifiers && !p->alignment);
    analyze(&f);
    assert(p->alignment==16 && p->local && p->local->alignment==16);
    assert(p->type->kind==type_kind_pointer && type_object_alignment(p->type)==8 && type_object_size(p->type)==8);
    assert(p->local->type==p->type);
    struct ast_function_declaration *prior=(struct ast_function_declaration *)declaration(&f,0);
    assert(prior->symbol==fn->declaration->symbol);
    assert(prior->symbol->type->parameter_count==1);
    assert(type_object_alignment(prior->symbol->type->parameters->type)==8);
    close_fixture(&f);
    open_fixture(&f,"int f(_Alignas(16) int x) { return x; }",true); analyze(&f);
    p=function(&f,0)->declaration->parameters;
    assert(p->alignment==16 && p->local->alignment==16 && type_object_alignment(p->type)==4);
    close_fixture(&f);
}

static void check_literal_and_query_storage(void)
{
    struct fixture f;
    open_fixture(&f,"int f(void) { _Alignas(8) int x=(_Alignas(16) int){42}; return x; }",true);
    struct ast_function *fn=function(&f,0);
    struct ast_local_declaration *local=(struct ast_local_declaration *)fn->body->items;
    assert(local->item.kind==block_item_declaration);
    struct ast_compound_literal_expression *literal=(struct ast_compound_literal_expression *)local->initializer_syntax->expression;
    assert(literal->expression.kind==expression_compound_literal && literal->alignment_specifiers && !literal->alignment);
    struct ast_alignment_specifier *syntax=literal->alignment_specifiers;
    analyze(&f);
    assert(local->alignment==8 && literal->alignment==16 && literal->local && literal->local->alignment==16);
    assert(type_object_alignment(local->type)==4 && type_object_alignment(literal->expression.type)==4);
    assert(literal->initializer_plan && literal->initializer_plan->size==4 && literal->alignment_specifiers==syntax);
    close_fixture(&f);
    const char *queries[]={
        "int f(void) { return sizeof((_Alignas(16) int){42}); }",
        "int f(void) { return sizeof((static _Alignas(16) int){42}); }",
        "int f(void) { return sizeof((static _Thread_local _Alignas(16) int){42}); }",
    };
    for(unsigned i=0;i<sizeof queries/sizeof *queries;++i) {
        open_fixture(&f,queries[i],true); analyze(&f); fn=function(&f,0);
        assert(!fn->locals && !f.unit->static_declarations && !f.unit->strings);
        close_fixture(&f);
    }
}

static void check_failed_publication(void)
{
    struct fixture f;
    open_fixture(&f,"extern int cell; _Alignas(16) int cell=missing;",true);
    struct ast_external_object_declaration *first=object(&f,0),*bad=object(&f,1);
    assert(!sema_translation_unit(f.unit,&f.arena,&f.diagnostics) && f.diagnostics.errors==1);
    assert(first->symbol && first->symbol->alignment==4 && !first->symbol->requested_alignment);
    assert(!first->symbol->definition && !first->symbol->initializer_plan);
    assert(!bad->symbol && !bad->type && !bad->initializer_plan && !bad->alignment);
    assert(!f.unit->static_declarations && !f.unit->strings);
    close_fixture(&f);
    open_fixture(&f,"_Alignas(8) int cell=42; _Alignas(16) int cell=missing;",true);
    first=object(&f,0); bad=object(&f,1);
    assert(!sema_translation_unit(f.unit,&f.arena,&f.diagnostics) && f.diagnostics.errors==1);
    assert(first->symbol && first->symbol->alignment==8 && first->symbol->requested_alignment==8);
    assert(first->symbol->definition==&first->external && first->symbol->initializer_value.integer_bits==42);
    assert(!bad->symbol && !bad->type && !bad->initializer_plan && !bad->alignment);
    close_fixture(&f);
    open_fixture(&f,"extern int *cell; _Alignas(16) int *cell=&(_Alignas(16) int){missing};",true);
    first=object(&f,0); bad=object(&f,1);
    assert(!sema_translation_unit(f.unit,&f.arena,&f.diagnostics) && f.diagnostics.errors==1);
    assert(first->symbol && first->symbol->alignment==8 && !first->symbol->requested_alignment);
    assert(!first->symbol->definition && !first->symbol->initializer_plan);
    assert(!bad->symbol && !bad->type && !bad->alignment && !bad->initializer_plan);
    assert(!f.unit->static_declarations && !f.unit->strings);
    close_fixture(&f);
    open_fixture(&f,"struct R { char c; _Alignas(16) int n; _Alignas(3) int bad; };",true);
    struct ast_external_tag_declaration *tag=(struct ast_external_tag_declaration *)declaration(&f,0);
    assert(tag->external.kind==external_declaration_tag);
    struct ast_type_syntax *syntax=tag->declaration->type_syntax;
    assert(!sema_translation_unit(f.unit,&f.arena,&f.diagnostics) && f.diagnostics.errors==1);
    assert(!syntax->type || !type_record_definition(syntax->type)->complete);
    close_fixture(&f);
}

static void check_alignment_source_order(void)
{
    const char *valid[]={
        "_Alignas(sizeof(enum E { A=2 })) int x[A], y[A];",
        "int _Alignas(sizeof(enum E { A=2 })) x[A], y[A];",
        "#define REQUEST _Alignas(sizeof(enum E { A=2 }))\nREQUEST int x[A], y[A];",
    };
    for(unsigned i=0;i<sizeof valid/sizeof *valid;++i) {
        struct fixture f; open_fixture(&f,valid[i],true);
        struct ast_external_object_declaration *x=object(&f,0),*y=object(&f,1);
        struct ast_alignment_specifier *a=x->alignment_specifiers;
        assert(a && a==y->alignment_specifiers && a->after_type_specifier==(i==1));
        analyze(&f);
        assert(x->alignment==4 && y->alignment==4 && x->alignment_specifiers==a && y->alignment_specifiers==a);
        assert(type_object_size(x->type)==8 && type_object_size(y->type)==8);
        assert(type_object_alignment(x->type)==4 && type_object_alignment(y->type)==4);
        close_fixture(&f);
    }
    struct fixture f;
    open_fixture(&f,"enum { A=16 } _Alignas(A) x;",true);
    assert(object(&f,0)->alignment_specifiers->after_type_specifier);
    analyze(&f); assert(object(&f,0)->alignment==16 && type_object_alignment(object(&f,0)->type)==4);
    close_fixture(&f);
    open_fixture(&f,"struct R { int _Alignas(sizeof(enum { A=2 })) x[A]; }; struct R cell;",true);
    analyze(&f);
    struct record_definition *r=type_record_definition(object(&f,1)->type);
    assert(r && r->complete && r->size==8 && r->alignment==4);
    assert(type_object_size(r->members->type)==8);
    close_fixture(&f);
    const char *invalid[]={
        "_Alignas(A) enum { A=16 } x;",
        "int f(void) { _Alignas(A) enum { A=16 } x; return 0; }",
        "struct R { _Alignas(A) enum { A=16 } x; };",
        "int f(_Alignas(A) enum { A=16 } x) { return 0; }",
        "int f(void) { return (_Alignas(A) enum { A=16 }){42}; }",
        "#define REQUEST _Alignas(A)\nREQUEST enum { A=16 } x;",
    };
    for(unsigned i=0;i<sizeof invalid/sizeof *invalid;++i) {
        open_fixture(&f,invalid[i],true);
        assert(!sema_translation_unit(f.unit,&f.arena,&f.diagnostics) && f.diagnostics.errors==1);
        char message[512]; size_t n;
        rewind(f.stream); n=fread(message,1,sizeof message-1,f.stream); message[n]=0;
        assert(strstr(message,": error: use of undeclared identifier\n"));
        assert(!f.unit->strings && !f.unit->static_declarations);
        close_fixture(&f);
    }
}

static void check_parser_budget_and_placement(void)
{
    char *text=malloc(60000); assert(text);
    for(unsigned extra=0;extra<2;++extra) {
        char *p=text;
        for(unsigned n=0;n<ast_max_alignment_specifiers+extra;++n) { memcpy(p,"_Alignas(0) ",12); p+=12; }
        strcpy(p,"int cell;");
        struct fixture f; open_fixture(&f,text,!extra);
        if(!extra) { analyze(&f); assert(object(&f,0)->alignment==4); }
        close_fixture(&f);
    }
    free(text);
    const char *bad[]={"int f(void) { return (_Alignas(16) int)42; }",
        "unsigned long x=sizeof(_Alignas(16) int);", "unsigned long x=_Alignof(_Alignas(16) int);"};
    for(unsigned n=0;n<sizeof bad/sizeof *bad;++n) {
        struct fixture f; open_fixture(&f,bad[n],false); close_fixture(&f);
    }
}

int main(void)
{
    check_constructors_and_shared_syntax(); check_alias_root_alignment(); check_canonical_redeclarations();
    check_record_layout(); check_parameter_adjustment(); check_literal_and_query_storage();
    check_failed_publication(); check_alignment_source_order(); check_parser_budget_and_placement();
    puts("M18 alignment AST metadata/layout/rollback checks passed");
    return 0;
}

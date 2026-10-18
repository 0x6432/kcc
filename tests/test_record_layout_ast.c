/* Independent M16 nominal identity/layout/source-point/rollback tests.
 * Build with compiler sources excluding main.c. Assertions must stay enabled.
 * No aggregate by-value ABI, braced source initializers, bitfields or flex arrays.
 */
#include "parse.h"
#include "sema.h"
#include "type.h"
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

_Static_assert(offsetof(struct record_type, type) == 0, "record base first");
_Static_assert(offsetof(struct ast_record_type_syntax, syntax) == 0, "syntax base first");
_Static_assert(offsetof(struct ast_member_expression, expression) == 0, "member base first");
_Static_assert(offsetof(struct ast_external_tag_declaration, external) == 0, "tag base first");
_Static_assert(offsetof(struct ast_block_tag_declaration, item) == 0, "block tag base first");

struct fixture {
 struct source source;
 struct arena arena;
 FILE *stream;
 struct diagnostics diagnostics;
 struct preprocessor preprocessor;
 struct ast_translation_unit *unit;
};

static void open_fixture(struct fixture *f, const char *text)
{
 memset(f, 0, sizeof *f);
 f->stream = tmpfile(); assert(f->stream);
 f->diagnostics.stream = f->stream;
 assert(source_from_bytes(&f->source, "record-ast.c", (const unsigned char *)text, strlen(text)));
 assert(source_prepare(&f->source));
 preprocess_init(&f->preprocessor, &f->source, &f->diagnostics);
 f->unit = parse_translation_unit(&f->preprocessor, &f->arena, &f->diagnostics);
 assert(f->unit && !f->diagnostics.errors);
}

static void close_fixture(struct fixture *f)
{
 arena_destroy(&f->arena); preprocess_destroy(&f->preprocessor);
 source_destroy(&f->source); assert(fclose(f->stream) == 0);
}

static bool named(const struct token *t, const char *name)
{
 return t->length == strlen(name) && t->spelling_location.source &&
  memcmp(t->spelling_location.source->data + t->spelling_location.offset, name, t->length) == 0;
}

static struct ast_external_object_declaration *object(struct fixture *f, const char *name, unsigned occurrence)
{
 for (struct ast_external_declaration *d=f->unit->declarations; d; d=d->next)
  if (d->kind == external_object_declaration) {
   struct ast_external_object_declaration *o=(struct ast_external_object_declaration *)d;
   if (named(&o->name, name) && occurrence-- == 0) return o;
  }
 assert(!"missing object"); return NULL;
}

static const struct type *declared_type(struct fixture *f, const char *name)
{
 for (struct ast_external_declaration *d=f->unit->declarations;d;d=d->next)
  if (d->kind==external_type_declaration) {
   struct ast_external_type_declaration *o=(struct ast_external_type_declaration *)d;
   if (named(&o->name,name)) return o->type;
  }
 return object(f,name,0)->type;
}

static const struct type *referent(const struct type *t)
{
 assert(t && t->kind == type_kind_pointer);
 return ((const struct pointer_type *)t)->referent;
}

static const struct record_member *member(const struct type *t, const char *name, uint64_t wanted)
{
 struct record_definition *d=type_record_definition(t);
 assert(d && d->complete);
 for (struct record_member *m=d->members; m; m=m->next)
  if (named(&m->name,name)) { assert(m->offset==wanted); return m; }
 assert(!"missing member"); return NULL;
}

static void canonical_identity(void)
{
 struct fixture f;
 open_fixture(&f, "struct R; struct R *early; typedef struct R Alias; "
  "struct R { char c; int n; struct R *next; }; struct R value; "
  "const struct R *qualified; Alias *alias; struct R *late; "
  "struct Other { char c; int n; struct R *next; }; struct Other other; "
  "struct { int x; } a; struct { int x; } b;");
 assert(sema_translation_unit(f.unit,&f.arena,&f.diagnostics));
 const struct type *r=object(&f,"value",0)->type;
 const struct type *early=referent(object(&f,"early",0)->type);
 const struct type *q=referent(object(&f,"qualified",0)->type);
 struct record_definition *identity=type_record_definition(r);
 assert(identity && identity->complete && identity->size==16 && identity->alignment==8);
 assert(type_record_definition(early)==identity);
 assert(type_record_definition(q)==identity && (q->qualifiers&type_qualifier_const));
 assert(type_record_definition(referent(declared_type(&f,"alias")))==identity);
 assert(type_record_definition(referent(object(&f,"late",0)->type))==identity);
 assert(type_compatible(r,early));
 assert(!type_compatible(r,object(&f,"other",0)->type));
 assert(!type_compatible(object(&f,"a",0)->type,object(&f,"b",0)->type));
 assert(member(r,"c",0)->type->kind==type_kind_char);
 assert(member(r,"n",4)->type->kind==type_kind_int);
 assert(type_record_definition(referent(member(r,"next",8)->type))==identity);
 unsigned char saved[sizeof(struct record_type)]; memcpy(saved,q,sizeof saved);
 assert(type_object_size(q)==16 && type_object_alignment(q)==8);
 assert(type_is_complete_object(q) && !type_is_scalar(q));
 assert(type_composite(&f.arena,r,early));
 assert(memcmp(saved,q,sizeof saved)==0);
 close_fixture(&f);
}

static void layout_transaction(void)
{
 struct arena a={0};
 struct record_type *r=type_new_record(&a,false), *other=type_new_record(&a,false);
 assert(r && other && !type_compatible(&r->type,&other->type));
 const struct type *qualified=type_qualified(&a,&r->type,type_qualifier_const);
 assert(qualified && type_record_definition(qualified)==r->definition);
 unsigned char view[sizeof(struct record_type)]; memcpy(view,qualified,sizeof view);
 assert(!type_is_complete_object(&r->type));
 struct record_member first={0}, second={0};
 first.type=&type_char; first.offset=111; first.next=&second;
 second.type=&other->type; second.offset=222;
 r->definition->members=&first; r->definition->member_count=2;
 struct record_definition before=*r->definition;
 assert(!type_record_layout(r->definition));
 assert(memcmp(&before,r->definition,sizeof before)==0);
 assert(first.offset==111 && second.offset==222);
 assert(memcmp(view,qualified,sizeof view)==0);
 second.type=&type_long;
 assert(type_record_layout(r->definition));
 assert(first.offset==0 && second.offset==8 && r->definition->size==16 && r->definition->alignment==8);
 assert(type_object_size(qualified)==16 && memcmp(view,qualified,sizeof view)==0);
 /* Repeated queries neither alter layout nor allocate/mutate arena state. */
 before=*r->definition; struct arena_chunk *chunks=a.chunks;
 for (unsigned i=0;i<100;i++) {
  assert(type_object_size(qualified)==16 && type_object_alignment(qualified)==8);
  assert(type_compatible(qualified,qualified));
 }
 assert(a.chunks==chunks && memcmp(&before,r->definition,sizeof before)==0);
 /* Checked arithmetic and storage-limit failures must not partially publish. */
 struct array_type *huge=type_new_array(&a,&type_long,UINT64_MAX);
 assert(huge);
 struct record_type *bad=type_new_record(&a,false);
 struct record_member giant={0}; giant.type=&huge->type; giant.offset=123;
 bad->definition->members=&giant; bad->definition->member_count=1;
 before=*bad->definition;
 assert(!type_record_layout(bad->definition));
 assert(memcmp(&before,bad->definition,sizeof before)==0 && giant.offset==123);
 arena_destroy(&a);
}

static void layout_boundaries(void)
{
 struct arena a={0};
 struct record_type *u=type_new_record(&a,true);
 struct array_type *bytes=type_new_array(&a,&type_char,9);
 struct record_member first={0}, second={0};
 assert(u && bytes);
 first.type=&type_long; first.next=&second; second.type=&bytes->type;
 u->definition->members=&first; u->definition->member_count=2;
 assert(type_record_layout(u->definition));
 assert(first.offset==0 && second.offset==0 && u->definition->size==16 && u->definition->alignment==8);
 struct record_type *r=type_new_record(&a,false);
 struct array_type *elements=type_new_array(&a,&u->type,3);
 struct record_member nested={0}, tail={0};
 nested.type=&elements->type; nested.next=&tail; tail.type=&type_char;
 r->definition->members=&nested; r->definition->member_count=2;
 assert(type_record_layout(r->definition));
 assert(nested.offset==0 && tail.offset==48 && r->definition->size==56);
 struct record_type *maximum=type_new_record(&a,false);
 struct array_type *limit=type_new_array(&a,&type_char,type_max_record_size);
 struct record_member full={0}; full.type=&limit->type;
 maximum->definition->members=&full;
 assert(type_record_layout(maximum->definition));
 assert(maximum->definition->size==type_max_record_size);
 struct record_type *excess=type_new_record(&a,false);
 struct record_member too_full={0}, one_more={0};
 too_full.type=&limit->type; too_full.offset=91; too_full.next=&one_more;
 one_more.type=&type_char; one_more.offset=92;
 excess->definition->members=&too_full;
 struct record_definition before=*excess->definition;
 assert(!type_record_layout(excess->definition));
 assert(memcmp(&before,excess->definition,sizeof before)==0);
 assert(too_full.offset==91 && one_more.offset==92);
 arena_destroy(&a);
}

static void incomplete_at_sourcepoint(void)
{
 const char *texts[]={
  "struct R; int n=sizeof(struct R); struct R { int x; };",
  "struct R; int n=_Alignof(struct R); struct R { int x; };",
  "struct R; struct R a[2]; struct R { int x; };",
  "struct R; int f(void) { struct R a; return 0; } struct R { int x; };",
  "struct R { long x; }; int f(void) { struct R; return sizeof(struct R); }",
 };
 for (size_t i=0;i<sizeof texts/sizeof texts[0];i++) {
  struct fixture f; open_fixture(&f,texts[i]);
  assert(!sema_translation_unit(f.unit,&f.arena,&f.diagnostics));
  assert(f.diagnostics.errors==1); close_fixture(&f);
 }
}

static void failed_publication(void)
{
 struct fixture f;
 open_fixture(&f,"struct R { int x; }; struct R cell; struct S { int x; }; extern struct S cell;");
 assert(!sema_translation_unit(f.unit,&f.arena,&f.diagnostics));
 assert(f.diagnostics.errors==1);
 struct ast_external_object_declaration *first=object(&f,"cell",0), *failed=object(&f,"cell",1);
 assert(first->symbol && !failed->symbol && !failed->type);
 assert(first->symbol->type==first->type && first->symbol->file_type==first->type);
 assert(first->symbol->tentative_definition==&first->external && !first->symbol->definition);
 assert(type_object_size(first->type)==4 && type_object_alignment(first->type)==4);
 assert(first->symbol->next==NULL);
 close_fixture(&f);
}

static struct ast_function_declaration *function(struct fixture *f, const char *name)
{
 for (struct ast_external_declaration *d=f->unit->declarations;d;d=d->next) {
  struct ast_function_declaration *fn=NULL;
  if (d->kind==external_function_declaration) fn=(struct ast_function_declaration *)d;
  if (d->kind==external_function_definition) fn=((struct ast_function *)d)->declaration;
  if (fn && named(&fn->name,name)) return fn;
 }
 assert(!"missing function"); return NULL;
}

static void tag_scopes(void)
{
 struct fixture f;
 open_fixture(&f,"int f(struct Proto *); int g(struct Proto *); struct Proto { int x; }; struct Proto *file; "
  "int body(struct Body { int n; } *p) { struct Body *q=p; return q->n; } "
  "struct Body { long n; }; struct Body outside;");
 assert(sema_translation_unit(f.unit,&f.arena,&f.diagnostics));
 const struct type *a=referent(function(&f,"f")->parameters->type);
 const struct type *b=referent(function(&f,"g")->parameters->type);
 const struct type *file=referent(object(&f,"file",0)->type);
 assert(type_is_record(a) && type_is_record(b) && type_is_record(file));
 assert(!type_compatible(a,b) && !type_compatible(a,file) && !type_compatible(b,file));
 assert(!type_is_complete_object(a) && !type_is_complete_object(b));
 assert(type_is_complete_object(file));
 const struct type *body=referent(function(&f,"body")->parameters->type);
 assert(type_object_size(body)==4 && type_object_size(object(&f,"outside",0)->type)==8);
 assert(!type_compatible(body,object(&f,"outside",0)->type));
 close_fixture(&f);
}

static void member_captures(void)
{
 struct fixture f;
 open_fixture(&f,"struct R { char lead; union { long wide; int n; }; const int fixed; int *p; }; "
  "const struct R cell; const long *capture=&cell.wide; const int *fixed=&cell.fixed; "
  "int *const *pointer=&cell.p;");
 assert(sema_translation_unit(f.unit,&f.arena,&f.diagnostics));
 struct ast_external_object_declaration *capture=object(&f,"capture",0);
 assert(capture->initializer->kind==expression_address);
 struct ast_address_expression *address=(struct ast_address_expression *)capture->initializer;
 assert(address->operand->kind==expression_member);
 struct ast_member_expression *m=(struct ast_member_expression *)address->operand;
 assert(!m->indirect && m->offset==8 && m->member);
 assert(m->expression.type->kind==type_kind_long);
 assert(m->expression.type->qualifiers&type_qualifier_const);
 assert(m->expression.is_lvalue);
 struct ast_member_expression saved=*m;
 struct record_definition def=*type_record_definition(object(&f,"cell",0)->type);
 struct static_address before=capture->symbol->initializer_value.address;
 assert(capture->symbol->initializer_value.kind==static_data_address);
 for (unsigned i=0;i<100;i++) {
  assert(type_object_size(m->expression.type)==8);
  assert(type_record_definition(object(&f,"cell",0)->type)->size==32);
 }
 assert(memcmp(&saved,m,sizeof saved)==0);
 assert(memcmp(&def,type_record_definition(object(&f,"cell",0)->type),sizeof def)==0);
 assert(memcmp(&before,&capture->symbol->initializer_value.address,sizeof before)==0);
 const struct type *pp=referent(object(&f,"pointer",0)->type);
 assert(pp->kind==type_kind_pointer && (pp->qualifiers&type_qualifier_const));
 assert(!(referent(pp)->qualifiers&type_qualifier_const));
 close_fixture(&f);
}

static void member_static_assertions(void)
{
 struct fixture f;
 open_fixture(&f,"struct I { short x; }; struct R { char a; "
  "_Static_assert(sizeof(struct I)==2, \"prior complete\"); int b; "
  "_Static_assert(sizeof(int)==4, \"int\"); }; struct R cell;");
 assert(sema_translation_unit(f.unit,&f.arena,&f.diagnostics));
 struct record_definition *d=type_record_definition(object(&f,"cell",0)->type);
 assert(d && d->complete && d->member_count==2 && d->size==8 && d->alignment==4);
 assert(member(object(&f,"cell",0)->type,"b",4));
 close_fixture(&f);
 const char *bad[]={
  "struct R { int x; _Static_assert(0, \"record false\"); }; struct R *p;",
  "struct I; struct R { _Static_assert(sizeof(struct I)==4, \"incomplete\"); int x; }; struct I { int x; };",
  "struct R { int x; _Static_assert(sizeof(struct R)==4, \"self incomplete\"); };",
 };
 for (size_t i=0;i<sizeof bad/sizeof bad[0];i++) {
  open_fixture(&f,bad[i]);
  assert(!sema_translation_unit(f.unit,&f.arena,&f.diagnostics));
  assert(f.diagnostics.errors==1); close_fixture(&f);
 }
}

int main(void)
{
 canonical_identity(); layout_transaction(); layout_boundaries(); incomplete_at_sourcepoint(); failed_publication();
 tag_scopes(); member_captures(); member_static_assertions();
 puts("Record AST canonical identity, layout transactions, sourcepoint guards and publication passed");
 return 0;
}

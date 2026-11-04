# Generic selection

Expression-controlled `_Generic` selects an association by the controlling
expression's converted type, without evaluating the control. Association
types must be distinct compatible complete object types; one `default` is
allowed. All association expressions are checked, but only the selected one
is evaluated. The selected expression retains its lvalue, function designator,
or void behavior in the surrounding context.

The parser limits a selection to 128 associations and applies the ordinary
expression-depth limit. The later C2y type-name controlling form and variable-length
association types are not implemented. This compiler build succeeded; the
added positive, negative and QBE runtime cases have not been run.
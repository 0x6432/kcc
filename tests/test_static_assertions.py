"""Translation-time ICE requirements, diagnostic bytes, scopes and QBE erasure."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')


def accepts(text):
    return subprocess.run([host, '-std=c2x', '-pedantic-errors', '-x', 'c', '-fsyntax-only', '-'],
                          input=text + '\n', capture_output=True, text=True, timeout=10).returncode == 0


native_keyword = accepts('static_assert(1,"keyword");')
native_boolean = accepts('_Static_assert(sizeof(true)==1,"boolean"); bool flag;')
native_alignof = accepts('_Static_assert(alignof(int)==4,"alignment");')
native_for_assertion = accepts('int f(void) { for(_Static_assert(1,"for");0;) ; return 42; }')
prefix = '' if native_keyword else '#define static_assert _Static_assert\n'
if not native_boolean:
    prefix += '#define bool _Bool\n#define true ((_Bool)1)\n#define false ((_Bool)0)\n'
if not native_alignof:
    prefix += '#define alignof _Alignof\n'
integers = ['_Bool', 'char', 'signed char', 'unsigned char', 'short', 'unsigned short',
            'int', 'unsigned', 'long', 'unsigned long', 'long long', 'unsigned long long']
programs = [f'static_assert(({name})1,"file"); int main(void) {{ '
            f'_Static_assert(sizeof({name})==sizeof({name}),"block"); return 42; }}' for name in integers]
numeric_message_program = 'static_assert(1,"a\\0" "b\\n\\\"\\\\%s"); int main(void) { _Static_assert(1,""); return 42; }'
programs += [
    'static_assert(-1); _Static_assert(1ULL<<63); static_assert(18446744073709551615ULL); '
    'int main(void) { static_assert(true); _Static_assert(!false); return 42; }',
    'static_assert(0U-1U); static_assert(4294967295U+1U==0); '
    'int main(void) { static_assert(18446744073709551615ULL*18446744073709551615ULL==1); return 42; }',
    'static_assert((unsigned char)256==0); static_assert((bool)(1ULL<<63)); '
    'int main(void) { static_assert((short)-1==-1); return 42; }',
    'static_assert(1?42:1/0); static_assert(0?1ULL<<64:42); '
    'static_assert(1?42:2147483647+1); int main(void) { static_assert(1 || 1/0); return 42; }',
    'static_assert(0?(1,2):42); static_assert(1 || (1,2)); '
    'int main(void) { static_assert(1?42:(0?(3,4):(5,6))); return 42; }',
    'static_assert(sizeof(int[2][3])==24); static_assert(alignof(const long)==8); '
    'int main(void) { int a[2]; static_assert(sizeof a==8); return 42; }',
    'int missing(void); static_assert(sizeof missing()==4); '
    'int main(void) { int x; static_assert(sizeof(x=1)==4); static_assert(sizeof(1/0)==4); return 42; }',
    'int f(int x) { static_assert(sizeof x==4); { short x; _Static_assert(sizeof x==2); } '
    'static_assert(sizeof x==4); return x; } static_assert(sizeof f(0)==4); int main(void) { return f(42); }',
    'int main(void) { return 42; static_assert(1,"unreachable"); }',
    'int main(void) { if(0) { static_assert(1); } else { _Static_assert(1); } return 42; }',
    numeric_message_program,
    '#define CHECK static_assert\n#define MSG "macro " "message"\n'
    '#define CAT(a,b) a##b\nCHECK(1,MSG); int main(void) { CAT(static_,assert)(1); return 42; }',
]
for_program = 'int main(void) { int x=42; for(static_assert(sizeof x==4,"for");0;) ; return x; }'
# Object-like compatibility macros would change these defined/undef checks.
pp_program = '#if defined(static_assert) || defined(_Static_assert)\n#error not builtin macros\n#endif\n' \
             '#define static_assert _Static_assert\nstatic_assert(1,"expanded");\n#undef static_assert\n' \
             'int main(void) { static_assert(1); return 42; }'
constraints = [
    ('static_assert(0);', 'static assertion failed'),
    ('_Static_assert(false,"zero");', 'static assertion failed: "zero"'),
    ('static_assert((unsigned char)256);', 'static assertion failed'),
    ('static_assert(0 && 1/0);', 'static assertion failed'),
    ('static_assert(1/0);', 'division by zero'),
    ('static_assert(1%0);', 'division by zero'),
    ('static_assert(2147483647+1);', 'signed overflow'),
    ('static_assert(-(-2147483647-1));', 'signed overflow'),
    ('static_assert((-9223372036854775807LL-1LL)/-1LL);', 'signed overflow'),
    ('static_assert(1ULL<<64);', 'invalid shift count'),
    ('static_assert(1<<-1);', 'invalid shift count'),
    ('static_assert(-1<<1);', 'negative left operand'),
    ('static_assert(1<<31);', 'signed overflow'),
    ('int f(int x) { static_assert(x); return 0; }', 'not an integer constant expression'),
    ('int f(void) { const int x=1; static_assert(x); return 0; }', 'not an integer constant expression'),
    ('int f(int x) { static_assert(1?1:x); return 0; }', 'not an integer constant expression'),
    ('int f(int x) { static_assert(0 || x); return 0; }', 'not an integer constant expression'),
    ('int f(int x) { static_assert(1 || x); return 0; }', 'not an integer constant expression'),
    ('int f(void); static_assert(1 || f());', 'not an integer constant expression'),
    ('int f(void); static_assert(f());', 'not an integer constant expression'),
    ('int f(int x) { static_assert(1?1:(x=1)); return 0; }', 'not an integer constant expression'),
    ('static_assert((1,42));', 'evaluated comma'),
    ('int f(int x) { static_assert(&x); return 0; }', 'requires integer operands'),
    ('static_assert("literal");', 'requires integer operands'),
    ('int f(void); static_assert(f);', 'requires integer operands'),
    ('static_assert(sizeof later()==4); int later(void);', 'undeclared function'),
    ('int f(void) { static_assert(sizeof x==4); int x; return 0; }', 'undeclared identifier'),
    ('int f(void) { { int x; } static_assert(sizeof x==4); return 0; }', 'undeclared identifier'),
    ('int f(void) { return 0; static_assert(0,"unreachable"); }', 'unreachable'),
    ('int f(void) { if(0) { static_assert(0,"skipped"); } return 0; }', 'skipped'),
    ('int f(void) { for(static_assert(0,"for");0;) ; return 0; }', 'static assertion failed'),
    ('static_assert();', 'expected'),
    ('static_assert(1,);', 'expected string literal'),
    ('static_assert(1,42);', 'expected string literal'),
    ('static_assert(1,("message"));', 'expected string literal'),
    ('static_assert(1,"one","two");', "expected ')'"),
    ('static_assert(1)', "expected ';'"),
    ('static_assert(1=1);', "expected ')'"),
    ('int f(void) { if(1) static_assert(1); return 0; }', 'not a statement'),
]
strict_rejections = ['int f(int x) { _Static_assert(x,"form"); return 0; }',
                     'int f(int x) { _Static_assert(1||x,"form"); return 0; }',
                     'int f(void); _Static_assert(1||f(),"form");', '_Static_assert((1,42),"form");']

with tempfile.TemporaryDirectory(prefix='kcc static assertions ') as directory:
    directory = Path(directory)
    source, native, il, assembly, executable = [directory / name for name in ('k.c', 'h.c', 'k.ssa', 'k.s', 'p')]

    def compile_source(text, success=True, message=''):
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=15)
        if success:
            assert result.returncode == 0 and not result.stderr, (text[:500], result.stderr[-2000:])
        else:
            assert result.returncode == 1 and not result.stdout and message in result.stderr, (text[:500], result.stderr[-2000:])
        return result

    native_count = 0
    numeric_message_gap = False
    keyword_macro_warning = False
    for text in programs + [for_program, pp_program]:
        result = compile_source(text)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
            subprocess.run([host, str(assembly), '-o', str(executable)], capture_output=True, check=True, timeout=10)
            assert subprocess.run([str(executable)], timeout=5).returncode == 42, text
        if text == for_program and not native_for_assertion:
            # Require the exact known Clang 15 grammar gap, not any host failure.
            native.write_text(prefix + text + '\n')
            gap = subprocess.run([host, '-std=c2x', '-pedantic-errors', '-fsyntax-only', str(native)],
                                 capture_output=True, text=True, timeout=10)
            assert gap.returncode != 0 and "expected identifier or '('" in gap.stderr, gap.stderr
            continue
        if text == pp_program and not native_keyword:
            continue
        native.write_text((prefix if text != pp_program else '') + text + '\n')
        result = subprocess.run([host, '-std=c2x', '-pedantic-errors', '-fsigned-char', str(native), '-o', str(executable)],
                                capture_output=True, text=True, timeout=10)
        # Macro replacement uses preprocessing identifiers, including later
        # language keywords. New Clang's pedantic keyword-macro policy is not
        # a C constraint. Retry the identical source with only that warning
        # disabled, and only after verifying its exact one-error diagnostic.
        if result.returncode != 0 and text == pp_program:
            assert 'keyword is hidden by macro definition [-Werror,-Wkeyword-macro]' in result.stderr, result.stderr
            assert result.stderr.count('error:') == 1 and '1 error generated.' in result.stderr, result.stderr
            result = subprocess.run([host, '-std=c2x', '-pedantic-errors', '-Wno-keyword-macro',
                                     '-fsigned-char', str(native), '-o', str(executable)],
                                    capture_output=True, text=True, timeout=10)
            keyword_macro_warning = True
        # C23 6.4.5/6.7.11 permit numeric escapes in these messages.
        # Some newer Clang releases apply the C++ unevaluated-string rule
        # to C too. Keep the original kcc/QBE test and recognize only this
        # exact host failure; do not ban valid C or rewrite the message.
        if result.returncode != 0 and text == numeric_message_program:
            assert "invalid escape sequence '\\0' in an unevaluated string literal" in result.stderr, result.stderr
            assert result.stderr.count('error:') == 1 and '1 error generated.' in result.stderr, result.stderr
            numeric_message_gap = True
            continue
        assert result.returncode == 0, (text, result.stderr)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, text
        native_count += 1

    for text, message in constraints:
        compile_source(text, False, message)
    for text in strict_rejections:
        native.write_text(text + '\n')
        result = subprocess.run([host, '-std=c2x', '-pedantic-errors', '-fsyntax-only', str(native)],
                                capture_output=True, text=True, timeout=10)
        assert result.returncode != 0, text

    result = compile_source('static_assert(1,"not a datum");')
    assert result.stdout == ''
    result = compile_source('int missing(void); static_assert(sizeof missing()==4,"secret message"); '
                            'int f(void) { static_assert(1,"another message"); return 42; }')
    assert '$missing' not in result.stdout and '.Lkcc.string' not in result.stdout
    assert 'message' not in result.stdout and result.stdout.count('copy') == 1, result.stdout
    result = compile_source('static_assert(0,"first\\0" "last\\n\\\"\\\\%s\\xff");', False,
                            'static assertion failed: "first\\x00last\\x0a\\\"\\\\%s\\xff"')
    assert result.stderr.count('\n') == 1 and ':1:1: error:' in result.stderr, result.stderr
    result = compile_source('#define CHECK static_assert\nCHECK(0,"expanded");', False, 'expanded')
    assert ':2:1: error:' in result.stderr, result.stderr
    result = compile_source('static_assert(1/(2-2));', False, 'division by zero')
    assert ':1:16: error:' in result.stderr, result.stderr

    # Every decoded byte survives diagnostic rendering, including NUL and '%'.
    spelling = ''.join(f'\\x{byte:02x}' for byte in range(256))
    rendered = ''
    for byte in range(256):
        if byte in (34, 92):
            rendered += '\\' + chr(byte)
        elif 32 <= byte <= 126:
            rendered += chr(byte)
        else:
            rendered += f'\\x{byte:02x}'
    result = compile_source('static_assert(0,"' + spelling + '");', False,
                            'static assertion failed: "' + rendered + '"')
    assert result.stderr.count('\n') == 1
    for count, valid in [(1048576, True), (1048577, False)]:
        compile_source('static_assert(1,"' + 'a' * count + '");', valid, 'string literal storage/count limit')

    for count, valid in [(127, True), (128, False)]:
        compile_source('static_assert(' + '+ ' * count + '1);', valid, 'depth')
    for count, valid in [(126, True), (127, False)]:
        compile_source('static_assert(' + '+ ' * count + 'true);', valid, 'typed expression exceeds depth')
    for count, valid in [(512, True), (513, False)]:
        compile_source('static_assert(1);\n' * count, valid, 'declaration limit')
    for count, valid in [(4095, True), (4096, False)]:
        compile_source('int f(void) {' + 'static_assert(1);' * count + 'return 42;}', valid, 'item limit')
    for count, valid in [(4093, True), (4094, False)]:
        compile_source('int f(void) {' + 'static_assert(1);' * count +
                       'for(static_assert(1);0;) ; return 42;}', valid, 'item limit')
    for count, valid in [(4096, True), (4097, False)]:
        compile_source('static_assert(1,' + '"a"' * count + ');', valid, 'string fragment limit')

print(f'Static assertions passed: {len(programs)+2} original programs, {native_count} strict native agreements, '
      f'{len(constraints)} constraints, {len(strict_rejections)} strict native ICE rejections, diagnostic bytes/provenance, '
      f'exact syntax/typed/item/external/string limits; {host}; '
      + ('numeric-message Clang oracle gap; ' if numeric_message_gap else '')
      + ('exact keyword-macro warning disabled on unchanged source; ' if keyword_macro_warning else '')
      + ('native keyword' if native_keyword else 'labelled static_assert/_Static_assert oracle')
      + ('; native for-declaration' if native_for_assertion else '; exact legacy for-declaration parser gap')
      + ('; QBE/runtime and erasure passed' if qbe else ''))

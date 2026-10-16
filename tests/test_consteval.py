"""Pure typed ICE queries; only curated defined constants reach host execution."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
oracle = Path(os.environ.get('CONSTEVAL_ORACLE', root / 'build' / 'consteval_oracle'))
host = os.environ.get('HOST_CC', 'cc')
types = ['_Bool', 'char', 'signed char', 'unsigned char', 'short', 'unsigned short',
         'int', 'unsigned', 'long', 'unsigned long', 'long long', 'unsigned long long']
spellings = ['0', '1', '-1', '127', '128', '255', '256', '32767', '32768', '65535', '65536',
             '2147483647', '2147483648U', '4294967295U', '1ULL<<63', '18446744073709551615ULL',
             '(-9223372036854775807LL-1LL)']
values = []
for name in types:
    for spelling in spellings:
        values += [f'({name})({spelling})', f'+({name})({spelling})']
    values += [f'~({name})1', f'-({name})1', f'!({name})0', f'({name})1<<3', f'({name})-1>>1']
for a in types:
    for b in types:
        values += [f'({a})1+({b})2', f'({a})-1<({b})0', f'1?({a})-1:({b})0']
values += [
    '0U-1U', '4294967295U+1U', '18446744073709551615ULL+1ULL', '0ULL-1ULL',
    '18446744073709551615ULL*18446744073709551615ULL',
    '(-2147483647-1)+1', '2147483647-1', '-2147483647-1',
    '(-9223372036854775807LL-1LL)+1LL', '9223372036854775807LL-1LL',
    '(-2147483647-1)/2', '(-2147483647-1)%3', '-7/3', '-7%3',
    '(-9223372036854775807LL-1LL)/2LL', '(-9223372036854775807LL-1LL)%3LL',
    '(-9223372036854775807LL-1LL)*1LL', '-4611686018427387904LL*2LL',
    '(-2147483647-1)>>31', '(-9223372036854775807LL-1LL)>>63',
    '1U<<31', '1ULL<<63', '18446744073709551615ULL>>63',
    '42==42', '42!=7', '-7<42', '42<=42', '-7>-42', '42>=42',
    '(1ULL<<63)>9223372036854775807LL', '255U&42U', '255U^42U', '8U|2U',
    '0 && (1/0)', '1 || (1/0)', '1?42:1/0', '0?1/0:42',
    '1?42:2147483647+1', '0?1ULL<<64:42', '1?42:-1<<1',
    '0?(1,2):42', '1?42:(0?(3,4):(5,6))', '0?((1,2),(3,4)):42', '0 && (1,2)', '1 || (1,2)', '1?42:(1/0,2)',
    'sizeof(int)', '_Alignof(long)', 'sizeof(int[2][3])', 'sizeof(int (*)(void))',
    "'A'", "'\\n'", "'\\0'", 'sizeof x', 'sizeof(x=1)', 'sizeof named()', 'sizeof(1/0)', 'sizeof "a\\0b"',
]
invalid = [
    '2147483647+1', '(-2147483647-1)-1', '2147483647-(-1)',
    '(-2147483647-1)+(-1)', '2147483647*2', '(-2147483647-1)*-1',
    '-(-2147483647-1)', '(-2147483647-1)/-1', '(-2147483647-1)%-1',
    '9223372036854775807LL+1LL', '(-9223372036854775807LL-1LL)-1LL',
    '(-9223372036854775807LL-1LL)*-1LL', '-(-9223372036854775807LL-1LL)',
    '(-9223372036854775807LL-1LL)/-1LL', '(-9223372036854775807LL-1LL)%-1LL',
    '4611686018427387904LL*2LL', '-4611686018427387905LL*2LL',
    '1/0', '1%0', '1U/0U', '1ULL%0ULL', '1<<-1', '1<<32', '1ULL<<64',
    '1>>-1', '1>>32', '1ULL>>64', '-1<<1', '1<<31', '1LL<<63',
    '1U<<4294967295U', '1ULL<<18446744073709551615ULL',
    '2147483647-(-1)+0U', '(int)(2147483647+1)',
]
not_constant = ['x', 'c', 'x+1', '(int)x', 'x?1:2', '0&&x', '1||x', '1?42:x',
                'named()', '0&&named()', '1?42:named()', '(1,42)', '(x=1)',
                '1?42:(x=1)', '0?(x,2):42', '&x', '&x==&x', '(_Bool)&x', '0&&(_Bool)&x']

with tempfile.TemporaryDirectory(prefix='kcc constant queries ') as directory:
    directory = Path(directory)
    source, native, executable = [directory / name for name in ('k.c', 'h.c', 'p')]

    def query(expressions):
        source.write_text('int named(void); int f(int x) { const int c=42;\n' +
                          ''.join(f'({expression});\n' for expression in expressions) + 'return 0; }\n')
        result = subprocess.run([str(oracle), str(source)], capture_output=True, text=True, timeout=15)
        assert result.returncode == 0 and not result.stderr, result.stderr
        lines = result.stdout.splitlines()
        assert len(lines) == len(expressions), result.stdout
        return lines

    boolean_values = ['true', 'false', '(bool)42', '(bool)0', '+true', 'true?false:true']
    assert query(boolean_values) == ['value 1 8 1', 'value 0 8 1', 'value 1 8 1',
                                     'value 0 8 1', 'value 1 32 0', 'value 0 32 0']
    actual = query(values)
    # Each _Static_assert enforces ICE form separately from executing its value.
    # The host program only contains explicitly curated defined expressions.
    header = '#include <stdio.h>\nint named(void);\n'
    header += 'int main(void) { int x;\n'
    native_text = header
    for expression in values:
        native_text += f'_Static_assert(({expression})==({expression}),"ICE form");\n'
        native_text += f'printf("value %llu %u %u\\n",(unsigned long long)({expression}) & '
        native_text += f'(~0ULL >> (64-sizeof({expression})*8)),(unsigned)(sizeof({expression})*8),'
        native_text += f'_Generic(({expression}),_Bool:1u,unsigned char:1u,unsigned short:1u,'
        native_text += 'unsigned int:1u,unsigned long:1u,unsigned long long:1u,default:0u));\n'
    native.write_text(native_text + 'return 0; }\n')
    result = subprocess.run([host, '-std=c2x', '-pedantic-errors', '-fsigned-char', str(native), '-o', str(executable)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr[-6000:]
    expected = subprocess.run([str(executable)], capture_output=True, text=True, check=True, timeout=10).stdout.splitlines()
    assert len(expected) == len(actual)
    for expression, got, want in zip(values, actual, expected):
        assert got == want, (expression, got, want)
    for expression, result in zip(invalid, query(invalid)):
        assert result == 'invalid', (expression, result)
    for expression, result in zip(not_constant, query(not_constant)):
        assert result == 'not_constant', (expression, result)

    # Strict native form rejection for nonconstant integer operands. Do not
    # execute them or demand that hosts reject every UB extension they accept.
    strict_cases = ['x', 'c', '0&&x', '1||x', '1?42:x', '0&&named()', '1?42:named()', '(1,42)']
    for expression in strict_cases:
        native.write_text('int named(void); int f(int x) { const int c=42; '
                          f'_Static_assert(({expression})==0,"not ICE"); return 0; }}')
        result = subprocess.run([host, '-std=c2x', '-pedantic-errors', '-fsyntax-only', str(native)],
                                capture_output=True, text=True, timeout=10)
        assert result.returncode != 0, expression

print(f'Integer constant foundation passed: {len(values)} strict native ICE/value agreements, '
      f'{len(boolean_values)} C23 boolean queries, {len(invalid)} nonexecuted invalid arithmetic cases, {len(not_constant)} nonconstant forms, '
      f'{len(strict_cases)} strict native form rejections; {host}')

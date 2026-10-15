"""Bounded signed-decimal #if arithmetic and macro/defined oracle."""
import os
import random
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root / 'build' / 'kcc'
oracle = root / 'build' / 'pp_oracle'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
rng = random.Random(0x23)
expressions = [
    ('0', False), ('1', True), ('missing', False),
    ('2+3*4 == 14', True), ('(2+3)*4 == 20', True),
    ('8/3/2 == 1', True), ('6-2-1 == 3', True), ('-7%3 == -1', True),
    ('-7/3 == -2', True), ('!-2 == 0', True), ('1 < 2 == 1', True),
    ('1 == 2 < 3', True), ('1 < 2 < 1', False), ('1 || 0 && 0', True),
    ('0 && 1/0', False), ('1 || 1/0', True),
    ('1 || (9223372036854775807+1)', True),
    ('0 && (-(-9223372036854775807-1))', False),
    ('9223372036854775807-1 == 9223372036854775806', True),
    ('(-9223372036854775807-1)+9223372036854775807 == -1', True),
    ('(-9223372036854775807-1)*1 == (-9223372036854775807-1)', True),
    ('(-9223372036854775807-1)*0 == 0', True),
    ('(-9223372036854775807-1)/2 == -4611686018427387904', True),
    ('5 > 3 && 3 >= 3 && 2 <= 2 && 2 != 3', True),
]

expressions += [
    ('~0 == -1', True), ('~(-1) == 0', True),
    ('~(-9223372036854775807-1) == 9223372036854775807', True),
    ('-8 >> 2 == -2', True), ('-1 >> 63 == -1', True),
    ('(-9223372036854775807-1) >> 63 == -1', True),
    ('(-9223372036854775807-1) >> 1 == -4611686018427387904', True),
    ('0 << 63 == 0', True), ('1 << 62 == 4611686018427387904', True),
    ('3 << 2+1 == 24', True), ('8 >> 1+1 == 2', True),
    ('1 < 2 << 1', True), ('1 & 2 == 0', False), ('(1&2) == 0', True),
    ('1 ^ 3 & 1', False), ('1 | 2 ^ 3 & 1', True),
    ('(5 & 3) == 1', True), ('(5 ^ 3) == 6', True), ('(5 | 3) == 7', True),
    ('(-1 & 42) == 42', True), ('(-1 ^ 1) == -2', True),
    ('1 ? 42 : 0', True), ('0 ? 42 : 0', False),
    ('0 ? 1 : 0 ? 2 : 3', True), ('1 ? 0 ? 0 : 42 : 0', True),
    ('1 || 0 ? 0 : 42', False), ('1 ? 0 : 1 || 1', False),
    ('1 ? 42 : 1/0', True), ('0 ? 1/0 : 42', True),
    ('1 ? 42 : (9223372036854775807+1)', True),
    ('0 && (1 << 64)', False), ('1 || (-1 << 1)', True),
    ('1 ? 42 : (1 >> -1)', True), ('0 ? (1 << 63) : 42', True),
]

def expression(depth):
    if not depth or rng.randrange(4) == 0:
        value = rng.randrange(6)
        return str(value), value
    left, a = expression(depth-1)
    if rng.randrange(5) == 0:
        op = rng.choice(['+', '-', '!'])
        return f'{op}({left})', a if op == '+' else -a if op == '-' else int(not a)
    if rng.randrange(6) == 0:
        yes, a_yes = expression(depth-1)
        no, a_no = expression(depth-1)
        return f'({left}) ? ({yes}) : ({no})', a_yes if a else a_no
    op = rng.choice(['+', '-', '*', '/', '%', '<', '<=', '>', '>=', '==', '!=', '&', '^', '|', '&&', '||'])
    right, b = expression(depth-1)
    if op in ('/', '%'):
        b = rng.randrange(1, 6)
        right = str(b)
        quotient = (abs(a)//b) * (-1 if a < 0 else 1)
        value = quotient if op == '/' else a - quotient*b
    elif op == '+': value = a+b
    elif op == '-': value = a-b
    elif op == '*': value = a*b
    elif op == '<': value = int(a < b)
    elif op == '<=': value = int(a <= b)
    elif op == '>': value = int(a > b)
    elif op == '>=': value = int(a >= b)
    elif op == '==': value = int(a == b)
    elif op == '!=': value = int(a != b)
    elif op == '&': value = a & b
    elif op == '^': value = a ^ b
    elif op == '|': value = a | b
    elif op == '&&': value = int(bool(a) and bool(b))
    else: value = int(bool(a) or bool(b))
    return f'({left}) {op} ({right})', value

for _ in range(150):
    text, value = expression(4)
    expressions.append((text, bool(value)))

prefix = '#define X missing\n#define ADD(a,b) ((a)+(b))\n#define C(a,b) a##b\n'
expressions += [(text, value) for text, value in [
    ('defined X', True), ('defined(X)', True), ('defined(missing)', False),
    ('defined X && !defined(missing) && X == 0', True),
    ('ADD(40,2) == C(4,2)', True), ('!defined(none) && ADD(2,3) == 5', True),
]]

with tempfile.TemporaryDirectory(prefix='kcc-if-') as directory:
    directory = Path(directory)
    source = directory / 'input.c'
    for text, selected in expressions:
        expected = '42' if selected else '0'
        for ending in ('\n', '\r\n', '\r'):
            source.write_bytes((prefix + f'#if {text}\n42\n#else\n0\n#endif\n').replace('\n', ending).encode())
            result = subprocess.run([str(oracle), '--pp', str(source)],
                                    capture_output=True, text=True, timeout=5)
            assert result.returncode == 0 and not result.stderr, (text, result.stderr)
            assert result.stdout == f'pp-number:{expected}\n', (text, result.stdout, expected)
            reference = subprocess.run([host, '-std=c2x', '-E', '-P', str(source)],
                                       capture_output=True, text=True, timeout=10)
            assert reference.returncode == 0 and reference.stdout.split() == [expected], (text, reference.stderr)
    for text, message in [
        ('defined()', 'expected an identifier'), ('defined(X', "expected ')'"),
        ('1/0', 'division by zero'), ('1%0', 'division by zero'),
        ('9223372036854775807+1', 'signed overflow'),
        ('(-9223372036854775807-1)-1', 'signed overflow'),
        ('(-9223372036854775807-1)*-1', 'signed overflow'),
        ('(-9223372036854775807-1)/-1', 'signed overflow'),
        ('(-9223372036854775807-1)%-1', 'signed overflow'),
        ('-(-9223372036854775807-1)', 'signed overflow'),
        ('1 || (1+)', 'expected an operand'), ('1 &&', 'expected an operand'),
        ('1U', 'only decimal'), ('1 << 64', 'shift count'),
        ('1 << -1', 'shift count'), ('-1 << 1', 'negative left'),
        ('1 << 63', 'signed overflow'), ('1 ? 2', "expected ':'"),
        ('1 ? 42 : (1+)', 'expected an operand'),
    ]:
        source.write_text(f'#if {text}\n#endif\nint main(void) {{ return 0; }}\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)
    programs = [
        '#if 2+3*4==14\nreturn 42;\n#else\n#error bad\n#endif\n',
        '#if ((-8>>1)==-4) && ((5^3)==6)\nreturn 42;\n#endif\n',
        '#if 1 ? 42 : (1/0)\nreturn 42;\n#endif\n',
        '#if 0 ? (1<<64) : ((1<<62)>0)\nreturn 42;\n#endif\n',
        '#if 0 ? 0 : 1 ? 42 : 0\nreturn 42;\n#endif\n',
        '#if 0\n#error hidden\n#elif defined(X) && ADD(40,2)==42\nreturn 42;\n#endif\n',
        '#if 0 && 1/0\n#error hidden\n#elif 1 || 1/0\nreturn 42;\n#endif\n',
        '#if defined(X) && !defined(missing) && X==0\nreturn 42;\n#endif\n',
        '#if ADD(C(4,0),2)==42\nreturn 42;\n#endif\n',
        '#if 0\n#if F(\n#error hidden\n#endif\n#else\nreturn 42;\n#endif\n',
    ]
    for body in programs:
        for ending in ('\n', '\r\n', '\r'):
            source.write_bytes((prefix+'int main(void) {\n'+body+'}\n').replace('\n', ending).encode())
            result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
            assert result.returncode == 0 and not result.stderr, result.stderr
            if qbe:
                il, assembly, executable = [directory/name for name in ('p.ssa', 'p.s', 'p')]
                il.write_text(result.stdout)
                subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
                subprocess.run([host, str(assembly), '-o', str(executable)], check=True, timeout=10)
                assert subprocess.run([str(executable)], timeout=5).returncode == 42
                subprocess.run([host, '-std=c2x', str(source), '-o', str(executable)], check=True, timeout=10)
                assert subprocess.run([str(executable)], timeout=5).returncode == 42
print(f'Conditional expressions passed ({len(expressions)*3} host/model agreements; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

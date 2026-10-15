"""intmax/uintmax models, usual conversions and ternary branch types."""
import os
import random
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root/'build'/'kcc'
oracle = root/'build'/'pp_oracle'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
mask = (1 << 64)-1
minimum = -(1 << 63)
maximum = (1 << 63)-1
rng = random.Random(0x64ff)
cases = [
    ('18446744073709551615U + 1U == 0', True),
    ('0U-1U == 18446744073709551615U', True),
    ('-1U == 18446744073709551615U', True),
    ('~0U == 18446744073709551615U', True),
    ('18446744073709551615U * 2 == 18446744073709551614U', True),
    ('-1 < 1U', False), ('-1 == 18446744073709551615U', True),
    ('0xffffffffffffffff == -1', True), ('0x8000000000000000L < 0', False),
    ('1U << 63 == 9223372036854775808U', True),
    ('18446744073709551615U << 1 == 18446744073709551614U', True),
    ('18446744073709551615U >> 63 == 1', True),
    ('(-1 >> 1U) == -1', True), ('((1 >> 63U)-1) < 0', True),
    ('((1U==1U)-2)<0', True), ('((1U&&1U)-2)<0', True),
    ('((!0U)-2)<0', True),
    ('(1 ? -1 : 1U)<0', False), ('(0 ? 1U : -1)<0', False),
    ('(1 ? -1 : 1U/0)<0', False), ('(1 ? -1 : (0&&1U))<0', True),
    ('(1 ? -1 : (1U<2U))<0', True), ('(1 ? -1 : (1<<-1U))<0', True),
    ('(1 ? -1 : ~0U)<0', False),
    ('(1 ? -1 : (+1U))<0', False), ('(1 ? -1 : (1U<<0))<0', False),
    ('(1 ? -1 : (-1>>1U))<0', True), ('(1 ? -1 : (1U&&0U))<0', True),
    ('(0 ? 1U/0 : -1)>0', True), ('((0 || 1U)-2)<0', True),
    ('U(18446744073709551615)+1 == 0', True),
    ('CAT(1,u)<<63 == 9223372036854775808U', True),
    ('(-9223372036854775807-1)/-1U == 0U', True),
    ('(-9223372036854775807-1)%-1U == 9223372036854775808U', True),
]
for suffix in ('u', 'U', 'ul', 'uL', 'Ul', 'UL', 'ull', 'uLL', 'Ull', 'ULL',
               'lu', 'lU', 'Lu', 'LU', 'llu', 'llU', 'LLu', 'LLU'):
    cases.append((f'42{suffix} == 42U', True))


def literal(value, unsigned):
    if unsigned:
        return str(value & mask)+'U'
    if value == minimum:
        return '(-9223372036854775807-1)'
    return str(value) if value >= 0 else f'(-{-value})'


def model(a, ua, b, ub, op):
    unsigned = ua or ub
    left, right = (a & mask, b & mask) if unsigned else (a, b)
    if op == '+': result = left+right
    elif op == '-': result = left-right
    elif op == '*': result = left*right
    elif op in ('/', '%'):
        if right == 0 or not unsigned and left == minimum and right == -1:
            return None
        quotient = abs(left)//abs(right) * (-1 if (left < 0) != (right < 0) else 1)
        result = quotient if op == '/' else left-quotient*right
    elif op in ('<<', '>>'):
        if b < 0 or b >= 64:
            return None
        unsigned = ua  # Right operand does not change the result type.
        left = a & mask if ua else a
        if op == '<<':
            if not ua and (left < 0 or left > maximum >> b):
                return None
            result = left << b
        else: result = left >> b
    elif op == '&': result = left & right
    elif op == '^': result = left ^ right
    elif op == '|': result = left | right
    elif op == '<': return int(left < right), False
    elif op == '<=': return int(left <= right), False
    elif op == '>': return int(left > right), False
    elif op == '>=': return int(left >= right), False
    elif op == '==': return int(left == right), False
    else: return int(left != right), False
    if unsigned:
        return result & mask, True
    if result < minimum or result > maximum:
        return None
    return result, False


models = 0
while models < 250:
    ua, ub = bool(rng.randrange(2)), bool(rng.randrange(2))
    a = rng.choice([0, 1, 42, maximum, 1 << 63, mask, rng.getrandbits(64)]) if ua else rng.choice([minimum, -42, -1, 0, 1, 42, maximum])
    b = rng.choice([0, 1, 42, maximum, 1 << 63, mask, rng.getrandbits(64)]) if ub else rng.choice([minimum, -42, -1, 0, 1, 42, maximum])
    op = rng.choice(['+', '-', '*', '/', '%', '<<', '>>', '&', '^', '|', '<', '<=', '>', '>=', '==', '!='])
    if op in ('<<', '>>'):
        b = rng.choice([0, 1, 31, 32, 63])
    expected = model(a, ua, b, ub, op)
    if expected is None:
        continue
    value, unsigned = expected
    text = f'({literal(a, ua)}) {op} ({literal(b, ub)})'
    # Check value AND type: OR with -1 is negative iff the result is signed.
    condition = f'(({text}) == {literal(value, unsigned)}) && (((({text}) | -1)<0) == {int(not unsigned)})'
    cases.append((condition, True))
    models += 1

with tempfile.TemporaryDirectory(prefix='kcc-uintmax-') as directory:
    directory = Path(directory)
    source = directory/'input.c'
    for text, selected in cases:
        expected = '42' if selected else '0'
        source.write_text('#define U(x) x##U\n#define CAT(a,b) a##b\n'+f'#if {text}\n42\n#else\n0\n#endif\n')
        result = subprocess.run([str(oracle), '--pp', str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        assert result.stdout == f'pp-number:{expected}\n', (text, result.stdout, expected)
        reference = subprocess.run([host, '-std=c2x', '-E', '-P', str(source)], capture_output=True, text=True, timeout=10)
        assert reference.returncode == 0 and reference.stdout.split() == [expected], (text, reference.stderr, reference.stdout)
    for text in ('1U/0', '1U%0', '1U<<64', '1U>>-1', '1U << 18446744073709551615U',
                 '18446744073709551616U', '1UU', '1uLl'):
        source.write_text(f'#if {text}\n#endif\nint main(void) {{ return 0; }}\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and 'error:' in result.stderr, text
    for text in ('0U-1U == 18446744073709551615U', '(1 ? -1 : 1U/0)>0',
                 '((1U==1U)-2)<0', '(-1 >> 1U)==-1', '1U<<63 == 9223372036854775808U'):
        for ending in ('\n', '\r\n', '\r'):
            source.write_bytes((f'#if {text}\nint main(void) {{ return 42; }}\n#else\n#error bad\n#endif\n').replace('\n', ending).encode())
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
print(f'Unsigned conditions passed ({len(cases)} host/model agreements; {host})'
      + ('; QBE/runtime passed' if qbe else ''))

"""File-scope internal fixed arrays: source-point types, local storage and ABI.

Only small, defined curated programs execute. Constraints, undefined-linkage
refusals and maximal resource fixtures are compile-only. Native diagnostics are
never silently classified as agreements. QBE has no ELF data-size metadata:
validate its exact IL allocation, local symbol offsets and BSS extent together.
"""
import os
import re
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
flags = ['-std=c2x', '-pedantic-errors', '-fno-common']

integer_types = [
    ('_Bool', '1', 1), ('char', '-7', 1), ('signed char', '-7', 1),
    ('unsigned char', '255', 1), ('short', '-1234', 2),
    ('unsigned short', '65535', 2), ('int', '-1234567', 4),
    ('unsigned', '4294967295U', 4), ('long', '4294967296L', 8),
    ('unsigned long', '18446744073709551615UL', 8),
    ('long long', '4611686018427387904LL', 8),
    ('unsigned long long', '18446744073709551615ULL', 8),
]
programs = []
for kind, value, size in integer_types:
    programs.append((
        f'static {kind} items[4]; int main(void) {{ '
        f'if(items[0]!=0 || items[3]!=0) return 1; items[2]={value}; '
        f'return items[2]==({kind}){value}?42:2; }}',
        {'items': (size * 4, size)}))
programs += [
    ('static const int items[3]; int main(void) { '
     'return items[0]==0 && items[2]==0?42:1; }', {'items': (12, 4)}),
    ('static int items[3]; extern int items[]; static int items[]; '
     'int main(void) { items[2]=42; return sizeof(items)==12?items[2]:1; }',
     {'items': (12, 4)}),
    ('typedef int Row[3]; static Row rows[2]; int main(void) { '
     'if(rows[0][0] || rows[1][2]) return 1; rows[1][2]=42; '
     'return &rows[1]-&rows[0]==1?rows[1][2]:2; }', {'rows': (24, 4)}),
    ('static int items[2], f(void), other[3]; int f(void) { '
     'items[1]=40; other[2]=2; return items[1]+other[2]; } '
     'int main(void) { return f(); }', {'items': (8, 4), 'other': (12, 4)}),
    ('static int *items[2]; int main(void) { int x=42; '
     'if(items[0] || items[1]) return 1; items[1]=&x; return *items[1]; }',
     {'items': (16, 8)}),
    ('static int (*items[2])(int); static int id(int x) { return x; } '
     'int main(void) { if(items[0] || items[1]) return 1; '
     'items[1]=id; return items[1](42); }', {'items': (16, 8)}),
    ('static int rows[2][3]; extern int rows[][3]; '
     'int main(void) { int (*p)[3]=rows; p[1][2]=42; '
     'return sizeof(rows)==24?rows[1][2]:1; }', {'rows': (24, 4)}),
    ('static int items[3]; typedef int A[3]; static A items; '
     'int main(void) { int (*p)[3]=&items; (*p)[2]=42; return items[2]; }',
     {'items': (12, 4)}),
    ('#define STORE static\nSTORE int items[3]; int main(void) { '
     '{ int items=2; if(items!=2) return 1; } return items[0]+42; }',
     {'items': (12, 4)}),
]

# These are independently expected kcc runtime results, not native agreements
# when the host lacks the exact C23 syntax.
query_programs = [
    ('static typeof(int[3]) items; int main(void) { '
     'items[2]=42; return items[0]==0?items[2]:1; }', {'items': (12, 4)}),
    ('static int items[3]; static typeof(items) items; '
     'int main(void) { items[2]=42; return items[2]; }', {'items': (12, 4)}),
    ('static typeof(nullptr) items[2]; int main(void) { '
     'return items[0]==nullptr && items[1]==nullptr?42:1; }',
     {'items': (16, 8)}),
]
constraints = [
    'static int items[];',
    'static int cell[];',
    'static int items[]; static int items[3];',
    'static int items[]; extern int items[3];',
    'typedef int A[]; static A items;',
    'static int items[3]; static int items[4];',
    'static int items[3]; extern long items[3];',
    'static const int items[3]; int main(void) { items[0]=1; return 0; }',
    'static int items[2][];',
    'static void items[2];',
    'static int items[0];',
    'static int items[-1];',
    'static int f(void); static int f[2];',
    'static int items[2]; typedef int items;',
    'static int items[3]; int main(void) { int other[3]; items=other; return 0; }',
]
linkage_refusals = [
    'int items[3]; static int items[3];',
    'extern int items[3]; static int items[3];',
    'static int items[3]; int items[3];',
    'static int items[3]; extern int items[]; int items[3];',
    'extern int cell[3]; static int cell[3];',
]
acceptance_only = [
    'static int cell[3];', 'static int cell[2][3];',
    'typedef int A[3]; static A cell;', 'static typeof(int[3]) cell;',
    'static int cell,items[3];', 'static int items[3],cell;',
    'static int items[3];',
]
subset_refusals = [
    'static int items[3]={1,2,3};',
    'static int items[3]={};',
    'int main(void) { static int items[3]; return 0; }',
]


def invoke(args):
    return subprocess.run(list(map(str, args)), capture_output=True,
                          text=True, timeout=15)


def fresh_output(args, output):
    output.unlink(missing_ok=True)
    result = invoke(args)
    assert result.returncode == 0 and not result.stdout and not result.stderr, (args, result)
    assert output.is_file() and output.stat().st_size > 0, (args, output)
    return result


def native_constraint(result, path):
    return (result.returncode == 1 and not result.stdout
            and re.search(re.escape(str(path)) + r':\d+:\d+: error:', result.stderr)
            and not re.search(r'internal compiler error|LLVM ERROR|Stack dump|'
                              r'PLEASE submit|[Ss]egmentation fault|'
                              r'unrecognized command-line|unknown argument|fatal error:',
                              result.stderr))


feature_probes = {'typeof': 'typeof(int) value;', 'nullptr': 'int *p=nullptr;'}


def exact_legacy_probe(feature, text, result, path):
    if text != feature_probes[feature] or result.returncode != 1 or result.stdout:
        return False
    normalized = result.stderr.replace('‘', "'").replace('’', "'")
    expected = {
        'typeof': [
            ["return type defaults to 'int' [-Wimplicit-int]",
             "expected declaration specifiers before 'value'",
             "expected '{' at end of input"],
            ['expected function body after function declarator']],
        'nullptr': [["'nullptr' undeclared here (not in a function)"],
                    ["use of undeclared identifier 'nullptr'"]],
    }
    messages = []
    lines = normalized.splitlines()
    for index, line in enumerate(lines):
        match = re.fullmatch(re.escape(str(path)) + r':\d+(?::\d+)?: error: (.+)', line)
        if match:
            messages.append(match.group(1))
        elif re.fullmatch(r'\s*\d+ \| ?' + re.escape(text), line):
            pass
        elif re.fullmatch(r'\s*\d+ \| ?', line):
            pass
        elif re.fullmatch(r'[ \t]*\|[ ~^]*', line):
            pass
        elif line == text or re.fullmatch(r'[ ~^]+', line):
            pass
        elif feature == 'typeof' and line == str(path) + ": In function 'typeof':":
            pass
        elif (index == len(lines) - 1
              and line == f"{len(messages)} error{'s' if len(messages) != 1 else ''} generated."):
            pass
        else:
            return False
    return messages in expected[feature]


def check_local_bss(assembly_text, nm_text, section_text, owned):
    # Independently reconcile exact allocation directives, all storage symbols,
    # ordered offsets and writable ELF NOBITS extent/alignment. A zero offset
    # does not establish actual section alignment, and full-section size alone
    # cannot establish an individual symbol's allocation.
    for name, (size, alignment) in owned.items():
        expected = (f'.bss\n.balign {alignment}\n{name}:\n'
                    f'\t.fill {size},1,0\n/* end data */')
        assert assembly_text.count(expected) == 1, (expected, assembly_text)
    assert len(re.findall(r'^\.bss$', assembly_text, re.M)) == len(owned)
    assert len(re.findall(r'^\s*\.fill\b', assembly_text, re.M)) == len(owned)
    assert not re.search(r'^\s*\.(?:comm|lcomm)\b', assembly_text, re.M)
    for name in owned:
        assert not re.search(r'^\s*\.(?:globl|global)\s+' + re.escape(name) + r'\b',
                             assembly_text, re.M)
    records = {}
    for line in nm_text.splitlines():
        fields = line.split()
        assert len(fields) in (2, 3, 4), (line, nm_text)
        if fields[-2] in 'bBdDrRcCsSgG' and fields[-1] not in owned:
            raise AssertionError(('unexplained storage owner', line))
        if fields[-1] in owned:
            name = fields[-1]
            assert name not in records, (name, nm_text)
            assert len(fields) in (3, 4) and fields[-2] == 'b', (name, nm_text)
            address = int(fields[0], 16)
            size, alignment = owned[name]
            assert address % alignment == 0, (name, address, alignment)
            if len(fields) == 4:
                assert int(fields[1], 16) == size, (name, nm_text)
            records[name] = address
    assert set(records) == set(owned), (owned, nm_text)
    order = sorted(owned, key=lambda name: assembly_text.index(f'\n{name}:\n'))
    cursor = 0
    for name in order:
        size, alignment = owned[name]
        cursor = (cursor + alignment - 1) // alignment * alignment
        assert records[name] == cursor, (name, cursor, records)
        cursor += size
    rows = [re.fullmatch(
        r'\s*\[\s*\d+\]\s+\.bss\s+NOBITS\s+[0-9a-fA-F]+\s+[0-9a-fA-F]+\s+'
        r'([0-9a-fA-F]+)\s+\S+\s+(\S+)\s+\d+\s+\d+\s+(\d+)\s*', line)
        for line in section_text.splitlines()]
    rows = [row for row in rows if row is not None]
    assert len(rows) == 1, section_text
    size, flags, alignment = rows[0].groups()
    assert int(size, 16) == cursor and 'W' in flags and 'A' in flags, section_text
    assert int(alignment) >= max(a for _, a in owned.values()), section_text


def local_layout(il, obj, assembly_text, owned):
    for name, (size, alignment) in owned.items():
        expected = f'data ${name} = align {alignment} {{ z {size} }}'
        assert il.splitlines().count(expected) == 1, (expected, il)
        assert not re.search(r'export data \$' + re.escape(name) + r'\b', il)
    nm = invoke(['nm', '-S', obj])
    sections = invoke(['readelf', '-SW', obj])
    assert nm.returncode == 0 and not nm.stderr, nm.stderr
    assert sections.returncode == 0 and not sections.stderr, sections.stderr
    check_local_bss(assembly_text, nm.stdout, sections.stdout, owned)


def layout_controls():
    owned = {'first': (3, 1), 'second': (16, 8), 'third': (12, 4)}
    asm = ''.join(f'.bss\n.balign {alignment}\n{name}:\n'
                  f'\t.fill {size},1,0\n/* end data */\n\n'
                  for name, (size, alignment) in owned.items())
    nm = '00000000 b first\n00000008 b second\n00000018 b third\n'
    sections = ' [ 3] .bss NOBITS 00000000 000040 000024 00 WA 0 0 8\n'
    check_local_bss(asm, nm, sections, owned)
    for changed_asm, changed_nm, changed_sections in [
        (asm.replace('.fill 16,1,0', '.fill 8,1,0'), nm, sections),
        (asm.replace('.balign 8', '.balign 1'), nm, sections),
        (asm, nm, sections.replace('WA 0 0 8', 'WA 0 0 1')),
        (asm, nm + '0000000c b hidden\n', sections),
        (asm.replace('.fill 16,1,0', '.fill 4,1,0\nhidden:\n.zero 12'),
         nm + '0000000c b hidden\n', sections),
        (asm, nm.replace('00000008', '00000003'), sections),
        (asm, nm.replace('b second', 'B second'), sections),
        (asm, nm.replace('b second', 'r second'), sections),
        (asm, nm + '00000000 b first\n', sections),
        (asm, nm.replace('00000008 b second\n', ''), sections),
        (asm, nm, sections.replace('000024', '000023')),
        (asm, nm, sections.replace('NOBITS', 'PROGBITS')),
        (asm, nm, sections.replace(' WA ', ' A ')),
        (asm, nm, ''),
    ]:
        try:
            check_local_bss(changed_asm, changed_nm, changed_sections, owned)
        except AssertionError:
            pass
        else:
            raise AssertionError('invalid local-array layout evidence accepted')


layout_controls()

# Exact legacy footers are syntactically supported, not evidence that a
# particular unavailable Clang version was tested here.
for feature, text in feature_probes.items():
    path = Path('/synthetic/probe.c')
    message = ('expected function body after function declarator' if feature == 'typeof'
               else "use of undeclared identifier 'nullptr'")
    diagnostic = f'{path}:1:1: error: {message}\n'
    assert exact_legacy_probe(feature, text, subprocess.CompletedProcess(
        [], 1, '', diagnostic + '1 error generated.\n'), path)
    for footer in ['2 errors generated.\n', '1 errors generated.\n',
                   '1 error generated.\n1 error generated.\n',
                   '1 error generated.\nunparsed failure\n']:
        assert not exact_legacy_probe(feature, text, subprocess.CompletedProcess(
            [], 1, '', diagnostic + footer), path)


with tempfile.TemporaryDirectory(prefix='kcc static arrays ') as directory:
    directory = Path(directory)
    source = directory / 'input.c'

    def compile_source(text, accepted=True, message=None):
        source.write_text(text + '\n')
        result = invoke([compiler, source])
        if accepted:
            assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        else:
            assert result.returncode == 1 and not result.stdout, (text, result)
            assert str(source) + ':' in result.stderr and 'error:' in result.stderr
            if message:
                assert message in result.stderr, (text, result.stderr)
        return result.stdout

    def native_program(text):
        source.write_text(text + '\n')
        executable = directory / 'native'
        fresh_output([host, *flags, '-O0', source, '-o', executable], executable)
        assert invoke([executable]).returncode == 42, text

    def qbe_object(text, owned, stem='generated'):
        emitted = compile_source(text)
        il = directory / (stem + '.ssa')
        assembly = directory / (stem + '.s')
        obj = directory / (stem + '.o')
        il.write_text(emitted)
        fresh_output([qbe, '-t', 'amd64_sysv', '-o', assembly, il], assembly)
        fresh_output([host, '-c', assembly, '-o', obj], obj)
        local_layout(emitted, obj, assembly.read_text(), owned)
        return obj

    for text, owned in programs:
        emitted = compile_source(text)
        for name, (size, alignment) in owned.items():
            assert f'data ${name} = align {alignment} {{ z {size} }}' in emitted.splitlines()
        native_program(text)
        if qbe:
            obj = qbe_object(text, owned)
            executable = directory / 'generated'
            fresh_output([host, obj, '-o', executable], executable)
            assert invoke([executable]).returncode == 42, text

    supported = set()
    for feature, text in feature_probes.items():
        probe = directory / 'probe.c'
        output = directory / 'probe.o'
        probe.write_text(text + '\n')
        output.unlink(missing_ok=True)
        result = invoke([host, *flags, '-c', probe, '-o', output])
        if result.returncode == 0:
            assert not result.stdout and not result.stderr and output.is_file()
            assert output.stat().st_size > 0
            supported.add(feature)
        else:
            assert exact_legacy_probe(feature, text, result, probe), result
            for changed in [
                subprocess.CompletedProcess([], 1, 'unexpected stdout', result.stderr),
                subprocess.CompletedProcess([], 1, '', result.stderr + 'unparsed failure\n'),
                subprocess.CompletedProcess([], 0, '', result.stderr),
                subprocess.CompletedProcess([], 1, '', result.stderr + 'LLVM ERROR: crash\n'),
            ]:
                assert not exact_legacy_probe(feature, text, changed, probe)
            assert not exact_legacy_probe(feature, text + ' ', result, probe)
    query_native = 0
    for text, owned in query_programs:
        compile_source(text)
        required = {'typeof', 'nullptr'} if 'nullptr' in text else {'typeof'}
        if required <= supported:
            native_program(text)
            query_native += 1
        if qbe:
            obj = qbe_object(text, owned)
            executable = directory / 'query'
            fresh_output([host, obj, '-o', executable], executable)
            assert invoke([executable]).returncode == 42, text

    for text in constraints:
        compile_source(text, False)
        source.write_text(text + '\n')
        result = invoke([host, *flags, '-c', source, '-o', directory / 'invalid.o'])
        assert native_constraint(result, source), (text, result.stderr)
    # Driver/ICE failures and unrelated error text cannot inflate the native
    # constraint agreement count.
    valid_diagnostic = str(source) + ':1:1: error: invalid array type\n'
    assert native_constraint(subprocess.CompletedProcess([], 1, '', valid_diagnostic), source)
    for status, out, err in [
        (0, '', valid_diagnostic), (2, '', valid_diagnostic),
        (1, 'unexpected output', valid_diagnostic),
        (1, '', 'cc: error: unrecognized command-line option\n'),
        (1, '', str(source) + ':1:1: internal compiler error: crash\n'),
        (1, '', valid_diagnostic + 'LLVM ERROR: crash\n'),
    ]:
        assert not native_constraint(subprocess.CompletedProcess([], status, out, err), source)
    for text in linkage_refusals + subset_refusals:
        compile_source(text, False)  # UB/subset probes NEVER execute.
    for text in acceptance_only:
        compile_source(text)
    for text in [
        'static int items[];', 'static int items[]; static int items[3];',
        'typedef int A[]; static A items;', 'static typeof(int[]) items;',
    ]:
        compile_source(text, False, 'internal tentative object requires a complete type at its declaration')

    # Legal source-point completeness comes only from PRIOR visible declarations.
    compile_source('static int items[3]; static int items[];')
    compile_source('static int (*items[2])[];')
    for amount in (262144, 262145):
        compile_source(f'static int items[{amount}];', amount == 262144)
    for amount in (256, 257):
        compile_source('static int ' + ','.join(f'a{i}[2]' for i in range(amount)) + ';',
                       amount == 256)
    for amount in (512, 513):
        compile_source('static int ' + ','.join(['items[2]'] * amount) + ';',
                       amount == 512)
    with open('/dev/full', 'w') as full:
        source.write_text('static int items[3];\n')
        result = subprocess.run([str(compiler), str(source)], stdout=full,
                                stderr=subprocess.PIPE, text=True, timeout=15)
        assert result.returncode == 1 and 'cannot write QBE output' in result.stderr

    # Distinct same-spelled internal arrays in two TUs, tested in BOTH backend
    # directions. A wrongly exported array causes a link conflict or wrong value.
    owner = ('static int items[3]; int *address(void) { return items; } '
             'int set(void) { if(items[0] || items[2]) return 0; items[2]=40; return items[2]; }')
    companion = ('static int items[5]; int set(void); int *address(void); '
                 'int main(void) { if(items[0] || items[4] || address()==items) return 1; '
                 'items[4]=2; int x=set(); return x+items[4]; }')
    for index, (generated, native) in enumerate(((owner, companion), (companion, owner))):
        native_path = directory / 'companion.c'
        native_path.write_text(native + '\n')
        native_obj = directory / 'companion.o'
        fresh_output([host, *flags, '-O0', '-c', native_path, '-o', native_obj], native_obj)
        if qbe:
            obj = qbe_object(generated, {'items': (12 if index == 0 else 20, 4)}, f'paired{index}')
            executable = directory / 'paired'
            fresh_output([host, obj, native_obj, '-o', executable], executable)
            assert invoke([executable]).returncode == 42

print(f'Static fixed arrays passed: {len(programs)} unchanged native runtime agreements, '
      f'{len(query_programs)} C23 fixtures ({query_native} native agreements, '
      f'{len(query_programs)-query_native} exact legacy-gated originals), '
      f'{len(constraints)} native constraints, '
      f'{len(linkage_refusals)} compile-only linkage refusals, {len(subset_refusals)} subset refusals; '
      'source-point completeness, per-array/object/declaration boundaries, output failure'
      + ('; QBE runtime/local BSS layout and both-direction isolated-TU ABI passed' if qbe else ''))
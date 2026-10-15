"""Compare supported macro token kinds AND spellings with the host preprocessor."""
import os
import random
import shlex
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
driver = root / "build" / "pp_oracle"
host = shlex.split(os.environ.get("HOST_CC", "cc"))
examples = [
    "#define X 42\nX X\n#undef X\nX\n#define X 7\nX\n",
    "#define A B\n#define B A\nA B A B\n",
    "#define A 1 B\n#define B 2 A\nA B\n",
    "#define A B C\n#define B A\n#define C A\nA B C\n",
    "#define A A A\nA A\n",
    "#define A B B\n#define B C C\n#define C B A\nA\n",
    "#define E\n#define A E\n#define B A A\nE A B 1\n",
    "#define X int\n#define int 9\nX\n#undef int\nX\n",
    "#define int value\n#define return 42\nint return\n",
    "#define X (1 +2)\n#define X /* comment */ (1\t+2)\nX\n",
    "%:define X 3\nX\n%:undef X\nX\n",
    "#define X ret\\\nurn\n#define VALUE 4\\\n2\nX VALUE\n",
    "#define A B\nA\n#define B 3\nA\n#undef B\nA\n",
    "#define A B\n#define B A\nA\n#undef A\n#define A 5\nB\n",
    "#define X/* across\nlines */(7)\nX\n",
    "#define ONE 1\n#define PLUS +\nONE 2 PLUS+\n",
    "#define X (\nX 1 )\n",
]
examples += [
    "#define F() 7\nF F() F (\n)\n",
    "#define F()\nF() F() F\n",
    "#define F()7\n#define F( /**/ ) 7\nF()\n",
    "#define F() 7\n#define A F\nA()\n",
    "#define F() 7\n#define A F(\nA )\n",
    "#define F() 7\n#define LP (\nF LP )\n",
    "#define F() 7\n#define E\nF E ()\n",
    "#define F() F()\nF() F()\n",
    "#define F() G()\n#define G() F()\nF() G()\n",
    "#define A F()\n#define F() A\nA F()\n",
    "#define A F\n#define F() A\nA() A()() A()()()\n",
    "#define F() G\n#define G() F\nF()() F()()() F()()()()\n",
    "#define F() 7\n#define A F() F\nA()\n",
    "#define F() G\n#define G() 7\nF()()\n",
    "#define F() G\n#define G() 7\n#define X F()()\nX\n",
    "#define F() 7\nF/**/(/**/) F\\\n()\n",
    "#define F() 7\nF()\n#undef F\n#define F 9\nF\n",
    "#define F 7\nF\n#undef F\n#define F() 9\nF()\n",
    "#define int() 7\nint int() int\n",
    "#define F() 12u \"unused\"\nF\n",
]
# Deterministic cyclic graphs exercise disabled ancestors and repeated rescans.
random_source = random.Random(42)
for _ in range(80):
    lines = []
    names = [f"M{i}" for i in range(8)]
    words = names + ["1", "2", "value", "+", "int"]
    for name in names:
        body = " ".join(random_source.choice(words)
                        for _ in range(random_source.randrange(3)))
        lines.append(f"#define {name} {body}\n")
    lines.append(" ".join(names) + "\n")
    examples.append("".join(lines))

# Zero-parameter calls form cyclic graphs; object aliases cross source frames.
for _ in range(80):
    lines = []
    names = [f"F{i}" for i in range(8)]
    for name in names:
        body = " ".join(random_source.choice(names) + "()"
                        for _ in range(random_source.randrange(3)))
        lines.append(f"#define {name}() {body}\n")
    lines.append("#define ALIAS F0\nALIAS() " + " ".join(name + "()" for name in names) + "\n")
    examples.append("".join(lines))

# A long chain consumes source delimiters while completed frames disappear.
lines = [f"#define F{i}() F{i+1}\n" for i in range(200)]
lines.append("#define F200() 1\nF0" + "()" * 201 + "\n")
examples.append("".join(lines))
examples += [
    "#define ID(x) x\nID(42) ID(ID(3)) ID()\n",
    "#define ADD(a,b) ((a)+(b))\nADD(1,2) ADD(ADD(3,4),5)\n",
    "#define KEEP(a,b) a b\nKEEP(,) KEEP(1,) KEEP(,2)\n",
    "#define ID(x) x\n#define EMPTY\nID(EMPTY) ID((1,2))\n",
    "#define DROP(x) 7\nDROP(12u) DROP(@) DROP(#) DROP(UNKNOWN(1,2))\n",
    "#define BAD(a,b) a b\n#define DROP(x) 7\nDROP(BAD(1))\n",
    "#define DROP(x) 7\n#define OUT(x) DROP(x)\nOUT(12u)\n",
    "#define ID(x) x\n#define F() 7\nID(F)()\n",
    "#define ID(x) x\n#define F(x) x\nID(F)(7)\n",
    "#define F(x) x x\nF(F(1))\n",
    "#define F(x) F(x)\nF(1)\n",
    "#define F(x) G(x)\n#define G(x) F(x)\nF(1) G(2)\n",
    "#define X 9\n#define F(X) X\nF(3)\n",
    "#define F(int) int\nF(7)\n",
    "#define C 1,2\n#define ADD(a,b) a+b\n#define CALL(x) ADD(x)\nCALL(C)\n",
    "#define ID(x) x\n#define LP (\n#define F() 7\nID(F LP) )\n",
    "#define foo(x) bar x\n#define bar(x) foo x\nfoo(foo)(2)\n",
    "#define f(x) x x\n#define g f\nf(g)(2)\n",
    "#define A F(A)\n#define F(x) x\nA\n",
    "#define F(x) x\n#define G() F\nF(G)()(7)\n",
    "#define F(x,y) x+y\n#define F( x , y ) x+y\nF(1,2)\n",
    "#define F(x) x\nF(1)\n#undef F\n#define F(a,b) a b\nF(2,3)\n",
    "#define ID(x) x\nID(ID(ID(ID(1))))\n",
    "#define A(x) x()\n#define B() 3\nA(B)\n",
    "#define BOTH(a,b) a b\n#define F(x) x\nBOTH(F,(3))\n",
    "#define RET(x) return x\nRET(3)\n",
    "#define F(x) x\nF(/**/) F(\n) F(\\\n7)\n",
    "#define DROP(a,b) 7\nDROP({1,2}) DROP([1,2])\n",
]
# Bounded expression trees vary prescan depth, repeat substitutions and commas.
for _ in range(80):
    def expression(depth):
        if not depth:
            return str(random_source.randrange(10))
        if random_source.randrange(2):
            return "TWICE(" + expression(depth - 1) + ")"
        return "ADD(" + expression(depth - 1) + "," + expression(depth - 1) + ")"
    examples.append("#define ADD(a,b) ((a)+(b))\n#define TWICE(x) ADD(x,x)\n"
                    + expression(3) + "\n")
examples += [
    "#define x 2\n#define f(a) f(x*(a))\nf(f(1))\n",
    "#define x 2\n#define f(a) f(x*(a))\n#define g f\n#define t(a) a\nt(t(g)(0)+t)(1)\n",
    "#define f(x) x\n#define h(x) f(x)\n#define g f\nh(g)(2)\n",
    "#define A(x) x B\n#define B(x) x A\nA(B)(7)\n",
    "#define F(x) x x\n#define G(x) F(x)\nG(F)(7)\n",
    "#define F(x) x\n#define G(x) F(x)\nF(G)(F)(7)\n",
    "#define F(x) x\n#define CALL(x) F(x)\nCALL(F)(7)\n",
    "#define F(x) x F\nF(F)(7)\n",
]
for _ in range(60):
    names = [f"R{i}" for i in range(4)]
    lines = []
    for name in names:
        body = " ".join(random_source.choice(names) + "(x)"
                        for _ in range(random_source.randrange(3)))
        lines.append(f"#define {name}(x) {body}\n")
    lines.append("#define ALIAS R0\nALIAS(R1(7)) "
                 + " ".join(name + "(3)" for name in names) + "\n")
    examples.append("".join(lines))

# C23 variadics: omitted and expanded-empty tails, comma retention and boundaries.
examples += [
    "#define V(...) __VA_ARGS__\nV() V(1) V(1,2,3) V(,) V(,,)\n",
    "#define V(x,...) x __VA_ARGS__\nV() V(1) V(1,) V(1,2,3)\n",
    "#define V(x,y,...) x y __VA_ARGS__\nV(,) V(1,2) V(1,2,) V(1,2,3,4)\n",
    "#define V(...) __VA_OPT__(7)\n#define E\nV() V(E) V(,) V(E,E)\n",
    "#define E()\n#define V(...) __VA_OPT__(__VA_ARGS__)\nV(E()) V(7) V(1,2)\n",
    "#define V(...) f(0 __VA_OPT__(,) __VA_ARGS__)\nV() V(a,b,c)\n",
    "#define V(x,...) f(0,x __VA_OPT__(,) __VA_ARGS__)\nV(a) V(a,) V(a,b,c)\n",
    "#define V(...) __VA_OPT__() __VA_OPT__() __VA_ARGS__\nV() V(7)\n",
    "#define V(...) __VA_OPT__((__VA_ARGS__))\nV() V(1,2)\n",
    "#define DROP(...) 7\n#define BAD(x,y) x\nDROP(BAD(1)) DROP(@,#,12u)\n",
    "#define V(...) __VA_OPT__(7)\nV(12u) V(@) V(#)\n",
    "#define V(...) V(__VA_ARGS__)\nV() V(7) V(V(1))\n",
    "#define V(...) W(__VA_ARGS__)\n#define W(...) V(__VA_ARGS__)\nV(7) W(1,2)\n",
    "#define V(...) __VA_ARGS__ __VA_ARGS__\nV(V(7))\n",
    "#define V(...) __VA_OPT__(V(__VA_ARGS__))\nV() V(7) V(V(7))\n",
    "#define V(...) __VA_OPT__(G)\n#define G(x) x\nV(1)(7)\n",
    "#define V(...) __VA_OPT__(G() __VA_ARGS__)\n#define G() 7\nV(2)\n",
    "#define LP() (\n#define G(x) 42\n#define V(r,x,...) __VA_OPT__(G r x) )\nV(LP(),0,1)\n",
    "#define V(x,...) __VA_OPT__(x) (7)\n#define G(x) x\nV(G,1)\n",
    "#define V(x,...) x __VA_OPT__() ()\n#define G() 7\nV(G) V(G,1)\n",
    "#define V(...) __VA_ARGS__\n#define CALL(...) V(__VA_ARGS__)\n#define C 1,2\nCALL(C)\n",
    "#define V(...) __VA_OPT__(7)\n#define DROP(...)\nV(DROP(1,2))\n",
    "#define V(...) __VA_OPT__(DROP(__VA_ARGS__))\n#define DROP(...)\nV(1,2)\n",
    "#define V(...) __VA_OPT__(7)\n#define CALL(x,...) V(__VA_ARGS__)\nCALL(0) CALL(0,) CALL(0,1,2)\n",
    "#define V(...) __VA_OPT__(1) + __VA_OPT__(2)\nV() V(7)\n",
    "#define V(...) __VA_OPT__(7)\n#define V( ... ) __VA_OPT__(7)\nV(1)\n",
    "#define V(x,...) x __VA_ARGS__\n#undef V\n#define V(...) __VA_OPT__(7)\nV(1)\n",
    "#define V(...) __VA_OPT__(7)\nV({1,2}) V([1,2]) V((1,2))\n",
    "#define V(...) __VA_OPT__(7)\nV(/**/) V(\n) V(\\\n7)\n",
    "#define V(...) __VA_OPT__(G)\n#define G(x) 7\n#define A V(1)\nA(2)\n",
]
# Generated presence combinations include empty macros that expand to commas.
for _ in range(100):
    values = [random_source.choice(["", "E", "Z()", "7", "C", "(1,2)"])
              for _ in range(random_source.randrange(5))]
    examples.append("#define E\n#define Z()\n#define C ,\n"
                    "#define V(...) __VA_OPT__((__VA_ARGS__))\nV("
                    + ",".join(values) + ")\n")
# Recursive variadic graphs stress suppression in selected bodies and arguments.
for _ in range(60):
    names = [f"V{i}" for i in range(4)]
    lines = []
    for name in names:
        target = random_source.choice(names)
        lines.append(f"#define {name}(...) __VA_OPT__({target}(__VA_ARGS__))\n")
    lines.append(" ".join(name + "(7)" for name in names) + "\n")
    examples.append("".join(lines))

# Expanded-pp inspection retains string tokens without enabling C string semantics.
pp_examples = [
    '#define S(x) #x\n#define A 42\nS(A) S(A + 1) S()\n',
    '#define S(x) %: x\nS(a/**/b) S(  a\t +\n b  )\n',
    '#define S(x) #x\nS(hello) S(1+2) S(1 + 2) S((1,2))\n',
    '#define S(x) #x\n#define BAD(a,b) a\nS(BAD(1)) S(12u) S(@) S(#)\n',
    '#define S(...) #__VA_ARGS__\nS() S(,) S(a,b) S(a, b) S( a , b )\n',
    '#define S(x,...) #x #__VA_ARGS__\nS(a) S(a,) S(a,b,c)\n',
    '#define S(...) __VA_OPT__(#__VA_ARGS__)\n#define E\nS() S(E) S(7) S(,)\n',
    '#define S(x,...) __VA_OPT__(#x)\nS(7) S(7,1)\n',
    '#define S(x) #x #x\nS(a+b)\n',
    '#define S(x) #x\n#define S(x) #x\nS(a)\n#undef S\n#define S(x) x\nS(7)\n',
    '#define S(x) #x\n#define X(x) S(x)\n#define A 7\nX(A) X(S(a)) X(S(S(a)))\n',
    '#define S(x) #x\nS(a\\\nb) S(a/* across\nlines */b)\n',
    '#define S(x) #x\nS("a\\nb") S(\'a\') S(\'\\\\\')\n',
    '#define S(x) #x\nS("a\\\"b") S("\\\\") S(L"wide") S(u8"text") S(U\'x\')\n',
    '#define S(x) #x\nS(%: %:%: <% %> <: :> ::)\n',
    '#define S(x) #x\n#define G(x) x\nG(S(a))\n',
]
spacing_cases = [
    '#define E\nX(a+E+b)', '#define E\nX(a E+b)',
    '#define F(x) a+x\nX(F( b))', '#define F(x) a x+b\nX(F())',
    '#define A 1\nX(a+A)', '#define F(x) x\nX(a+F( b))',
    '#define V(...) a __VA_OPT__() b\nX(V(1)) X(V())',
    '#define V(...) a+__VA_OPT__() b\nX(V(1)) X(V())',
    '#define V(...) a __VA_OPT__()b\nX(V(1)) X(V())',
    '#define V(...) __VA_OPT__(a) __VA_OPT__(b)\nX(V(1)) X(V())',
    '#define V(...) a __VA_OPT__(__VA_ARGS__)b\nX(V())',
    '#define F(x) a x b\nX(F())', '#define F(x) a+x+b\nX(F())',
    '#define F(x) a x\nX(F())', '#define F(x) x b\nX(F())',
]
for body in spacing_cases:
    pp_examples.append('#define S(x) #x\n#define X(x) S(x)\n' + body + '\n')
# Two-level stringizing observes spacing through parameter and empty streams.
for _ in range(100):
    before, after, argument_space = [random_source.choice(['', ' ', '\t', '/**/'])
                                     for _ in range(3)]
    argument = random_source.choice(['', 'E', '7', 'E+7', '7+E', '(1,2)'])
    pp_examples.append('#define S(x) #x\n#define X(x) S(x)\n#define E\n'
                       f'#define F(x) a+{before}x{after}+b\nX(F({argument_space}{argument}))\n')
# Re-stringizing generated spelling repeatedly exercises owned-view lifetimes.
for depth in range(1, 12):
    pp_examples.append('#define S(x) #x\n#define X(x) S(x)\n'
                       + 'X(' * depth + '7' + ')' * depth + '\n')

# Stringized optional operands substitute parameters but do not rescan body names.
pp_examples += [
    '#define V(...) #__VA_OPT__(a)\n#define E\nV() V(E) V(1) V(,)\n',
    '#define V(x,...) #__VA_OPT__(x)\n#define A 7\nV(A) V(A,) V(A,1)\n',
    '#define V(...) %: __VA_OPT__(a)\nV() V(1)\n',
    '#define V(...) #__VA_OPT__()\nV() V(1)\n',
    '#define V(...) #__VA_OPT__(  a /**/ b  )\nV(1)\n',
    '#define A 7\n#define V(x,...) #__VA_OPT__(x A)\nV(A,1)\n',
    '#define BAD(a,b) a+b\n#define V(x,...) #__VA_OPT__(BAD(x))\nV(7,1)\n',
    '#define S(x) #x\n#define V(x,...) #__VA_OPT__(x)\nV(S(a),1)\n',
    '#define V(x,...) #__VA_OPT__(#x)\n#define A 7\nV(A,1) V(A)\n',
    '#define V(x,...) #__VA_OPT__(%: x)\nV(a+b,1)\n',
    '#define V(...) #__VA_OPT__(#__VA_ARGS__)\nV() V(7) V(a, b)\n',
    '#define V(...) #__VA_OPT__(__VA_ARGS__)\n#define A 7\nV(A) V(A,2) V(,)\n',
    '#define V(x,...) #__VA_OPT__(x x)\n#define A 7\nV(A,1)\n',
    '#define V(...) #__VA_OPT__(V(__VA_ARGS__))\nV(7) V(V(1))\n',
    '#define V(...) #__VA_OPT__(NEXT())\n#define NEXT() 7\nV(1)\n',
    '#define LP() (\n#define V(x,...) #__VA_OPT__(F x) )\nV(LP(),1)\n',
    '#define V(...) #__VA_OPT__(F) (7)\n#define F(x) x\nV(1)\n',
    '#define V(...) #__VA_OPT__(a) #__VA_OPT__(b)\nV(1) V()\n',
    '#define V(...) #__VA_OPT__(a) __VA_OPT__(b)\nV(1) V()\n',
    '#define V(...) #__VA_OPT__(a)\n#define V(...) #__VA_OPT__(a)\nV(1)\n',
    '#define V(...) #__VA_OPT__(a)\n#undef V\n#define V(x) #x\nV(7)\n',
    '#define V(x,...) #__VA_OPT__(x)\nV(12u,1)\n',
    '#define V(x,...) #__VA_OPT__(#x)\nV("a\\nb",1)\n',
    '#define V(x,...) #__VA_OPT__(x)\nV(L"wide",1) V(U\'x\',1)\n',
    '#define V(x,...) #__VA_OPT__(x)\n#define E\nV(E,1)\n',
    '#define V(x,...) #__VA_OPT__(x __VA_ARGS__)\nV((1,2),3,4)\n',
]
for _ in range(100):
    argument = random_source.choice(['A', 'P(2)', '1+2', '(1,2)', 'E'])
    tail = random_source.choice(['', 'E', '1', '1,2', 'P(3)'])
    pp_examples.append('#define A 7\n#define E\n#define P(x) (x)\n'
                       '#define V(x,...) #__VA_OPT__(x + A __VA_ARGS__)\n'
                       f'V({argument},{tail})\n')
# Argument prescan can nest optional-stringizing cursors, although definition
# syntax correctly forbids directly nested __VA_OPT__ constructs.
for depth in range(1, 9):
    expression = 'V(' * depth + '7' + ',1)' * depth
    pp_examples.append('#define V(x,...) #__VA_OPT__(x)\n' + expression + '\n')

# Pasting acts on definition operators only, before ordinary macro rescan.
pp_examples += [
    '#define C(a,b) a##b\nC(a,b) C(,b) C(a,) C(,) C(a b,c d)\n',
    '#define C(a,b,c) a##b##c\nC(a,b,c) C(a,,c) C(,b,) C(,,)\n',
    '#define C(a,b) a %:%: b\nC(a,b) C(1,2)\n',
    '#define X 1 ## 2\nX\n',
    '#define A 7\n#define C(a,b) a##b\n#define X(a,b) C(a,b)\nC(A,B) X(A,B) C(A,)\n',
    '#define C(a,b) a##b\nC(+,=) C(<,=) C(+, +) C(1,e2) C(1.,5)\n',
    '#define C(a,b) a##b\nC(L,"x") C(u8,"x") C(U,\'x\')\n',
    '#define W(x) L ## #x\nW(a+b) W()\n',
    '#define C(a,b) a##b\n#define ab 7\nC(a,b)\n',
    '#define C(a,b) a##b\n#define ID(x) x\nC(I,D)(7)\n',
    '#define C(a,b) a##b\n#define A C(A,)\nA\n',
    '#define C(a,b) a##b\n#define A B\n#define B A\nC(A,) C(,B)\n',
    '#define hash_hash # ## #\n#define mkstr(a) #a\n#define between(a) mkstr(a)\n'
    '#define join(c,d) between(c hash_hash d)\njoin(x,y)\n',
    '#define C(a,b) a##b\nC(,##) C(##,)\n',
    '#define C(a,b) a##b\n#define S(x) #x\n#define X(x) S(x)\nX(C(a b,c d))\n',
    '#define F(x,...) #__VA_OPT__(x##x x##x)\nF(,0) F(a,1) F(a)\n',
    '#define F(...) a ## __VA_OPT__(b)\nF() F(1)\n',
    '#define F(...) __VA_OPT__(a) ## b\nF() F(1)\n',
    '#define F(...) __VA_OPT__(a) ## __VA_OPT__(b)\nF() F(1)\n',
    '#define F(...) a ## __VA_OPT__() ## b\nF() F(1)\n',
    '#define A 7\n#define F(...) X ## __VA_OPT__(__VA_ARGS__)\nF(A) F()\n',
    '#define F(x,...) #__VA_OPT__(x##y)\n#define A 7\nF(A,1)\n',
    '#define F(x,...) #__VA_OPT__(x##y) )\nF(a,1)\n',
    '#define F(x) x##x\nF(a b) F()\n',
    '#define F(x,y) x##y #x y\n#define A 7\nF(A,B)\n',
    '#define F(...) a##__VA_ARGS__\nF() F(b,c)\n',
    '#define F(x,y) x##y\nF(ret,urn) F(4,2)\n',
]
# Enumerate all empty-operand combinations and multi-token boundaries.
for a in ['', 'a', 'a b']:
    for b in ['', 'b', 'b c']:
        for c in ['', 'c', 'c d']:
            pp_examples.append('#define C(a,b,c) a##b##c\n' + f'C({a},{b},{c})\n')
for _ in range(70):
    a = random_source.choice(['', 'a', 'b', 'c'])
    b = random_source.choice(['', 'a', 'b', 'c'])
    pp_examples.append('#define C(a,b) a##b\n#define X(a,b) C(a,b)\n'
                       '#define a 1\n#define b 2\n#define c 3\n'
                       + f'C({a},{b}) X({a},{b})\n')

pp_examples += [
    '#define BAD(a,b) a+b\n#define C(x) pre##x\nC(BAD(1))\n',
    '#define C(a,b) a##b\n#define F(x) C(x,)\nF(F)(1)\n',
    '#define C(a,b) a##b\n#define A C(A,)\n#define B C(A,)\nB\n',
    '#define C(a,b) a##b\n#define F(x) x\n#define G(x) C(F,)(x)\nG(G)(7)\n',
]
for _ in range(40):
    names = [f'N{i}' for i in range(4)]
    lines = ['#define C(a,b) a##b\n']
    for name in names:
        target = random_source.randrange(4)
        lines.append(f'#define {name}(x) C(N,{target})(x)\n')
    lines.append(' '.join(name + '(7)' for name in names) + '\n')
    pp_examples.append(''.join(lines))

# Observed GCC/Clang whitespace disagreements are explicit policy regressions,
# not claimed cross-host agreement or a ruling on ISO's intended interpretation.
policy_prefix = '#define S(x) #x\n#define X(x) S(x)\n'
policy_examples = [
    ('#define V(...) a+__VA_OPT__( )b\nX(V(1)) X(V())\n',
     ['a+b', 'a+b'], ['a+ b', 'a+ b']),
    ('#define V(...) a __VA_OPT__(b )c\nX(V(1)) X(V())\n',
     ['a bc', 'a c'], ['a b c', 'a c']),
    ('#define V(...) a+__VA_OPT__( b)c\nX(V(1)) X(V())\n',
     ['a+bc', 'a+c'], ['a+ bc', 'a+ c']),
    ('#define E\n#define F(x) a+x+b\nX(F( E)) X(F(E E)) X(F(7 E)) X(F(E 7))\n',
     ['a++b', 'a+ +b', 'a+7 +b', 'a+ 7+b'], ['a++b', 'a++b', 'a+7+b', 'a+7+b']),
    ('#define E\n#define F(x) a x+b\nX(F(7 E))\n',
     ['a 7 +b'], ['a 7+b']),
]

with tempfile.TemporaryDirectory(prefix="kcc-macro-oracle-") as directory:
    source = Path(directory) / "input.c"
    expanded = Path(directory) / "expanded.c"
    for pp_mode, texts in [(False, examples), (True, pp_examples)]:
        command = [str(driver)] + (["--pp"] if pp_mode else [])
        for text in texts:
            source.write_text(text)
            reference = subprocess.run(host + ["-std=c2x", "-E", "-P", str(source)],
                                       capture_output=True, text=True, timeout=5)
            assert reference.returncode == 0, (text, reference.stderr)
            expanded.write_text(reference.stdout)
            actual = subprocess.run(command + [str(source)],
                                    capture_output=True, text=True, timeout=5)
            expected = subprocess.run(command + [str(expanded)],
                                      capture_output=True, text=True, timeout=5)
            assert actual.returncode == expected.returncode == 0, (text, actual.stderr, expected.stderr)
            assert actual.stdout == expected.stdout, (text, actual.stdout, expected.stdout)
    for body, chosen, alternate in policy_examples:
        text = policy_prefix + body
        source.write_text(text)
        reference = subprocess.run(host + ["-std=c2x", "-E", "-P", str(source)],
                                   capture_output=True, text=True, timeout=5)
        assert reference.returncode == 0, (text, reference.stderr)
        expanded.write_text(reference.stdout)
        actual = subprocess.run([str(driver), "--pp", str(source)],
                                capture_output=True, text=True, timeout=5)
        expected = subprocess.run([str(driver), "--pp", str(expanded)],
                                  capture_output=True, text=True, timeout=5)
        chosen_dump = "".join('string:"' + value + '"\n' for value in chosen)
        alternate_dump = "".join('string:"' + value + '"\n' for value in alternate)
        assert actual.returncode == expected.returncode == 0, (text, actual.stderr, expected.stderr)
        assert actual.stdout == chosen_dump, (text, actual.stdout, chosen_dump)
        assert expected.stdout in (chosen_dump, alternate_dump), (text, expected.stdout)
    # N3096 6.10.4.1 example H4 retains inner placemarkers for the outer paste.
    # Legacy hosts can remove them early and emit ab; never call that agreement.
    source.write_text('#define F(x,...) __VA_OPT__(a x##x) ## b\nF(,1) F(x,1) F(x)\n')
    actual = subprocess.run([str(driver), "--pp", str(source)], capture_output=True, text=True, timeout=5)
    reference = subprocess.run(host + ["-std=c2x", "-E", "-P", str(source)], capture_output=True, text=True, timeout=5)
    assert reference.returncode == 0, reference.stderr
    expanded.write_text(reference.stdout)
    observed = subprocess.run([str(driver), "--pp", str(expanded)], capture_output=True, text=True, timeout=5)
    standard = 'identifier:a\nidentifier:b\nidentifier:a\nidentifier:xxb\nidentifier:b\n'
    legacy = 'identifier:ab\nidentifier:a\nidentifier:xxb\nidentifier:b\n'
    assert actual.returncode == observed.returncode == 0, (actual.stderr, observed.stderr)
    assert actual.stdout == standard, actual.stdout
    assert observed.stdout in (standard, legacy), observed.stdout
    # This inactive-body arity diagnostic differs between the two local hosts.
    # kcc intentionally does not expand named parameters of an inactive region.
    source.write_text('#define BAD(a,b) a+b\n#define E\n'
                      '#define V(x,...) #__VA_OPT__(x)\nV(BAD(1),E)\n')
    actual = subprocess.run([str(driver), "--pp", str(source)],
                            capture_output=True, text=True, timeout=5)
    reference = subprocess.run(host + ["-std=c2x", "-E", "-P", str(source)],
                               capture_output=True, text=True, timeout=5)
    assert actual.returncode == 0 and actual.stdout == 'string:""\n', actual.stderr
    assert reference.returncode in (0, 1), reference.stderr
    if reference.returncode:
        assert "macro" in reference.stderr and "argument" in reference.stderr, reference.stderr
print(f"Macro token/spelling oracle passed ({len(examples)} language + "
      f"{len(pp_examples)} expanded-pp agreements; "
      f"1 C23 normative example; {len(policy_examples)} whitespace + "
      f"1 inactive-argument diagnostic policies; {host[0]})")

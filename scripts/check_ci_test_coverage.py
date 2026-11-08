#!/usr/bin/env python3
"""Fail closed if make test stops covering the separate codegen gate.

The targets are intentionally explicit, single-line Makefile declarations with
one command per recipe line. Reject unsupported shapes rather than guessing at
make semantics. The only normalized command difference is the redundant QBE
assignment, because both targets export the same QBE value.
"""
from collections import Counter
from pathlib import Path
import re
import sys


class CoverageError(ValueError):
    pass


def target(text, name):
    lines = text.splitlines()
    exports = {}
    declaration = None
    for i, line in enumerate(lines):
        if not line.startswith(name + ':'):
            continue
        body = line[len(name) + 1:].strip()
        if body.startswith('export '):
            export = body[len('export '):]
            if ' := ' not in export:
                raise CoverageError(f'{name}: unsupported export {line}')
            key, value = export.split(' := ', 1)
            if key in exports:
                raise CoverageError(f'{name}: duplicate export {key}')
            exports[key] = value
        else:
            if declaration is not None or not body or '\\' in body or '$' in body:
                raise CoverageError(f'{name}: unsupported or duplicate declaration')
            declaration = (i, body.split())
    if declaration is None:
        raise CoverageError(f'{name}: missing target')
    i, prerequisites = declaration
    commands = []
    for line in lines[i + 1:]:
        if line.startswith('\t'):
            command = line[1:]
            if not command or '\\' in command:
                raise CoverageError(f'{name}: unsupported recipe {line}')
            prefix = 'QBE="$(QBE)" '
            if command.startswith(prefix):
                command = command[len(prefix):]
            commands.append(command)
        elif line.strip() and not line.lstrip().startswith('#'):
            if not re.match(r'^[^\s:#=]+\s*:', line):
                raise CoverageError(f'{name}: unsupported line in recipe block: {line}')
            break
    if not commands:
        raise CoverageError(f'{name}: missing recipe')
    return exports, Counter(prerequisites), Counter(commands)


def check(text):
    # Make can conditionally replace or extend rules outside the parsed recipe
    # blocks. Reject those forms rather than trusting a textual subset check.
    for line in text.splitlines():
        if line.startswith('\t') or not line.strip() or line.lstrip().startswith('#'):
            continue
        if line == '-include $(wildcard build/obj/src/*.d build/obj/tests/*.d build/*.d)':
            continue  # Compiler-generated object dependency files in a clean CI checkout.
        if (re.match(r'^\s*(?:ifeq|ifneq|ifdef|ifndef|else|endif|-?include|sinclude|define|endef|override)\b', line)
                or re.match(r'^\s*\.ONESHELL\s*:', line)
                or re.match(r'^\s*\.RECIPEPREFIX\s*[:?+!]?=', line)
                or '$(eval' in line or '${eval' in line):
            raise CoverageError(f'unsupported Makefile directive: {line}')
        rule = re.match(r'^([^:=]+):', line)
        if rule:
            names = rule.group(1).split()
            if any(name in ('test', 'test-codegen') for name in names) and len(names) != 1:
                raise CoverageError(f'unsupported shared target rule: {line}')
    test_exports, test_dependencies, test_commands = target(text, 'test')
    codegen_exports, codegen_dependencies, codegen_commands = target(text, 'test-codegen')
    expected = {'QBE': '$(QBE)', 'KCC_SOURCE': '$(CURDIR)',
                'KCC_RUNTIME_LDFLAGS': '$(LDFLAGS)'}
    if test_exports != expected or codegen_exports != expected:
        raise CoverageError('target-specific exports changed; review CI coverage')
    missing_dependencies = codegen_dependencies - test_dependencies
    missing_commands = codegen_commands - test_commands
    if missing_dependencies or missing_commands:
        raise CoverageError(f'test-codegen coverage missing: dependencies={list(missing_dependencies.elements())}; '
                            f'commands={list(missing_commands.elements())}')
    return sum(codegen_commands.values())


def main():
    path = Path(__file__).resolve().parents[1] / 'Makefile'
    try:
        count = check(path.read_text())
    except CoverageError as exc:
        print(f'CI coverage check failed: {exc}', file=sys.stderr)
        return 1
    print(f'CI coverage: all {count} codegen recipes and prerequisites covered by test')
    return 0


if __name__ == '__main__':
    sys.exit(main())

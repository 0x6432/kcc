"""Link flags for generated programs using the instrumented KCC runtime.

The compiler test gates export their linker flags so sanitizers used to build
libkccrt are also linked into executables that consume the archive. Standalone
test invocations can set KCC_RUNTIME_LDFLAGS explicitly.
"""
import os
import shlex


def runtime_link_flags():
    return shlex.split(os.environ.get('KCC_RUNTIME_LDFLAGS', ''))

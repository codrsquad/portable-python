import os
import sys
from unittest.mock import patch

import runez

from portable_python.builder import BuildSetup
from portable_python.builder.python import Cpython

from .conftest import dummy_tarball


def test_module_invocation(cli):
    cli.exercise_main("-mportable_python", "src/portable_python/cli.py")


def test_build(cli):
    v = BuildSetup.supported.cpython.latest
    cli.run("--dryrun", "build", "2.7.1", "--target=foo-bar")
    assert cli.failed
    assert "cpython:2.7.1 is not in the supported list" in cli.logged
    assert "Compiling 0 external modules" in cli.logged
    assert "Compiling on platform 'foo' is not yet supported" in cli.logged

    cli.run("--dryrun", "build", v, "--target=darwin-x86_64")
    assert cli.succeeded

    # Simulate some tcl/tk setup, to help coverage
    bf = runez.to_path(f"build/cpython-{v}")
    runez.touch(bf / "deps/include/readline/readline.h", logger=None)
    runez.touch(bf / "build/tcl/pkgs/sqlite", logger=None)
    runez.write(bf / "build/tcl/Makefile.in", "--enable-shared foo", logger=None)
    cli.run("--dryrun", "build", v, "--target=darwin-x86_64", "-mall", "--static")
    assert cli.succeeded
    assert "Skipping xorgproto" in cli.logged
    assert f"Patched build/cpython-{v}/build/tcl/Makefile.in" in cli.logged
    assert f"Would tar build/cpython-{v}/{v} -> dist/cpython-{v}-darwin-x86_64.tar.gz" in cli.logged

    cli.run("--dryrun", "build", v, "--target=linux-x86_64", "-mall", "--prefix", "/apps/foo{python_version}")
    assert cli.succeeded
    assert f"Would run: ./configure --prefix=/apps/foo{v} --with-ensurepip=upgrade" in cli.logged
    assert "Would tar " not in cli.logged

    cli.run("--dryrun", "list")
    assert cli.succeeded

    cli.run("--dryrun", "list", "conda", "cpython")
    assert cli.succeeded


def test_failed_run(cli):
    v = BuildSetup.supported.cpython.latest
    build_path = runez.to_path(f"build/cpython-{v}")
    runez.touch("sample/README", logger=None)
    runez.compress("sample/README", "build/downloads/readline-8.1.tar.gz", logger=None)
    cli.run("build", v, "-mreadline")
    assert cli.failed
    assert "./configure is not an executable" in cli.logged
    assert os.path.exists(build_path / "build/readline/README")
    assert os.path.exists(build_path / "logs/01-readline.log")


def test_finalization(cli):
    v = BuildSetup.supported.cpython.latest
    dummy_tarball(f"Python-{v}.tar.xz")
    base = runez.to_path(f"build/cpython-{v}")
    bin = base / f"{v}/bin"

    # Triggers compilation skip
    runez.touch(base / "build/cpython/README", logger=None)

    # Create some files to be groomed by finalize()
    runez.touch(base / "deps/libs/foo.a", logger=None)
    os.chmod(base / "deps/libs/foo.a", 0o600)
    runez.touch(bin.parent / "lib/idle_test/foo", logger=None)
    runez.touch(bin.parent / "lib/__phello__.foo.py", logger=None)
    runez.touch(bin / "2to3", logger=None)
    runez.touch(bin / "foo-python", logger=None)
    runez.symlink(bin / "foo-python", bin / "python3", logger=None)  # Simulate a funky symlink, to test edge cases
    runez.write(bin / "some-exe", "#!.../bin/python3\nhello", logger=None)
    runez.write(bin / "some-exe3", "#!/bin/sh\nhello", logger=None)
    with patch("runez.run", return_value=runez.program.RunResult(code=0)):
        cli.run("build", v, "-mnone", "--x-finalize")
        assert cli.succeeded
        assert "Compiling 0 external modules" in cli.logged
        assert f"Skipping compilation of cpython {v}: build folder already there" in cli.logged
        assert "INFO Cleaned 2 build artifacts: __phello__.foo.py idle_test" in cli.logged
        assert f"Deleted build/cpython-{v}/{v}/bin/2to3" in cli.logged
        assert "Symlink foo-python <- python" in cli.logged
        assert f"Auto-corrected shebang for build/cpython-{v}/{v}/bin/some-exe" in cli.logged

    assert runez.readlines(bin / "some-exe", logger=None) == ["#!/bin/sh", '"exec" "$(dirname $0)/foo-python" "$0" "$@"', "hello"]
    assert runez.readlines(bin / "some-exe3", logger=None) == ["#!/bin/sh", "hello"]
    assert Cpython.actual_basename(bin / "python") == "foo-python"


def test_inspect(cli):
    cli.run("inspect", sys.executable, "foo")
    assert cli.succeeded
    assert "readline" in cli.logged
    assert "foo: not available" in cli.logged


def test_inspect_module():
    # Exercise _inspect code
    import portable_python._inspect

    all_modules = portable_python._inspect.get_modules(["python", "all"])
    assert "_tracemalloc" in all_modules

    # Verify convenience parsing works
    base = portable_python._inspect.get_modules([])
    with_foo = portable_python._inspect.get_modules(["python", "+,,foo"])
    assert with_foo == base + ["foo"]

    assert portable_python._inspect.get_report(["readline", "sys", "zlib"])

    # Verify edge cases don't crash
    assert portable_python._inspect.module_report("foo-bar") == "*absent*"
    assert portable_python._inspect.module_representation("foo", [])


def test_invalid(cli):
    v = BuildSetup.supported.cpython.latest
    cli.run("--dryrun", "build", "foo")
    assert cli.failed
    assert "Invalid python spec: ?foo" in cli.logged

    cli.run("--dryrun", "build", v, "-mfoo")
    assert cli.failed
    assert "Unknown modules: foo" in cli.logged

    cli.run("--dryrun", "build", v, "--build", "foo bar")
    assert cli.failed
    assert "Refusing path with space" in cli.logged

    cli.run("--dryrun", "build", "conda:1.0")
    assert cli.failed
    assert "Python family 'conda' is not yet supported" in cli.logged

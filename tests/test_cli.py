import os
import sys
from unittest.mock import patch

import runez

from portable_python.builder import BuildSetup
from portable_python.builder.python import Cpython

from .conftest import dummy_tarball


LATEST = str(BuildSetup.supported.cpython.latest)


def test_module_invocation(cli):
    cli.exercise_main("-mportable_python", "src/portable_python/cli.py")


def test_dryrun(cli):
    cli.run("--dryrun", "build", LATEST)
    assert cli.succeeded
    assert "Would tar build/cpython-{v}/{v} -> dist/{v}.tar.gz".format(v=LATEST) in cli.logged

    cli.run("--dryrun", "build", LATEST, "-mall")
    assert cli.succeeded

    cli.run("--dryrun", "build", LATEST, "--prefix", "/apps/foo{python_version}")
    assert cli.succeeded
    assert "./configure --prefix=/apps/foo" in cli.logged

    cli.run("--dryrun", "build", LATEST, "-mnone")
    assert cli.succeeded
    assert "Compiling 0 external modules" in cli.logged

    cli.run("--dryrun", "build", "2.7.1", "-mnone")
    assert cli.succeeded
    assert "cpython:2.7.1 is not in the supported list" in cli.logged

    cli.run("--dryrun", "list")
    assert cli.succeeded

    cli.run("--dryrun", "list", "conda", "cpython")
    assert cli.succeeded


def test_failed_run(cli):
    build_path = runez.to_path("build/cpython-%s" % LATEST)
    runez.touch("sample/README", logger=None)
    runez.compress("sample/README", "build/downloads/readline-8.1.tar.gz", logger=None)
    cli.run("build", LATEST, "-mreadline")
    assert cli.failed
    assert "./configure is not an executable" in cli.logged
    assert os.path.exists(build_path / "build/readline/README")
    assert os.path.exists(build_path / "logs/01-readline.log")


def test_finalization(cli):
    dummy_tarball("Python-%s.tar.xz" % LATEST)
    base = runez.to_path("build/cpython-%s" % LATEST)
    bin = base / LATEST / "bin"

    # Triggers compilation skip
    runez.touch(base / "build/cpython/README", logger=None)

    # Create some files to be groomed by finalize()
    runez.touch(bin.parent / "lib/idle_test/foo", logger=None)
    runez.touch(bin.parent / "lib/libpython.a", logger=None)
    runez.touch(bin.parent / "lib/config/libpython.a", logger=None)
    runez.touch(bin / "2to3", logger=None)
    runez.touch(bin / "foo-python", logger=None)
    runez.symlink(bin / "foo-python", bin / "python3", logger=None)  # Simulate a funky symlink, to test edge cases
    runez.write(bin / "pip", "#!.../bin/python3\nhello", logger=None)
    runez.write(bin / "pip3", "#!/bin/sh\nhello", logger=None)
    with patch("runez.run", return_value=runez.program.RunResult(code=0)):
        cli.run("build", LATEST, "-mnone", "--x-finalize")
        assert cli.succeeded
        assert "Compiling 0 external modules" in cli.logged
        assert f"Skipping compilation of cpython {LATEST}: build folder already there" in cli.logged
        assert "INFO Cleaned up 1 build artifacts" in cli.logged
        assert f"Deleted build/cpython-{LATEST}/{LATEST}/bin/2to3" in cli.logged
        assert "Symlink foo-python <- python" in cli.logged
        assert f"Auto-corrected shebang for build/cpython-{LATEST}/{LATEST}/bin/pip" in cli.logged

    assert runez.readlines(bin / "pip", logger=None) == ["#!/bin/sh", '"exec" "$(dirname $0)/foo-python" "$0" "$@"', "hello"]
    assert runez.readlines(bin / "pip3", logger=None) == ["#!/bin/sh", "hello"]
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
    cli.run("--dryrun", "build", "foo")
    assert cli.failed
    assert "Invalid python spec: ?foo" in cli.logged

    cli.run("--dryrun", "build", LATEST, "-mfoo")
    assert cli.failed
    assert "Unknown modules: foo" in cli.logged

    cli.run("--dryrun", "build", LATEST, "--build", "foo bar")
    assert cli.failed
    assert "Refusing path with space" in cli.logged

    cli.run("--dryrun", "build", "conda:1.0")
    assert cli.failed
    assert "Python family 'conda' is not yet supported" in cli.logged

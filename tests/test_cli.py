import os
import sys
from unittest.mock import patch

import runez

from portable_python.versions import PythonVersions

from .conftest import dummy_tarball


def test_module_invocation(cli):
    cli.exercise_main("-mportable_python", "src/portable_python/cli.py")


def test_build(cli):
    v = PythonVersions.cpython.latest
    mm = f"{v.major}.{v.minor}"
    cli.run("--dryrun", "build", "2.7.1", "-m+bdb", "--target=foo-bar")
    assert cli.failed
    assert " bdb:" in cli.logged
    assert "Compiling on platform 'foo' is not yet supported" in cli.logged

    bf = runez.to_path(f"build/cpython-{v}")
    cli.run("--dryrun", "build", v, "--target=darwin-x86_64", "-m+bdb,-openssl")
    assert cli.succeeded
    assert " openssl:" not in cli.logged
    assert " bdb:" in cli.logged
    assert f" --prefix=/{v} " in cli.logged
    assert f" install DESTDIR={bf}" in cli.logged

    cli.run("--dryrun", "build", v, "--target=darwin-x86_64", "-mnone", "--prefix", "/apps/python")
    assert cli.succeeded
    assert " --prefix=/apps/python " in cli.logged
    assert f" install DESTDIR={bf}/root" in cli.logged

    # Simulate presence of some key files to verify code that is detecting them is hit
    runez.touch(bf / "build/tcl/pkgs/sqlite", logger=None)
    deps_dir = bf / "deps"
    runez.touch(deps_dir / "bin/bzcat", logger=None)
    runez.touch(deps_dir / "include/readline/readline.h", logger=None)
    runez.touch(deps_dir / "lib/libssl.a", logger=None)
    os.chmod(deps_dir / "lib/libssl.a", 0o755)
    lib_static = f"libpython{mm}.a"
    lp = bf / f"{v}/lib"
    lpc = lp / f"python{mm}/config-{mm}-darwin"
    lib1 = lp / lib_static
    lib2 = lpc / lib_static
    runez.touch(bf / f"{v}/bin/python", logger=None)
    runez.touch(lib1, logger=None)
    runez.touch(lib2, logger=None)

    cli.run("--dryrun", "build", v, "--target=darwin-x86_64", "--static")
    assert cli.succeeded
    assert f"Would symlink {lib2} <- {lib1}" in cli.logged
    assert f"Corrected permissions for {deps_dir}/lib/libssl.a" in cli.logged

    cli.run("--dryrun", "build", v, "--target=darwin-x86_64", "-mall", "--no-static")
    assert cli.succeeded
    assert f"Cleaned 2 build artifacts: config-{mm}-darwin libpython{mm}.a" in cli.logged
    assert f"Would tar build/cpython-{v}/{v} -> dist/cpython-{v}-darwin-x86_64.tar.gz" in cli.logged

    cli.run("--dryrun", "build", v, "--target=linux-x86_64", "-mall", "--prefix", "/apps/foo{python_version}")
    assert cli.succeeded
    assert f" --prefix=/apps/foo{v} " in cli.logged

    cli.run("--dryrun", "list")
    assert cli.succeeded

    cli.run("--dryrun", "list", "conda", "cpython")
    assert cli.succeeded


def test_failed_run(cli):
    v = PythonVersions.cpython.latest
    dummy_tarball("zlib-1.2.11.tar.gz")
    build_path = runez.to_path(f"build/cpython-{v}")
    cli.run("build", v, "-mzlib")
    assert cli.failed
    assert "./configure is not an executable" in cli.logged
    assert os.path.exists(build_path / "logs/01-zlib.log")


def test_finalization(cli):
    v = PythonVersions.cpython.latest
    dummy_tarball(f"Python-{v}.tar.xz")
    dummy_tarball("bzip2-1.0.8.tar.gz")
    base = runez.to_path(f"build/cpython-{v}")
    bin = base / f"{v}/bin"

    runez.touch(base / "build/cpython/README", logger=None)  # Triggers compilation skip with --x-debug

    # Create some files to be groomed by CPython
    runez.touch(bin.parent / "lib/idle_test/foo", logger=None)
    runez.touch(bin.parent / "lib/__phello__.foo.py", logger=None)
    runez.touch(bin / "2to3", logger=None)
    runez.touch(bin / "foo-python", logger=None)
    runez.symlink(bin / "foo-python", bin / "python3", logger=None)  # Simulate a funky symlink, to test edge cases
    runez.write(bin / "some-exe", "#!.../bin/python3\nhello", logger=None)
    runez.write(bin / "some-exe3", "#!/bin/sh\nhello", logger=None)
    with patch("runez.run", return_value=runez.program.RunResult(code=0)):
        cli.run("build", v, "-mbzip2", "--x-debug")
        assert cli.failed
        assert "Modules selected: bzip2" in cli.logged
        assert "INFO Cleaned 2 build artifacts: __phello__.foo.py idle_test" in cli.logged
        assert f"Deleted build/cpython-{v}/{v}/bin/2to3" in cli.logged
        assert "Symlink foo-python <- python" in cli.logged
        assert f"Auto-corrected shebang for build/cpython-{v}/{v}/bin/some-exe" in cli.logged
        assert "Build failed" in cli.logged

    assert runez.readlines(bin / "some-exe", logger=None) == ["#!/bin/sh", '"exec" "$(dirname $0)/foo-python" "$0" "$@"', "hello"]
    assert runez.readlines(bin / "some-exe3", logger=None) == ["#!/bin/sh", "hello"]
    assert runez.basename(bin / "python", follow=True) == "foo-python"


def test_inspect(cli):
    cli.run("inspect", sys.executable, "-m+sys")
    assert cli.succeeded

    cli.run("inspect", sys.executable)
    assert ".so files:" in cli.logged

    cli.run("inspect", sys.executable, "foo", "-mall")
    assert cli.succeeded
    assert "readline" in cli.logged
    assert "foo: not available" in cli.logged


def test_invalid(cli):
    v = PythonVersions.cpython.latest
    cli.run("--dryrun", "build", "foo")
    assert cli.failed
    assert "Invalid python spec: ?foo" in cli.logged

    cli.run("--dryrun", "build", "3.6")
    assert cli.failed
    assert "Please provide full desired version" in cli.logged

    cli.run("--dryrun", "build", v, "-mfoo,bar")
    assert cli.failed
    assert "Unknown modules: foo, bar" in cli.logged

    cli.run("--dryrun", "build", v, "--build", "foo bar")
    assert cli.failed
    assert "Refusing path with space" in cli.logged

    cli.run("--dryrun", "build", "conda:1.2.3")
    assert cli.failed
    assert "Python family 'conda' is not yet supported" in cli.logged


def test_scan(cli):
    cli.run("scan", "--target", "darwin-x86_64")
    assert cli.succeeded

    with patch("portable_python.cpython.runez.which", return_value=None):
        cli.run("scan", "--target", "linux-x86_64")
        assert cli.succeeded
        assert "requires tclsh" in cli.logged

    with patch("portable_python.ModuleBuilder._find_telltale", return_value="foo"):
        cli.run("scan", "--target", "linux-x86_64")
        assert cli.succeeded
        assert "on top of libffi-dev" in cli.logged

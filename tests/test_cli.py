import os
import re
from unittest.mock import patch

import runez

from portable_python.versions import CPythonFamily, PythonVersions

from .conftest import dummy_tarball


def test_build_bogus_platform(cli, monkeypatch):
    monkeypatch.setenv("PP_TARGET", "foo-bar")
    cli.run("--dryrun", "build", "2.7.1", "-m+bdb")
    assert cli.failed
    assert "Modules selected: [+bdb] -> " in cli.logged
    assert " bdb:" in cli.logged
    assert "Compiling on platform 'foo' is not yet supported" in cli.logged


def test_build_cleanup(cli, monkeypatch):
    v = PythonVersions.cpython.latest
    mm = f"{v.major}.{v.minor}"
    bf = runez.to_path(f"build/cpython-{v}")

    # Simulate presence of some key files to verify code that is detecting them is hit
    runez.touch(bf / "build/tcl/pkgs/sqlite", logger=None)
    deps_dir = bf / "deps"
    runez.touch(deps_dir / "bin/bzcat", logger=None)
    runez.touch(deps_dir / "include/readline/readline.h", logger=None)
    runez.touch(deps_dir / "lib/libssl.a", logger=None)
    os.chmod(deps_dir / "lib/libssl.a", 0o755)
    runez.touch(bf / f"{v}/bin/python", logger=None)
    runez.touch(bf / f"{v}/lib/libpython{mm}.a", logger=None)
    runez.touch(bf / f"{v}/lib/python{mm}/config-{mm}-darwin/libpython{mm}.a", logger=None)

    monkeypatch.setenv("PP_TARGET", "macos-x86_64")
    cli.run("--dryrun", "build", v)
    assert cli.succeeded
    assert f"Corrected permissions for {deps_dir}/lib/libssl.a" in cli.logged
    assert f" install DESTDIR={bf}\n" in cli.logged

    cli.run("--dryrun", "build", v, "-mall", "--clean", "pip,libpython")
    assert cli.succeeded
    assert f"Cleaned 2 build artifacts: config-{mm}-darwin libpython{mm}.a" in cli.logged
    assert f"Would tar build/cpython-{v}/{v} -> dist/cpython-{v}-macos-x86_64.tar.gz" in cli.logged


def test_build_macos(cli, monkeypatch):
    monkeypatch.setenv("PP_TARGET", "macos-x86_64")
    cli.run("--dryrun", "build", "latest", "-m+bdb,-openssl")
    assert cli.succeeded
    assert " openssl:" not in cli.logged
    assert " bdb:" in cli.logged


def test_build_prefix(cli, monkeypatch):
    monkeypatch.setenv("PP_TARGET", "linux-x86_64")
    v = PythonVersions.cpython.latest
    cli.run("--dryrun", "build", "latest", "-mnone", "--prefix", "/apps/python")
    assert cli.succeeded
    assert "Modules selected: [none]\n" in cli.logged
    assert " --prefix=/apps/python " in cli.logged
    assert f" install DESTDIR=build/cpython-{v}/root\n" in cli.logged
    assert f"Would tar build/cpython-{v}/root/apps/python -> dist/cpython-{v}-linux-x86_64.tar.gz" in cli.logged

    cli.run("--dryrun", "build", "latest", "-mall", "--prefix", "/apps/foo{python_version}")
    assert cli.succeeded
    assert f" --prefix=/apps/foo{PythonVersions.cpython.latest} " in cli.logged


def test_diagnostics(cli):
    cli.run("-c", cli.tests_path("sample-config1.yml"), "diagnostics")
    assert cli.succeeded
    assert "tests/sample-config2.yml config:" in cli.logged


def test_failed_run(cli):
    v = PythonVersions.cpython.latest
    dummy_tarball("zlib-1.2.11.tar.gz")
    build_path = runez.to_path(f"build/cpython-{v}")
    cli.run("build", v, "-mzlib")
    assert cli.failed
    assert "./configure is not an executable" in cli.logged
    assert os.path.exists(build_path / "logs/01-zlib.log")


def test_finalization(cli, monkeypatch):
    cli.run("--dryrun", "build", "latest", "--clean", "foo")
    assert cli.failed
    assert "'foo' is not a valid value for --clean" in cli.logged

    v = PythonVersions.cpython.latest
    dummy_tarball(f"Python-{v}.tar.xz")
    dummy_tarball("bzip2-1.0.8.tar.gz")
    base = runez.to_path(f"build/cpython-{v}")
    bin = base / f"{v}/bin"

    runez.touch(base / "build/cpython/README", logger=None)

    # Create some files to be groomed by CPython
    runez.touch(bin.parent / "lib/idle_test/foo", logger=None)
    runez.touch(bin.parent / "lib/__phello__.foo.py", logger=None)
    runez.touch(bin / "2to3", logger=None)
    runez.touch(bin / "foo-python", logger=None)
    runez.symlink(bin / "foo-python", bin / "python3", logger=None)  # Simulate a funky symlink, to test edge cases
    runez.write(bin / "some-exe", "#!.../bin/python3\nhello", logger=None)
    runez.write(bin / "some-exe3", "#!/bin/sh\nhello", logger=None)
    runez.write(bin / "pythond", b"\xe4", logger=None)  # Non-unicode char to trigger edge case
    monkeypatch.setenv("PP_X_DEBUG", "direct-finalize")
    with patch("runez.run", return_value=runez.program.RunResult(code=0)):
        cli.run("build", v, "-mbzip2", "--clean", "bin,libpython")
        assert cli.failed
        assert "Modules selected: [bzip2] -> bzip2:" in cli.logged
        assert "INFO Cleaned 2 build artifacts: __phello__.foo.py idle_test" in cli.logged
        assert f"Deleted build/cpython-{v}/{v}/bin/2to3" in cli.logged
        assert "Symlink foo-python <- python" in cli.logged
        assert f"Auto-corrected shebang for build/cpython-{v}/{v}/bin/some-exe" in cli.logged
        assert "Build failed" in cli.logged

    assert list(runez.readlines(bin / "some-exe")) == ["#!/bin/sh", '"exec" "$(dirname $0)/foo-python" "$0" "$@"', "hello"]
    assert list(runez.readlines(bin / "some-exe3")) == ["#!/bin/sh", "hello"]
    assert runez.basename(bin / "python", follow=True) == "foo-python"


def test_inspect(cli):
    cli.run("--dryrun", "inspect", "foo", "bar", "-m+sys")
    assert cli.succeeded

    cli.run("--dryrun", "inspect", "foo", "--validate")
    assert cli.failed  # Fails with --validate
    assert "foo: not an executable" in cli.logged


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

    cli.run("--dryrun", "build", "conda:1.2.3")
    assert cli.failed
    assert "Python family 'conda' is not yet supported" in cli.logged


def test_invoker(cli):
    cli.run("inspect", "invoker", "-vv", "-mall")
    assert cli.succeeded

    # Invoker may not be completely clean, but it has to have at least one OK .so usage
    m = re.search(r"^\.so files: .+(\d+) OK", cli.logged.stdout.contents(), re.MULTILINE)
    assert m
    reported = int(m.group(1))
    assert reported > 0


# GH_CPYTHON_SAMPLE = """
# [{"ref": "refs/tags/v3.9.7"},{"ref": "refs/tags/v3.8.12"}]
# """
PYTHON_ORG_SAMPLE = """
<a href="3.9.5/">3.9.5/</a>
<a href="3.9.6/">3.9.6/</a>
<a href="3.9.7/">3.9.7/</a>
<a href="3.8.12/">3.9.12/</a>
"""


@CPythonFamily.client.mock({
    "https://www.python.org/ftp/python/": PYTHON_ORG_SAMPLE,
    # "https://api.github.com/repos/python/cpython/git/matching-refs/tags/v3.": GH_CPYTHON_SAMPLE,
})
def test_list(cli, monkeypatch):
    monkeypatch.setattr(CPythonFamily, "_test_latest", None)
    cp = CPythonFamily()
    assert str(cp.latest) == "3.9.7"  # Exercise cached property 'latest', which is otherwise mocked for tests/dryrun

    cli.run("list")
    assert cli.succeeded

    cli.run("list", "--json")
    assert cli.succeeded
    assert cli.logged.stdout.contents().startswith("{")

    cli.run("list", "conda")
    assert cli.failed
    assert "Python family 'conda' is not yet supported" in cli.logged


def test_module_invocation(cli):
    cli.exercise_main("src/portable_python/external/_inspect.py")
    cli.exercise_main("-mportable_python", "src/portable_python/cli.py")


def test_recompress(cli):
    cli.run("--dryrun", "recompress", "foo", "gz")
    assert cli.failed
    assert "'foo' does not exist" in cli.logged

    runez.touch("build/cpython-3.9.7/3.9.7/bin/python", logger=None)
    cli.run("recompress", "3.9.7", "gz")
    assert cli.succeeded
    assert "Tar build/cpython-3.9.7/3.9.7 -> dist/cpython-3.9.7-" in cli.logged
    files = list(runez.ls_dir("dist"))
    assert len(files) == 1  # Actual name depends on current platform

    cli.run("--dryrun", "recompress", files[0], "gz")
    assert cli.succeeded
    assert "-recompressed.tar.gz" in cli.logged

    cli.run("recompress", files[0], "bz2")
    assert cli.succeeded
    assert "Tar tmp -> cpython-3.9.7-" in cli.logged
    files = list(runez.ls_dir("dist"))
    assert len(files) == 2


def test_scan(cli, monkeypatch):
    monkeypatch.setenv("PP_TARGET", "macos-x86_64")
    cli.run("scan")
    assert cli.succeeded

    monkeypatch.setenv("PP_TARGET", "linux-x86_64")
    with patch("portable_python.cpython.runez.which", return_value=None):
        cli.run("scan")
        assert cli.succeeded
        assert "!needs tclsh" in cli.logged

        cli.run("scan", "--validate")
        assert cli.failed
        assert "!needs tclsh" in cli.logged

    with patch("portable_python.ModuleBuilder._find_telltale", return_value="foo"):
        cli.run("scan")
        assert cli.succeeded
        assert "on top of libffi-dev" in cli.logged

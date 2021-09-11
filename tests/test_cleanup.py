import os

import runez


def test_cleanup(cli):
    v = "3.9.7"
    mm = v[:3]
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

    cli.run("-ntmacos-x86_64", "-c", cli.tests_path("sample-config-github.yml"), "build", "-mopenssl,tkinter", v)
    assert cli.succeeded
    assert f"Corrected permissions for {deps_dir}/lib/libssl.a" in cli.logged
    assert f" install DESTDIR={bf}\n" in cli.logged

    cli.run("-ntlinux-x86_64", "build", v, "-mall", "--clean", "pip,libpython")
    assert cli.succeeded
    assert "selected: all" in cli.logged
    assert f"Cleaned 2 build artifacts: config-{mm}-darwin libpython{mm}.a" in cli.logged
    assert f"Would tar build/cpython-{v}/{v} -> dist/cpython-{v}-linux-x86_64.tar.gz" in cli.logged

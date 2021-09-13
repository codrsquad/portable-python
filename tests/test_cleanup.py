import os

import runez


def test_cleanup(cli):
    v = "3.9.7"
    mm = v[:3]
    bf = runez.to_path(f"build/cpython-{v}/pp-install-folder-marker")
    lib = bf / f"{v}/lib"

    # Simulate presence of some key files to verify code that is detecting them is hit
    runez.touch(bf / "build/tcl/pkgs/sqlite", logger=None)
    deps_dir = bf.parent / "deps"
    runez.touch(deps_dir / "bin/bzcat", logger=None)
    runez.touch(deps_dir / "include/readline/readline.h", logger=None)
    runez.touch(deps_dir / "lib/libssl.a", logger=None)
    os.chmod(deps_dir / "lib/libssl.a", 0o755)
    runez.touch(bf / f"{v}/bin/python", logger=None)
    runez.touch(bf / f"{v}/bin/easy_install", logger=None)
    runez.touch(lib / "idle_test/foo", logger=None)
    sample_content = "dummy content for libpython.a\n" * 1000
    runez.write(lib / f"libpython{mm}.a", sample_content, logger=None)
    runez.write(lib / f"python{mm}/config-{mm}-darwin/libpython{mm}.a", sample_content, logger=None)

    cfg = cli.tests_path("sample-config1.yml")
    cli.run("-ntmacos-x86_64", f"-c{cfg}", "build", "-mopenssl,readline", v)
    assert cli.succeeded
    assert "Cleaned 1 build artifact (0 B): idle_test" in cli.logged
    assert f"Cleaned 2 build artifacts (59 KB): config-{mm}-darwin libpython{mm}.a" in cli.logged
    assert f"Corrected permissions for {deps_dir}/lib/libssl.a" in cli.logged
    assert f" install DESTDIR={bf.parent}\n" in cli.logged

    cli.run("-ntlinux-x86_64", f"-c{cfg}", "build", v, "-mall")
    assert cli.succeeded
    assert "Cleaned 1 build artifact (0 B): easy_install" in cli.logged
    assert "selected: all" in cli.logged
    assert f"Would symlink {lib}/python{mm}/config-{mm}-darwin/libpython{mm}.a <- {lib}/libpython{mm}.a"
    assert f"Would tar {bf}/{v} -> dist/cpython-{v}-linux-x86_64.tar.gz" in cli.logged

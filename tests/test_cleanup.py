import os

import runez

from .conftest import typical_build_folder, typical_install_folder


def test_cleanup(cli):
    v = "3.9.7"
    mm = v[:3]
    build_dir = typical_build_folder(v)
    install_dir = typical_install_folder(v)
    lib = install_dir / "lib"

    # Simulate presence of some key files to verify code that is detecting them is hit
    runez.touch(install_dir / "build/tcl/pkgs/sqlite", logger=None)
    runez.touch(build_dir / "deps/bin/bzcat", logger=None)
    runez.touch(build_dir / "deps/include/readline/readline.h", logger=None)
    runez.touch(build_dir / "deps/lib/libssl.a", logger=None)
    os.chmod(build_dir / "deps/lib/libssl.a", 0o755)
    runez.touch(install_dir / "bin/python", logger=None)
    runez.touch(install_dir / "bin/easy_install", logger=None)
    runez.touch(lib / "idle_test/foo", logger=None)
    sample_content = "dummy content for libpython.a\n" * 1000
    runez.write(lib / f"libpython{mm}.a", sample_content, logger=None)
    runez.write(lib / f"python{mm}/config-{mm}-darwin/libpython{mm}.a", sample_content, logger=None)

    cfg = cli.tests_path("sample-config1.yml")
    cli.run("-ntmacos-x86_64", f"-c{cfg}", "build", "-mopenssl,readline", v)
    assert cli.succeeded
    assert "Cleaned 1 build artifact (0 B): idle_test" in cli.logged
    assert f"Cleaned 2 build artifacts (59 KB): config-{mm}-darwin libpython{mm}.a" in cli.logged
    assert f"Corrected permissions for {build_dir}/deps/lib/libssl.a" in cli.logged
    assert f" install DESTDIR={build_dir}\n" in cli.logged

    cli.run("-ntlinux-x86_64", f"-c{cfg}", "build", v, "-mall")
    assert cli.succeeded
    assert "Cleaned 1 build artifact (0 B): easy_install" in cli.logged
    assert "selected: all" in cli.logged
    assert f"Would symlink {lib}/python{mm}/config-{mm}-darwin/libpython{mm}.a <- {lib}/libpython{mm}.a"
    assert f"Would tar {install_dir} -> dist/cpython-{v}-linux-x86_64.tar.gz" in cli.logged

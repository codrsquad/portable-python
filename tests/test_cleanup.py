import os

import runez

from portable_python import BuildContext
from portable_python.versions import PPG


def test_cleanup(cli, monkeypatch):
    f = PPG.get_folders(version="3.7.12")
    install_dir = f.resolved_destdir()
    lib = install_dir / "lib"

    # Simulate presence of some key files to verify code that is detecting them is hit
    runez.write(f.components / "cpython/Mac/Makefile.in", "hmm\nmentions /usr/local\n", logger=None)
    runez.write(f.components / "cpython/Lib/trace.py", "hmm\nmentions /usr/local", logger=None)  # ignored because in Lib/ folder
    runez.write(f.components / "cpython/setup.py", "path.startswith('/usr/') and not path.startswith('/usr/local')", logger=None)
    runez.write(f.components / "cpython/foo", b"hello\xe4 /usr/local", logger=None)
    runez.touch(f.deps / "bin/bzcat", logger=None)
    runez.touch(f.deps / "include/readline/readline.h", logger=None)
    runez.touch(f.deps / "lib/libssl.a", logger=None)
    os.chmod(f.deps / "lib/libssl.a", 0o755)
    runez.touch(install_dir / "bin/python", logger=None)
    runez.touch(install_dir / "bin/easy_install", logger=None)
    runez.touch(install_dir / f"bin/pip{f.mm}", logger=None)
    runez.touch(lib / "idle_test/foo", logger=None)
    sample_content = "dummy content for libpython.a\n" * 1000
    runez.write(lib / f"libpython{f.mm}.a", sample_content, logger=None)
    runez.write(lib / f"python{f.mm}/config-{f.mm}-darwin/libpython{f.mm}.a", sample_content, logger=None)
    runez.touch(lib / f"python{f.mm}/site-packages/setuptools", logger=None)

    cfg = cli.tests_path("sample-config1.yml")
    cli.run("-ntmacos-x86_64", f"-c{cfg}", "build", "-mopenssl,readline", f.version)
    assert cli.succeeded
    assert "Patched '/usr/local\\b' in build/components/cpython/Mac/Makefile.in" in cli.logged
    assert "MACOSX_DEPLOYMENT_TARGET=10.25" in cli.logged
    assert "Pass 1: Cleaned" in cli.logged
    assert "Pass 2: Cleaned" in cli.logged
    assert "PEP 668: Cleaned" in cli.logged
    assert f"Corrected permissions for {f.deps}/lib/libssl.a" in cli.logged
    assert f" install DESTDIR={f.build_folder}\n" in cli.logged
    cli.match("Patched 'startswith(...)' in build/components/cpython/setup.py")
    assert "Exercising configured validation script" in cli.logged
    assert "Lib/trace.py" not in cli.logged

    cli.run("-ntlinux-x86_64", f"-c{cfg}", "build", f.version, "-mall")
    assert cli.succeeded
    assert "MACOSX_DEPLOYMENT_TARGET" not in cli.logged
    assert "selected: all" in cli.logged
    assert f"Would symlink {install_dir}/bin/pip{f.mm} <- {install_dir}/bin/pip" in cli.logged
    assert f"Would symlink {lib}/python{f.mm}/config-{f.mm}-darwin/libpython{f.mm}.a <- {lib}/libpython{f.mm}.a" in cli.logged
    assert f"Would tar {install_dir} -> dist/cpython-{f.version}-linux-x86_64.tar.gz" in cli.logged

    runez.touch("bin/brew", logger=None)
    runez.touch("include/dbm.h", logger=None)
    monkeypatch.setattr(BuildContext, "usr_local", os.getcwd())
    cli.run("-ntmacos-arm64", f"-c{cfg}", "build", f.version)
    assert cli.succeeded
    assert "Patched '/usr/local\\b' in build/components/cpython/setup.py" in cli.logged
    assert "Can't patch 'build/components/cpython/foo'" in cli.logged
    assert "isolate-usr-local: mount-shadow" in cli.logged

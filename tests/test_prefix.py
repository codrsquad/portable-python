def test_prefix_linux(cli):
    cli.run("-ntlinux-x86_64", "build", "3.9.7", "-mnone", "--prefix", "/apps/python")
    assert cli.succeeded
    assert "selected: none" in cli.logged
    assert " --prefix=/apps/python " in cli.logged
    assert " install DESTDIR=build/cpython-3.9.7/root\n" in cli.logged
    assert "Would tar build/cpython-3.9.7/root/apps/python -> dist/apps-python-linux-x86_64.tar.gz" in cli.logged


def test_prefix_macos(cli):
    cli.run("-ntmacos-arm64", "build", "3.10.1", "-mnone", "--prefix", "/opt/foo{python_version}")
    assert cli.succeeded
    assert " --prefix=/opt/foo3.10.1 " in cli.logged
    assert "Would tar build/cpython-3.10.1/root/opt/foo3.10.1 -> dist/opt-foo3.10.1-macos-arm64.tar.gz" in cli.logged

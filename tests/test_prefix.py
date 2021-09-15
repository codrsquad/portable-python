def test_prefix_linux(cli):
    v = "3.9.7"
    cli.run("-ntlinux-x86_64", "build", v, "-mnone", "--prefix", "/apps/python{version}")
    assert cli.succeeded
    assert "selected: none" in cli.logged
    assert f" --prefix=/apps/python{v} " in cli.logged
    assert " install DESTDIR=build\n" in cli.logged
    assert f"Would tar build/apps/python{v} -> dist/apps-python{v}-linux-x86_64.tar.gz" in cli.logged


def test_prefix_macos(cli):
    v = "3.10.1"
    cli.run("-ntmacos-arm64", "build", v, "-mnone", "--prefix", "/opt/foo{version}")
    assert cli.succeeded
    assert f" --prefix=/opt/foo{v} " in cli.logged
    assert f"Would tar build/opt/foo{v} -> dist/opt-foo{v}-macos-arm64.tar.gz" in cli.logged

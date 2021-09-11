def test_build_prefix(cli):
    v = "3.9.7"
    cli.run("-ntlinux-x86_64", "build", v, "-mnone", "--prefix", "/apps/python")
    assert cli.succeeded
    assert "selected: none" in cli.logged
    assert " --prefix=/apps/python " in cli.logged
    assert f" install DESTDIR=build/cpython-{v}/root\n" in cli.logged
    assert f"Would tar build/cpython-{v}/root/apps/python -> dist/cpython-{v}-linux-x86_64.tar.gz" in cli.logged

    cli.run("-n", "build", v, "-mnone", "--prefix", "/apps/foo{python_version}")
    assert cli.succeeded
    assert f" --prefix=/apps/foo{v} " in cli.logged

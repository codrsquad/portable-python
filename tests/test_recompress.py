import runez


def test_recompress(cli):
    cli.run("-n", "recompress", "foo", "gz")
    assert cli.failed
    assert "'foo' does not exist" in cli.logged

    runez.touch("build/3.9.7/bin/python", logger=None)
    cli.run("recompress", "3.9.7", "gz")
    assert cli.succeeded
    assert "Tar build/3.9.7 -> dist/cpython-3.9.7-" in cli.logged
    files = list(runez.ls_dir("dist"))
    assert len(files) == 1  # Actual name depends on current platform

    cli.run("-n", "recompress", files[0], "gz")
    assert cli.succeeded
    assert "-recompressed.tar.gz" in cli.logged

    cli.run("recompress", files[0], "bz2")
    assert cli.succeeded
    assert "Tar tmp -> cpython-3.9.7-" in cli.logged
    files = list(runez.ls_dir("dist"))
    assert len(files) == 2

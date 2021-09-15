import runez

from portable_python.versions import PPG

from .conftest import dummy_tarball


def test_build_bogus_platform(cli):
    cli.run("-ntfoo-bar", "build", "2.7.1")
    assert cli.failed
    assert "Compiling on platform 'foo' is not yet supported" in cli.logged


def test_failed_run(cli, monkeypatch):
    folders = PPG.get_folders(version="3.9.7")
    dummy_tarball(folders, "zlib-1.2.11.tar.gz")
    monkeypatch.setenv("PP_X_DEBUG", "continue")
    cli.run("-c", runez.DEV.tests_path("sample-config2.yml"), "build", folders.version, "-mzlib")
    assert cli.failed
    assert "./configure is not an executable" in cli.logged
    assert (folders.build_folder / "logs/01-zlib.log").exists()


def test_invalid(cli):
    cli.run("-n", "build", "foo")
    assert cli.failed
    assert "Invalid python spec: ?foo" in cli.logged

    cli.run("-n", "build", "3.6")
    assert cli.failed
    assert "Please provide full desired version" in cli.logged

    cli.run("-n", "build", "3.6.7", "-mfoo,bar")
    assert cli.failed
    assert "Unknown modules: foo, bar" in cli.logged

    cli.run("-n", "build", "conda:1.2.3")
    assert cli.failed
    assert "Python family 'conda' is not yet supported" in cli.logged

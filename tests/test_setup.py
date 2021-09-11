def test_config(cli):
    cli.run("-ntmacos-arm64", "-c", cli.tests_path("sample-config1.yml"), "build", "3.9.7", "-mnone")
    assert cli.succeeded
    assert "env MACOSX_DEPLOYMENT_TARGET=11" in cli.logged  # Comes from more specific macos-arm64.yml
    assert " -> dist/cpython-3.9.7-macos-arm64.tar.xz" in cli.logged  # Comes from macos.yml (not defined in macos-arm64.yml)
    assert "Would run: build/cpython-3.9.7/3.9.7/bin/python -mpip install -U wheel" in cli.logged
    assert "--enable-optimizations" in cli.logged  # From default config

    cli.run("-ntlinux-x86_64", "-c", cli.tests_path("sample-config1.yml"), "build", "3.9.7", "-mnone")
    assert cli.succeeded
    assert "env MACOSX_DEPLOYMENT_TARGET" not in cli.logged
    assert " -> dist/cpython-3.9.7-linux-x86_64.tar.gz" in cli.logged  # Default .tar.gz
    assert "pip install -U wheel" not in cli.logged  # No pip-install section for linux
    assert "--enable-optimizations" in cli.logged  # From default config


def test_diagnostics(cli):
    cli.run("-c", cli.tests_path("sample-config1.yml"), "diagnostics")
    assert cli.succeeded
    assert "tests/sample-config2.yml config:" in cli.logged


def test_inspect(cli):
    cli.run("-n", "inspect", "foo", "bar", "-m+sys")
    assert cli.failed
    assert "foo: not an executable" in cli.logged

    cli.run("-n", "inspect", "foo")
    assert cli.failed

from portable_python import BuildSetup, ModuleBuilder
from portable_python.versions import PythonVersions


def test_config(cli, monkeypatch):
    monkeypatch.setenv("PP_TARGET", "macos-arm64")
    cli.run("--dryrun", "-c", cli.tests_path("sample-config1.yml"), "build", "3.9.7", "-mnone")
    assert cli.succeeded
    assert "env MACOSX_DEPLOYMENT_TARGET=11" in cli.logged  # Comes from more specific macos-arm64.yml
    assert " -> dist/cpython-3.9.7-macos-arm64.tar.xz" in cli.logged  # Comes from macos.yml (not defined in macos-arm64.yml)
    assert "Would run: build/cpython-3.9.7/3.9.7/bin/python -mpip install -U wheel" in cli.logged
    assert "--enable-optimizations" in cli.logged  # From default config

    monkeypatch.setenv("PP_TARGET", "linux-x86_64")
    cli.run("--dryrun", "-c", cli.tests_path("sample-config1.yml"), "build", "3.9.7", "-mnone")
    assert cli.succeeded
    assert "env MACOSX_DEPLOYMENT_TARGET" not in cli.logged
    assert " -> dist/cpython-3.9.7-linux-x86_64.tar.gz" in cli.logged  # Default .tar.gz
    assert "pip install -U wheel" not in cli.logged  # No pip-install section for linux
    assert "--enable-optimizations" in cli.logged  # From default config


def test_edge_cases(temp_folder, monkeypatch):
    monkeypatch.setenv("PP_TARGET", "linux-x86_64")
    assert str(PythonVersions.cpython)

    setup = BuildSetup()
    assert "build/cpython-" in str(setup)
    assert ", 1 config source" in str(setup.config)
    assert setup.python_spec.version == PythonVersions.cpython.latest
    assert str(setup.python_builder.modules) == "selected: None (0 modules)"

    mb = ModuleBuilder(setup)
    assert not mb.url
    assert not mb.version

from portable_python import BuildSetup, ModuleBuilder
from portable_python.versions import PythonVersions


def test_config(cli, monkeypatch):
    monkeypatch.setenv("PP_TARGET", "macos-arm64")
    cli.run("--dryrun", "-c", cli.tests_path("sample-config1.yml"), "build", "3.9.7", "-mnone")
    assert cli.succeeded
    assert "env MACOSX_DEPLOYMENT_TARGET=11" in cli.logged  # Comes from more specific macos-arm64.yml
    assert " -> dist/cpython-3.9.7-macos-arm64.zip" in cli.logged  # Comes from macos.yml (not defined in macos-arm64.yml)
    assert "Would run: build/cpython-3.9.7/3.9.7/bin/python -mpip install -U wheel" in cli.logged
    assert "--enable-optimizations" in cli.logged  # From default config


def test_edge_cases(monkeypatch):
    monkeypatch.setenv("PP_TARGET", "linux-x86_64")
    assert str(PythonVersions.cpython)

    setup = BuildSetup(modules="+readline")
    assert str(setup)
    assert str(setup.config)
    assert setup.python_spec.version == PythonVersions.cpython.latest
    assert str(setup.python_builder.modules) == "+readline"

    setup = BuildSetup()
    assert str(setup.python_builder.modules).startswith("auto-detected:")

    mb = ModuleBuilder(setup)
    assert not mb.url
    assert not mb.version
    assert str(mb.modules) == "no sub-modules"

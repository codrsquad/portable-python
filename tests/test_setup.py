from portable_python import BuildSetup, ModuleBuilder
from portable_python.versions import PythonVersions


def test_config(cli, monkeypatch):
    monkeypatch.setenv("PP_TARGET", "macos-arm64")
    monkeypatch.setenv("PP_BASE", cli.tests_path("config"))
    cli.run("--dryrun", "build", "3.9.7")
    assert cli.succeeded
    assert "env MACOSX_DEPLOYMENT_TARGET=11" in cli.logged  # Comes from more specific macos-arm64.yml
    assert " -> dist/cpython-3.9.7-macos-arm64.zip" in cli.logged  # Comes from macos.yml (not defined in macos-arm64.yml)


def test_edge_cases(monkeypatch):
    monkeypatch.setenv("PP_TARGET", "linux-x86_64")
    setup = BuildSetup(None, modules="+readline")
    assert str(setup.ppb)
    assert str(setup.ppb.config)
    assert setup.python_spec.version == PythonVersions.cpython.latest
    assert str(setup.python_builder.modules) == "+readline"

    setup = BuildSetup(None)
    assert str(setup)
    assert str(PythonVersions.cpython)
    assert str(setup.python_builder.modules).startswith("auto-detected:")

    mb = ModuleBuilder(setup)
    assert not mb.url
    assert not mb.version
    assert str(mb.modules) == "no sub-modules"

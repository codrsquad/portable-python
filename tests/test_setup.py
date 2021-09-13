import pytest
import runez

from portable_python import BuildSetup, ModuleBuilder
from portable_python.versions import PPG


def test_config(cli):
    cli.run("-ntmacos-arm64", "-c", cli.tests_path("sample-config1.yml"), "build", "3.9.7", "-mnone")
    assert cli.succeeded
    assert "env MACOSX_DEPLOYMENT_TARGET=12" in cli.logged  # Comes from more specific macos-arm64.yml
    assert " -> dist/cpython-3.9.7-macos-arm64.tar.xz" in cli.logged  # Comes from macos.yml (not defined in macos-arm64.yml)
    cli.match("Would run: build/cpython-.../bin/python -mpip install -U wheel")
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


def test_edge_cases(temp_folder, monkeypatch, logged):
    monkeypatch.setattr(PPG, "config", None)
    runez.write("pp.yml", "", logger=None)
    PPG.grab_config(path="pp.yml", base_folder=temp_folder, target="linux-x86_64")
    assert str(PPG.cpython) == "cpython"
    assert str(PPG.config) == "pp.yml, 2 config sources [linux-x86_64]"

    setup = BuildSetup("3.9.6")
    assert str(setup) == "build/cpython-3.9.6"

    mb = ModuleBuilder(setup)
    assert not mb.url
    assert not mb.version
    mb.resolved_telltale = "foo.h"
    mb.m_debian = "-foo"
    outcome, reason = mb.linker_outcome(is_selected=True)
    assert outcome.name == "failed"
    assert reason == "broken, can't compile statically with foo present"

    PPG.config.sources[0].data = dict(ext="foo")
    assert not logged
    with pytest.raises(BaseException):
        _ = BuildSetup("3.9.6")
    assert "Invalid extension 'foo'" in logged.pop()


def test_inspect(cli):
    cli.run("-n", "inspect", "foo", "bar", "-m+sys")
    assert cli.failed
    assert "foo: not an executable" in cli.logged

    cli.run("-n", "inspect", "foo")
    assert cli.failed

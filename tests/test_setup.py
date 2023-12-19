import pytest
import runez

from portable_python import BuildSetup, ModuleBuilder
from portable_python.versions import PPG


def test_config(cli):
    with pytest.raises(runez.system.AbortException):
        PPG.config.parsed_yaml("a: b\ninvalid line", "testing")

    cli.run("-ntmacos-arm64", "-c", cli.tests_path("sample-config1.yml"), "build", "3.9.7", "-mnone")
    assert cli.succeeded
    assert " -mpip install my-additional-package" in cli.logged
    assert "env MACOSX_DEPLOYMENT_TARGET=12" in cli.logged  # Comes from more specific macos-arm64.yml
    assert " -> dist/cpython-3.9.7-macos-arm64.tar.xz" in cli.logged  # Comes from macos.yml (not defined in macos-arm64.yml)
    cli.match("Would run: build/cpython-.../bin/python -mpip install -U wheel")
    assert "--enable-shared" in cli.logged  # From custom config
    assert "--with-system-ffi" in cli.logged  # Because libffi was not compiled

    cli.run("-ntlinux-x86_64", "-c", cli.tests_path("sample-config1.yml"), "build", "3.9.7", "-mnone")
    assert cli.succeeded
    assert "env MACOSX_DEPLOYMENT_TARGET" not in cli.logged
    assert " -> dist/cpython-3.9.7-linux-x86_64.tar.gz" in cli.logged  # Default .tar.gz


def test_diagnostics(cli):
    runez.write("pp-dev.yml", "a: b", logger=None)
    runez.write("portable-python.yml", "include: +pp-dev.yml", logger=None)
    cli.run("diagnostics")
    assert cli.succeeded
    assert "pp-dev.yml:\na: b\n\nportable-python.yml:\ninclude: +pp-dev.yml" in cli.logged.stdout


def test_edge_cases(temp_folder, monkeypatch, logged):
    monkeypatch.setattr(PPG, "config", None)
    PPG.grab_config(runez.DEV.tests_path("sample-incomplete.yml"))
    with pytest.raises(runez.system.AbortException):
        PPG.get_folders()
    assert "Folder 'destdir' must be configured" in logged.pop()

    runez.write("pp.yml", "folders:\n build: build/{family}-{version}", logger=None)
    PPG.grab_config("pp.yml", target="linux-x86_64")
    assert str(PPG.cpython) == "cpython"
    assert str(PPG.config) == "1 config source [linux-x86_64]"

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

    sources = getattr(PPG.config, "_sources", None)
    monkeypatch.setattr(sources[0], "data", {"ext": "foo"})
    assert not logged
    with pytest.raises(runez.system.AbortException):
        _ = BuildSetup("3.9.6")
    assert "Invalid extension 'foo'" in logged.pop()


def test_inspect(cli):
    cli.run("-n", "inspect", "foo", "-m+sys")
    assert cli.failed
    assert "Would run: foo" in cli.logged
    assert "foo: " in cli.logged

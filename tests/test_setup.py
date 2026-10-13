from pathlib import Path

import pytest
import runez

from portable_python import BuildSetup, correct_permissions, ModuleBuilder, patch_file, required_python_spec
from portable_python.versions import PPG


def test_config(cli):
    with pytest.raises(runez.system.AbortException):
        PPG.config.parsed_yaml("a: b\ninvalid line", "testing")

    # Exercise custom url in config
    cli.run("-ntmacos-arm64", "-c", cli.tests_path("sample-config1.yml"), "build", "3.9.7", "-mbzip2")
    assert cli.succeeded
    assert "Would download https://my-enterprise/.../assets/bzip2/123#sha256=123...def\n" in cli.logged
    assert "Would untar build/sources/bzip2-1.2.3.tar.gz -> build/components/bzip2\n" in cli.logged

    cli.run("-ntmacos-arm64", "-c", cli.tests_path("sample-config1.yml"), "build", "3.9.7", "-mnone")
    assert cli.succeeded

    assert " -mpip install --no-cache-dir --upgrade my-additional-package" in cli.logged
    assert "env MACOSX_DEPLOYMENT_TARGET=12" in cli.logged  # Comes from more specific macos-arm64.yml
    assert " -> dist/cpython-3.9.7-macos-arm64.tar.xz" in cli.logged  # Comes from macos.yml (not defined in macos-arm64.yml)
    cli.match("Would run: build/cpython-.../bin/python -mpip install -U wheel")
    assert "--enable-shared" in cli.logged  # From custom config
    assert "--with-system-ffi" in cli.logged  # Because libffi was not compiled

    cli.run("-ntlinux-x86_64", "-c", cli.tests_path("sample-config1.yml"), "build", "3.9.7", "-mnone")
    assert cli.succeeded
    assert "env MACOSX_DEPLOYMENT_TARGET" not in cli.logged
    assert " -> dist/cpython-3.9.7-linux-x86_64.tar.gz" in cli.logged  # Default .tar.gz


def test_module_overrides(cli, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://my-proxy:8080")  # Exercise proxy pass-through on downloads
    monkeypatch.setenv("HTTPS_PROXY", "http://my-proxy:8443")
    modules = "bdb gdbm libffi mpdec ncurses openssl readline sqlite uuid xz zlib".split()
    config = [f"{m}-configure: --my-{m}-opt --my-{m}-libs=$lib_dir:$lib64_dir" for m in modules]
    config.append("cpython-url: https://my-mirror/python-$version.tar.xz")
    config.append("openssl-version: 1.1.1w")  # Older versions have a different download url scheme
    config.append("openssl-patches:\n  - file: README\n    regex: foo\n    replacement: bar")
    config.append("  - file: no-such-file\n    regex: foo\n    replacement: bar")
    runez.write("pp.yml", "\n".join(config), logger=None)
    runez.write("README", "Hello foo", logger=None)  # Dryrun doesn't extract sources, so the build stays in this folder
    cli.run("-n", "-tlinux-x86_64", "-c", "pp.yml", "build", "3.14.4", "-mall")
    assert cli.succeeded
    for m in modules:
        assert f" --my-{m}-opt --my-{m}-libs=build/deps/lib:build/deps/lib64" in cli.logged  # Separate args (not quoted together)

    assert "Would apply patch: foo -> bar in README" in cli.logged
    assert "no-such-file" not in cli.logged  # Not reported in dryrun mode (sources to patch are not downloaded)
    assert "Would download https://my-mirror/python-3.14.4.tar.xz" in cli.logged
    assert "Would download https://github.com/openssl/openssl/releases/download/OpenSSL_1_1_1w/openssl-1.1.1w.tar.gz" in cli.logged


def test_diagnostics(cli):
    runez.write("pp-dev.yml", "a: b", logger=None)
    runez.write("portable-python.yml", "include: +pp-dev.yml", logger=None)
    cli.run("diagnostics")
    assert cli.succeeded
    assert "pp-dev.yml:\na: b\n\nportable-python.yml:\ninclude: +pp-dev.yml" in cli.logged.stdout


def test_folder_with_space(cli):
    runez.write("pp.yml", "folders:\n  build: my build", logger=None)
    cli.run("-n", "-c", "pp.yml", "build", "3.9.7")
    assert cli.failed
    assert "Refusing path with space (escapes too complex with makefiles, shell scripts etc): 'my build'" in cli.logged


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

    setup = BuildSetup(required_python_spec("3.9.6"))
    assert str(setup) == "build/cpython-3.9.6"

    mb = ModuleBuilder(setup)
    assert not mb.url
    assert not mb.version
    mb.resolved_telltale = "foo.h"
    mb.m_debian = "-foo"
    outcome, reason = mb.linker_outcome(is_selected=True)
    assert outcome.name == "failed"
    assert reason == "broken, can't compile statically with foo present"

    patch_file("no-such-file", "foo", "bar")  # Not in dryrun mode: a (configured) patch on a missing file is reported
    assert "Can't patch no-such-file: file not found" in logged.pop()

    lib = Path("libfoo.a")
    runez.touch(lib, logger=None)
    lib.chmod(0o755)
    correct_permissions(lib, 0o644)  # Not in dryrun mode: permissions are effectively corrected
    assert "Corrected permissions for libfoo.a to 0o644 (was 0o755)" in logged.pop()
    assert lib.stat().st_mode & 0o777 == 0o644

    runez.write("pp.yml", "ext: foo", logger=None)
    PPG.grab_config("pp.yml", target="linux-x86_64")
    assert not logged
    with pytest.raises(runez.system.AbortException):
        _ = BuildSetup(required_python_spec("3.9.6"))
    assert "Invalid extension 'foo'" in logged.pop()


def test_missing_bin_python(temp_folder, logged):
    PPG.grab_config(target="linux-x86_64")
    setup = BuildSetup(required_python_spec("3.9.6"))
    with pytest.raises(runez.system.AbortException):
        _ = setup.python_builder.bin_python
    assert "Can't find bin/python in /" in logged
    assert "/build/ppp-marker/3.9.6/bin\n" in logged.pop()


def test_inspect(cli):
    cli.run("-n", "inspect", "foo", "-m+sys")
    assert cli.failed
    assert "Would run: foo" in cli.logged
    assert "foo: " in cli.logged

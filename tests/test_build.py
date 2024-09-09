from unittest.mock import patch

import runez

from portable_python.versions import PPG

from .conftest import dummy_tarball


def test_build_rc(cli):
    f = PPG.get_folders(version="3.10.0rc2")
    install_dir = f.resolved_destdir()
    cli.run("-n", "-tmacos-arm64", "build", f.version, "-mnone")
    assert cli.succeeded
    assert f"Would tar {install_dir} -> dist/cpython-{f.version}-macos-arm64.tar.gz" in cli.logged


SAMPLE_SYS_CONF = """
# sys config
build_time_vars = {'a': '',
 'b': '/ppp-marker/3.9.7/bin',
 'c': '/ppp-marker/3.9.7 /ppp-marker/3.9.7/lib '
}
"""

SAMPLE_SYS_CONF_REL = """
# sys config
prefix = __file__.rpartition('/')[0].rpartition('/')[0].rpartition('/')[0]
build_time_vars = {'a': '',
 'b': f'{prefix}/bin',
 'c': f'{prefix} {prefix}/lib '
}
"""

EXPECTED_EXTERNALLY_MANAGED = """
[externally-managed]
error = Global pip installations are not allowed
\tPlease use a virtual environment
"""


def _setup_exes(bin_folder):
    runez.ensure_folder(bin_folder, clean=True, logger=None)
    runez.touch(bin_folder / "foo-python", logger=None)
    runez.touch(bin_folder / "pip3.9", logger=None)
    runez.symlink(bin_folder / "foo-python", bin_folder / "python3", logger=None)  # Simulate a funky symlink, to test edge cases
    runez.write(bin_folder / "some-exe", "#!.../bin/python3\nhello", logger=None)
    runez.write(bin_folder / "some-exe2", "#!/bin/sh\nhello", logger=None)
    runez.write(bin_folder / "some-exe3", b"\xe4", logger=None)  # Non-unicode char to trigger edge case
    runez.make_executable(bin_folder / "some-exe", logger=None)
    runez.make_executable(bin_folder / "some-exe2", logger=None)
    runez.make_executable(bin_folder / "some-exe3", logger=None)


def test_finalization(cli, monkeypatch):
    f = PPG.get_folders(version="3.9.7")
    dummy_tarball(f, f"Python-{f.version}.tar.xz")
    dummy_tarball(f, "bzip2-1.0.8.tar.gz")
    bin_folder = f.resolved_destdir("bin")
    lib = f.resolved_destdir(f"lib/python{f.mm}")
    sys_cfg = lib / "_sysconfigdata__.py"

    runez.touch(f.components / "cpython/README", logger=None)
    runez.write(sys_cfg, SAMPLE_SYS_CONF.strip())

    # Create some files to be groomed by CPython
    runez.touch(lib.parent / "idle_test/foo", logger=None)
    runez.touch(lib.parent / "__phello__.foo.py", logger=None)
    runez.touch(lib / "site-packages/pip", logger=None)
    _setup_exes(bin_folder)
    runez.touch(lib / "config-3.9/libpython3.9.a", logger=None)

    monkeypatch.setenv("PP_X_DEBUG", "direct-finalize")
    monkeypatch.setenv("SOME_ENV", "some-env-value")
    with patch("runez.run", return_value=runez.program.RunResult(code=0)):
        cli.run("-tlinux-x86_64", "-c", cli.tests_path("sample-config1.yml"), "build", f.version, "-mbzip2")
        assert cli.succeeded
        manifest = list(runez.readlines(f"build/ppp-marker/{f.version}/.manifest.yml"))
        assert "  some_env: some-env-value" in manifest
        assert "selected: bzip2" in cli.logged
        assert "Pass 1: Cleaned 1 build artifact (0 B): idle_test" in cli.logged
        assert f"PEP 668: Cleaned 2 build artifacts (0 B): pip pip{f.mm}" in cli.logged
        assert f"Symlink {bin_folder}/foo-python <- {bin_folder}/python" in cli.logged
        assert f"Symlink {bin_folder}/pip{f.mm} <- {bin_folder}/pip" in cli.logged
        assert f"Auto-corrected shebang for {bin_folder}/some-exe" in cli.logged
        assert f"Symlink {lib}/config-3.9/libpython3.9.a <- {lib.parent}/libpython3.9.a" in cli.logged

    transformed = "\n".join(runez.readlines(sys_cfg))
    assert transformed.strip() == SAMPLE_SYS_CONF_REL.strip()

    expected = ["#!/bin/sh", '"exec" "$(dirname $0)/foo-python" "$0" "$@"', "# -*- coding: utf-8 -*-", "hello"]
    assert list(runez.readlines(bin_folder / "some-exe")) == expected
    assert list(runez.readlines(bin_folder / "some-exe2")) == ["#!/bin/sh", "hello"]
    assert runez.basename(bin_folder / "python", follow=True) == "foo-python"

    assert (lib / "EXTERNALLY-MANAGED").read_text().strip() == EXPECTED_EXTERNALLY_MANAGED.strip()

    _setup_exes(f.destdir / "opt/foo/bin")
    runez.touch(f.destdir / "opt/foo/lib/python3.9/site-packages/pip", logger=None)
    with patch("runez.run", return_value=runez.program.RunResult(code=0)):
        cli.run("-tmacos-arm64", "-c", cli.tests_path("sample-config1.yml"), "build", f.version, "--prefix", "/opt/foo", "-mbzip2")
        assert cli.succeeded
        assert f"Deleted build/opt/foo/bin/pip{f.mm}" in cli.logged
        assert f"PEP 668: Cleaned 2 build artifacts (0 B): pip pip{f.mm}" in cli.logged
        # bin/ exes remain unchanged with --prefix
        assert list(runez.readlines(f.destdir / "opt/foo/bin/some-exe")) == ["#!.../bin/python3", "hello"]

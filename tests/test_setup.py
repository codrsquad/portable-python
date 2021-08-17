import pytest
import runez

from portable_python.builder import BuildSetup, ModuleBuilder
from portable_python.builder.clibs import Openssl
from portable_python.builder.db import Gdbm
from portable_python.builder.x11 import Xproto
from portable_python.cli import InspectionReport

from .conftest import dummy_tarball


def test_edge_cases(temp_folder, logged):
    mb = ModuleBuilder()
    assert not mb.url
    assert not mb.version
    assert mb.checked_folder(runez.to_path("."), "-L") == "-L."

    report = InspectionReport("foo", "python", {})
    assert str(report) == "python"
    assert report.color("*absent*")
    assert report.color("built-in")
    assert report.color("foo")

    sample = runez.to_path("libs/foo.a")
    runez.touch(sample, logger=None)
    sample.chmod(0o600)
    BuildSetup.fix_lib_permissions(runez.to_path("libs"))

    assert str(BuildSetup.supported.cpython)
    latest = BuildSetup.supported.cpython.latest
    setup = BuildSetup(latest, modules="none")
    gdbm = Gdbm()
    gdbm.attach(setup)
    assert gdbm.skip_reason() == "needs readline"

    setup.architecture = "x86_64"
    setup.platform = "darwin"
    assert setup.is_macos
    assert not setup.is_linux
    assert Openssl.compiler(setup) == "darwin64-x86_64-cc"

    xproto = Xproto()
    xproto.attach(setup)
    assert xproto.skip_reason() == "linux only"

    setup = BuildSetup(latest, modules="readline")
    assert setup.prefix is None
    assert str(setup) == "build/cpython-%s" % latest
    assert str(setup.module_builders) == "15 external module builders"

    setup.platform = "windows"
    assert Openssl.compiler(setup) == "windows-x86_64"
    dummy_tarball("readline-8.1.tar.gz")
    with pytest.raises(runez.system.AbortException):
        setup.compile()
    assert "Compiling on platform 'windows' is not yet supported" in logged.pop()

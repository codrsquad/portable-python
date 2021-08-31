from unittest.mock import patch

from portable_python import BuildSetup, ModuleBuilder, PythonInspector, SoInfo
from portable_python.versions import PythonVersions


def test_edge_cases(monkeypatch):
    setup = BuildSetup(None, modules="+readline")
    assert setup.python_spec.version == PythonVersions.cpython.latest
    assert str(setup.python_builder.modules) == "+readline"

    setup = BuildSetup(None, target="linux-x86_64")
    assert setup.target_system.is_linux
    assert str(setup)
    assert str(PythonVersions.cpython)
    assert str(setup.python_builder.modules).startswith("auto-detected:")

    mb = ModuleBuilder(setup)
    assert not mb.url
    assert not mb.version
    assert str(mb.modules) == "no sub-modules"

    inspector = PythonInspector("0.1.2")
    assert str(inspector) == "0.1.2 [not available]"

    monkeypatch.setattr(inspector.python, "problem", None)
    monkeypatch.setattr(inspector, "output", "foo")
    assert inspector.report() == "0.1.2 [cpython:0.1.2]:\nfoo"


LDD_SAMPLE = """
    linux-vdso.so.1 (0x00007ffe98bb3000)
    libtcl8.6.so => /usr/lib/x86_64-linux-gnu/libtcl8.6.so (0x00007f8d8f379000)
    libtinfo.so.5 => not found (0x00007f7de012f000)
    /lib64/ld-linux-x86-64.so.2 (0x00007f7de0dbe000)
"""

OTOOL_SAMPLE = """
.../lib/python3.9/lib-dynload/_dbm.cpython-39-darwin.so:
 ....../foo/bar.dylib (compatibility version 8.0.0, current version 8.4.0)
 /usr/local/opt/gdbm/lib/libgdbm_compat.4.dylib (compatibility version 5.0.0, current version 5.0.0)
 /usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1281.0.0)
"""


def test_inspect_lib():
    with patch("runez.which", return_value=None):
        info = SoInfo("_dbm...so")
        assert str(info) == "_dbm"
        info.extract_info(OTOOL_SAMPLE, None)
        assert info.report() == "_dbm*.so /usr/local/opt/gdbm/lib/libgdbm_compat.4.dylib foo/bar.dylib"

        info = SoInfo("_tkinter...so")
        info.extract_info(None, LDD_SAMPLE)
        assert info.report() == "_tkinter*.so tcl:8.6 libtinfo.so.5 => not found"


def test_inspect_module(logged):
    # Exercise _inspect code
    import portable_python._inspect

    portable_python._inspect.main("readline,zlib,sys,os,foo-bar")
    assert '"readline": {' in logged.pop()

    portable_python._inspect.main("sysconfig")
    assert "VERSION:" in logged.pop()

    assert portable_python._inspect.pymodule_version_info("key", b"foo", None) == {"version_field": "key", "version": "foo"}
    assert portable_python._inspect.pymodule_version_info("key", (1, 2), None) == {"version_field": "key", "version": "1.2"}

    # Verify edge cases don't crash
    assert portable_python._inspect.pymodule_info("foo", [])
    assert not logged

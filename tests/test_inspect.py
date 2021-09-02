from unittest.mock import patch

from portable_python.inspect import PythonInspector, SoInfo, SysLibInfo, TargetSystem


OTOOL_SAMPLE = """
.../test-sample.so:
 ....../foo/bar.dylib (compatibility version 8.0.0, current version 8.4.0)
 /usr/local/opt/gdbm/lib/libgdbm_compat.4.dylib (compatibility version 5.0.0, current version 5.0.0)
 @rpath/libssl.45.dylib (compatibility version 46.0.0, current version 46.1.0)
 /usr/lib/libncurses.5.4.dylib (compatibility version 5.4.0, current version 5.4.0)
 /usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1281.0.0)
"""

LDD_SAMPLE = """
    linux-vdso.so.1 (...)
    libtcl8.6.so => /usr/lib/x86_64-linux-gnu/libtcl8.6.so (...)
    libtinfo.so.5 => not found
    libbz2.so.1.0 => /lib/x86_64-linux-gnu/libbz2.so.1.0 (...)
    libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (...)
    librt.so.1 => /lib/x86_64-linux-gnu/librt.so.1 (...)
    /lib64/ld-linux-x86-64.so.2 (...)
"""


def test_inspect_lib(logged):
    with patch("runez.which", return_value="yup"):
        not_there = SoInfo("/dev/null/foo")
        assert str(not_there) == "foo*_failed.so"
        assert not_there.size == 0
        assert "otool exited with code" in logged.pop()

    with patch("runez.which", return_value=None):
        info1 = SoInfo("_dbm...so", SysLibInfo(TargetSystem("darwin-x86_64")))
        assert str(info1) == "_dbm*.so"
        info1.parse_otool(OTOOL_SAMPLE)
        assert str(info1) == "_dbm*.so ncurses:5.4.0 foo/bar.dylib:8.4.0 /usr/local/opt/gdbm/lib/libgdbm_compat.4.dylib:5.0.0"

        # Exercise sorting / hashing / comparing
        other1 = sorted(info1.other_libs)
        assert len(other1) == 2
        assert other1[0] != other1[1]
        assert len(other1) == len(set(other1))

        info2 = SoInfo("_tkinter...so", SysLibInfo(TargetSystem("linux-x86_64")))
        info2.parse_ldd(LDD_SAMPLE)
        assert str(info2) == "_tkinter*.so bz2:1.0 tcl8:8.6 missing: tinfo:5"
        assert info1 != info2
        assert not (info1 == info2)
        assert not logged


def test_find_python(monkeypatch):
    inspector = PythonInspector("invoker")
    r = inspector.full_so_report
    assert r.ok
    if r.problematic:  # Will depend on how "clean" the python we're running this test with is
        r.problematic = []  # Clear any inherited problematics for this test

    if not r.system_libs:
        r.system_libs = ["foo"]  # Simulate presence of system libs

    # Verify using system libs on darwin is considered OK
    r.sys_lib_info.target.platform = "darwin"
    assert r.is_valid

    # Verify using system libs on linux is considered a fail
    r.sys_lib_info.target.platform = "linux"
    assert not r.is_valid

    # Verify no crash on bogus python installs inspection
    inspector = PythonInspector("0.1.2")
    assert str(inspector) == "0.1.2 [not available]"

    monkeypatch.setattr(inspector.python, "problem", None)
    monkeypatch.setattr(inspector, "output", "foo")
    assert inspector.report() == "0.1.2 [cpython:0.1.2]:\nfoo"


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

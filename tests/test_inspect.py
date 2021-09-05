from unittest.mock import patch

from portable_python.inspect import LibType, PythonInspector, SoInfo, TargetSystem


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
    libpython3.6m.so.1.0 => BASE/lib/libpython3.6m.dylib.1.0 (...)  # basename taken from left side
    libtcl8.6.so => /usr/lib/x86_64-linux-gnu/libtcl8.6.so (...)
    libtinfo.so.5 => not found
    libbz2.so.1.0 => /lib/x86_64-linux-gnu/libbz2.so.1.0 (...)
    libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (...)
    librt.so.1 => /lib/x86_64-linux-gnu/librt.so.1 (...)
    /lib64/ld-linux-x86-64.so.2 (...)
"""


def test_inspect_lib(logged):
    inspector = PythonInspector("invoker")
    with patch("runez.which", return_value="yup"):
        not_there = SoInfo(inspector, "/dev/null/foo.platform.so")
        assert str(not_there) == "foo*!.so"
        assert not_there.is_failed
        assert not_there.is_problematic
        assert not_there.size == 0
        assert "otool exited with code" in logged.pop()

    with patch("runez.which", return_value=None):
        inspector.target = TargetSystem("darwin-x86_64")
        inspector.install_folder = "BASE"
        info1 = SoInfo(inspector, "_dbm...so")
        assert str(info1) == "_dbm*!.so"
        info1.parse_otool(OTOOL_SAMPLE)
        r = info1.represented()
        assert r == "_dbm*!.so foo/bar.dylib:8.4.0 /usr/local/opt/gdbm/lib/libgdbm_compat.4.dylib:5.0.0 ncurses:5.4.0"

        inspector.target = TargetSystem("linux-x86_64")
        info2 = SoInfo(inspector, "_tkinter...so")
        info2.parse_ldd(LDD_SAMPLE)
        r = info2.represented()
        assert r == "_tkinter*!.so missing: tinfo:5 libpython3.6m.so.1.0 tcl8:8.6 bz2:1.0"


def test_find_python(monkeypatch):
    inspector = PythonInspector("invoker")
    assert str(inspector)
    assert str(inspector.module_info["_ctypes"])
    r = inspector.full_so_report
    assert r.ok

    if r.problematic:
        r.problematic.items = []  # Simulate a nice/clean report, even if invoker is not clean

    c = r.lib_tracker.category[LibType.system]
    assert c.items  # At least one system lib must be used by invoker

    # Verify using system libs on darwin is considered OK
    inspector.target.platform = "darwin"
    assert r.is_valid

    # Verify using system libs on linux is considered a fail
    inspector.target.platform = "linux"
    assert not r.is_valid


def test_inspect_module(logged):
    # Exercise _inspect code
    from portable_python.external import _inspect

    with patch("sysconfig.get_config_var", return_value="."):
        assert _inspect.get_srcdir()  # Just covering py2 edge case

    assert _inspect.get_simplified_dirs("/tmp/foo/bar") == ["/tmp/foo"]
    assert _inspect.get_simplified_dirs("/private/tmp/foo") == ["/private/tmp", "/tmp"]
    assert _inspect.get_simplified_dirs("/bar/foo/baz") == ["/bar/foo", "/bar"]

    _inspect.main("readline,zlib,sys,os,foo-bar")
    assert '"readline": {' in logged.pop()

    _inspect.main("sysconfig")
    assert "VERSION:" in logged.pop()

    assert _inspect.pymodule_version_info("key", b"foo", None) == {"version_field": "key", "version": "foo"}
    assert _inspect.pymodule_version_info("key", (1, 2), None) == {"version_field": "key", "version": "1.2"}

    # Verify edge cases don't crash
    assert _inspect.pymodule_info("foo", [])
    assert not logged

import builtins
import os
import sys
from unittest.mock import patch

import runez

from portable_python.inspector import find_libs, LibAutoCorrect, LibType, PPG, PythonInspector, SoInfo


def test_find_libs(temp_folder):
    runez.touch("python3.9/config-3.9/libpython3.9.so", logger=None)
    runez.touch("lib-foo.a", logger=None)
    runez.touch("lp.so.1.0", logger=None)
    runez.symlink("lp.so.1.0", "lp.so")
    runez.touch("lp.dylib", logger=None)
    runez.touch("foo/foo.so", logger=None)  # Folder not examined (looking only at known py subfolders)
    runez.touch("README.so.txt", logger=None)  # Not a dynamic lib
    runez.touch("lib-foo.a.1", logger=None)  # Not a lib
    x = sorted(str(x) for x in find_libs("."))
    assert x == ["lib-foo.a", "lp.dylib", "lp.so", "lp.so.1.0", "python3.9/config-3.9/libpython3.9.so"]


def test_inspect_python(temp_folder, monkeypatch):
    PPG.grab_config("foo.yml")
    inspector = PythonInspector("invoker")
    assert str(inspector)
    assert str(inspector.module_info["_ctypes"])
    r = inspector.full_so_report
    assert r.ok

    if r.problematic:
        r.problematic.items = []  # Simulate a nice/clean report, even if invoker is not clean

    c = r.lib_tracker.category[LibType.system]
    assert c.items  # At least one system lib must be used by invoker

    # Verify using system libs on macos is considered OK
    PPG.grab_config(target="macos-arm64")
    assert not r.get_problem(True)

    # Verify using system libs on linux is considered a fail
    PPG.grab_config(target="linux-x86_64")
    monkeypatch.setitem(PPG.config.default.data, "linux", {"allowed-system-libs": "/foo"})
    problem = r.get_problem(True)
    assert problem.startswith("Uses system libs:")


OTOOL_SAMPLE = """
.../test-sample.so:
 ....../foo/bar.dylib (compatibility version 8.0.0, current version 8.4.0)
 /usr/local/opt/gdbm/lib/libgdbm_compat.4.dylib (compatibility version 5.0.0, current version 5.0.0)
 @rpath/libssl.45.dylib (compatibility version 46.0.0, current version 46.1.0)
 /usr/lib/libncurses.5.4.dylib (compatibility version 5.4.0, current version 5.4.0)
 /usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1281.0.0)
"""

LDD_SAMPLE = """
    linux-vdso.so.1 => (...)
    libpython3.6m.so.1.0 => /BASE/lib/libpython3.6m.dylib.1.0 (...)  # basename taken from left side
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
        assert inspector.libpython_report([not_there])  # Verify no crash, edge case testing

    with patch("runez.which", return_value=None):
        PPG.grab_config(target="macos-x86_64")
        info1 = SoInfo(inspector, "_dbm...so")
        assert str(info1) == "_dbm*!.so"
        info1.parse_otool(OTOOL_SAMPLE)
        r = info1.represented()
        assert r == "_dbm*!.so foo/bar.dylib:8.4.0 /usr/local/opt/gdbm/lib/libgdbm_compat.4.dylib:5.0.0 ncurses:5.4.0"
        rv = info1.represented(verbose=True)
        assert "[base] @rpath/libssl.45.dylib 46.1.0" in rv

        PPG.grab_config(target="linux-x86_64")
        inspector.install_folder = "/BASE"
        info2 = SoInfo(inspector, "_tkinter...so")
        info2.parse_ldd(LDD_SAMPLE)
        r = info2.represented()
        assert r == "_tkinter*!.so missing: tinfo:5 libpython3.6m.so.1.0 tcl8:8.6 bz2:1.0"


def test_inspect_module(logged):
    # Exercise _inspect code
    from portable_python.external import _inspect

    with patch("sysconfig.get_config_var", return_value="."):
        assert _inspect.get_srcdir()  # Just covering py2 edge case

    assert _inspect.get_simplified_dirs("/tmp/foo/bar") == ["/tmp/foo"]
    assert _inspect.get_simplified_dirs("/private/tmp/foo") == ["/private/tmp", "/tmp"]
    assert _inspect.get_simplified_dirs("/bar/foo/baz") == ["/bar/foo", "/bar"]

    _inspect.main("readline,zlib,pip,sys,os,foo-bar")
    assert '"readline": {' in logged.pop()

    _inspect.main("sysconfig")
    assert "VERSION:" in logged.pop()

    assert _inspect.pymodule_version_info("key", b"1.2", None) == {"version_field": "key", "version": "1.2"}
    assert _inspect.pymodule_version_info("key", (1, 2), None) == {"version_field": "key", "version": "1.2"}
    with patch("portable_python.external._inspect.pymodule_version_info", side_effect=Exception):
        assert "note" in _inspect.module_report("sys")

    # Edge cases
    assert _inspect.pymodule_info("builtins", builtins)
    assert _inspect.pymodule_info("foo", [])
    assert not logged


class MockSharedExeRun:
    def __init__(self, platform, prefix):
        PPG.grab_config(target=f"{platform}-x86_64")
        self.program_handler = getattr(self, "_%s_run" % platform)
        self.prefix = prefix
        self.called = []

    def _linux_run(self, *args):
        if args[1] == "--print-rpath":
            return self.prefix

    def _macos_run(self, program, *_):
        if program == "otool":
            return f"foo/bin/python:\n {self.prefix}/lib/libpython3.9.dylib (...)\n /usr/lib/... (...)"

    def __call__(self, *args, **_):
        x = self.program_handler(*args)
        if x is not None:
            return runez.program.RunResult(code=0, output=x)

        with runez.Anchored(os.getcwd()):
            self.called.append(runez.quoted(*args))
            return runez.program.RunResult(code=0)

    def __enter__(self):
        self.mock = patch("runez.run", side_effect=self)
        self.mock.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.mock.stop()


def test_lib_auto_correct(temp_folder):
    runez.touch("foo/bin/python", logger=None)
    runez.make_executable("foo/bin/python", logger=None)
    runez.touch("foo/lib/libpython3.9.dylib", logger=None)
    runez.touch("foo/lib/bar/baz.dylib", logger=None)
    foo_path = runez.to_path("foo").absolute()
    with MockSharedExeRun("macos", "/3.9.6") as m:
        ac = LibAutoCorrect(m.prefix, foo_path)
        ac.run()
        expected = [
            "install_name_tool -add_rpath @executable_path/../lib foo/bin/python",
            "install_name_tool -change /3.9.6/lib/libpython3.9.dylib @rpath/libpython3.9.dylib foo/bin/python",
            "install_name_tool -add_rpath @loader_path/.. foo/lib/bar/baz.dylib",
            "install_name_tool -change /3.9.6/lib/libpython3.9.dylib @rpath/libpython3.9.dylib foo/lib/bar/baz.dylib",
        ]
        assert m.called == expected

    with MockSharedExeRun("linux", "/3.9.6") as m:
        ac = LibAutoCorrect(m.prefix, foo_path)
        ac.run()
        expected = [
            "patchelf --set-rpath /3.9.6/lib:$ORIGIN/../lib foo/bin/python",
            "patchelf --set-rpath /3.9.6/lib:$ORIGIN/.. foo/lib/bar/baz.dylib",
            "patchelf --set-rpath /3.9.6/lib:$ORIGIN/. foo/lib/libpython3.9.dylib",
        ]
        assert m.called == expected

    with MockSharedExeRun("linux", "/ppp-marker/3.9.6") as m:
        ac = LibAutoCorrect(m.prefix, foo_path, ppp_marker=m.prefix)
        ac.run()
        expected = [
            "patchelf --set-rpath $ORIGIN/../lib foo/bin/python",
            "patchelf --set-rpath $ORIGIN/..:$ORIGIN/../lib foo/lib/bar/baz.dylib",
            "patchelf --set-rpath $ORIGIN/.:$ORIGIN/../lib foo/lib/libpython3.9.dylib",
        ]
        assert m.called == expected


def test_tool_version():
    x = PythonInspector.tool_version(sys.executable)
    sp = sys.version_info
    assert x == f"{sp[0]}.{sp[1]}.{sp[2]}"

    x = PythonInspector.parsed_version("gcc (GCC) 4.8.5 20150623 (Red Hat 4.8.5-44)")
    assert x == "4.8.5"

    x = PythonInspector.parsed_version("ldd (GNU libc) 2.17")
    assert x == "2.17"

    x = PythonInspector.parsed_version("ldd (Ubuntu GLIBC 2.35-0ubuntu3.1) 2.35")
    assert x == "2.35"

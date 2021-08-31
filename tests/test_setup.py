from portable_python import BuildSetup, ModuleBuilder, PythonInspector
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

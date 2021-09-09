from portable_python import BuildSetup, ModuleBuilder
from portable_python.versions import PythonVersions


def test_edge_cases(monkeypatch):
    monkeypatch.setenv("PP_TARGET", "linux-x86_64")
    setup = BuildSetup(None, modules="+readline")
    assert setup.python_spec.version == PythonVersions.cpython.latest
    assert str(setup.python_builder.modules) == "+readline"

    setup = BuildSetup(None)
    assert str(setup)
    assert str(PythonVersions.cpython)
    assert str(setup.python_builder.modules).startswith("auto-detected:")

    mb = ModuleBuilder(setup)
    assert not mb.url
    assert not mb.version
    assert str(mb.modules) == "no sub-modules"

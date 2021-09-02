from portable_python import BuildSetup, ModuleBuilder
from portable_python.versions import PythonVersions


def test_edge_cases():
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

from portable_python import PythonInspector
from portable_python.builder import BuildSetup, ModuleBuilder
from portable_python.versions import PythonVersions


def test_edge_cases():
    latest = PythonVersions.cpython.latest
    setup = BuildSetup(latest, target="linux-x86_64")
    assert setup.target_system.is_linux
    assert str(setup).endswith(f"build/cpython-{latest}")
    assert str(setup.python_builder) == f"cpython {latest}"
    assert str(PythonVersions.cpython).startswith("cpython ")

    mb = ModuleBuilder()
    assert not mb.url
    assert not mb.version

    inspector = PythonInspector("0.1.2")
    r0 = inspector.reports[0]
    assert str(r0) == "0.1.2 [not available]"
    assert r0.color("*absent*")
    assert r0.color("built-in")
    assert r0.color("foo")

    r = inspector._python_report("no-such-exe")
    assert r["exit_code"]

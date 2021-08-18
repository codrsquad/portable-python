from portable_python.builder import BuildSetup, ModuleBuilder
from portable_python.cli import InspectionReport


def test_edge_cases():
    latest = BuildSetup.supported.cpython.latest
    setup = BuildSetup(latest, target="linux-x86_64")
    assert setup.target_system.is_linux
    assert str(setup).endswith(f"build/cpython-{latest}")
    assert str(setup.python_builder) == f"cpython {latest}"
    assert str(setup.supported.cpython).startswith("cpython ")
    assert str(setup.python_builders) == "1 python builder"

    mb = ModuleBuilder()
    assert not mb.url
    assert not mb.version

    report = InspectionReport("foo", "python", {})
    assert str(report) == "python"
    assert report.color("*absent*")
    assert report.color("built-in")
    assert report.color("foo")

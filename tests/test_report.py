from unittest.mock import patch


def test_scan(cli):
    cli.run("-tmacos-x86_64", "build-report", "-mnone", "3.9.7")
    assert cli.succeeded

    with patch("portable_python.cpython.runez.which", return_value=None):
        cli.run("-tlinux-x86_64", "build-report", "-mall", "3.9.7")
        assert cli.failed
        assert "needs tclsh" in cli.logged
        assert "Problematic modules:" in cli.logged

from unittest.mock import patch

from portable_python.versions import PPG


def test_scan(cli):
    cli.run("-tmacos-x86_64", "build-report", "-mnone", "3.9.7")
    assert cli.succeeded

    with patch("portable_python.cpython.runez.which", return_value=None):
        cli.run("-tlinux-x86_64", "build-report", "-mall", "3.9.7")
        assert cli.failed
        assert "needs tclsh" in cli.logged
        assert "Problematic modules:" in cli.logged

    with patch.object(PPG, "find_telltale", return_value=None):  # Simulate a host without any system headers
        cli.run("-tlinux-x86_64", "build-report", "3.14.0")
        assert "zstd         1.5.7    static*  broken, can't compile without libzstd-dev" in cli.logged  # Auto-selected ('*')
        assert "mpdec        4.0.1    static*  broken, can't compile without libmpdec-dev" in cli.logged

        cli.run("-tmacos-arm64", "build-report", "3.14.0")
        assert "mpdec        4.0.1    static*  [auto-selected] Required for 3.14 and up" in cli.logged

from runez.http import RestClient

from portable_python import BuildSetup
from portable_python.versions import CPythonFamily, PPG

REST_CLIENT = RestClient()
GH_CPYTHON_SAMPLE = """
[
{"ref": "refs/tags/v3.9.7"},
{"ref": "refs/tags/v3.8.12"},
{"ref": "refs/tags/v3.5.10"}
]
"""

PYTHON_ORG_SAMPLE = """
<a href="3.9.5/">3.9.5/</a>
<a href="3.9.6/">3.9.6/</a>
<a href="3.8.11/">3.9.11/</a>
<a href="3.5.10/">3.5.10/</a>
"""


@REST_CLIENT.mock(
    {
        "https://www.python.org/ftp/python/": PYTHON_ORG_SAMPLE,
        "https://api.github.com/repos/python/cpython/git/matching-refs/tags/v3.": GH_CPYTHON_SAMPLE,
    },
)
def test_list(cli, monkeypatch):
    # Edge cases
    monkeypatch.setattr(PPG, "config", None)
    PPG.grab_config(target="macos-arm64")
    setup = BuildSetup()
    assert setup.python_spec.version == PPG.cpython.latest

    cp = CPythonFamily()
    assert str(cp.latest) == "3.9.6"

    monkeypatch.setattr(PPG.cpython, "_versions", None)
    cli.run("list")
    assert cli.succeeded
    assert cli.logged.stdout.contents().strip() == "cpython:\n  3.9: 3.9.6\n  3.8: 3.8.11"

    cli.run("list", "--json")
    assert cli.succeeded
    assert cli.logged.stdout.contents().startswith("{")

    cli.run("list", "conda")
    assert cli.failed
    assert "Python family 'conda' is not yet supported" in cli.logged

    monkeypatch.setattr(PPG.cpython, "_versions", None)
    cli.run("-c", cli.tests_path("sample-config1.yml"), "list")
    assert cli.succeeded
    assert cli.logged.stdout.contents().strip() == "cpython:\n  3.9: 3.9.7\n  3.8: 3.8.12"

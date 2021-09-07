import runez
from runez.conftest import cli, logged, temp_folder  # noqa: fixtures
from runez.http import GlobalHttpCalls
from runez.pyenv import Version

from portable_python.cli import main
from portable_python.versions import PythonVersions


GlobalHttpCalls.forbid()
PythonVersions.cpython.latest = Version("3.9.7")

# Ensure common logging setup is done throughout all tests (even tests not invoking cli)
runez.log.setup(debug=True, console_format="%(levelname)s %(message)s", locations=None)

cli.default_main = main


def dummy_tarball(basename):
    runez.touch("sample/README", logger=None)
    runez.compress("sample", "build/downloads/%s" % basename, logger=None)
    runez.delete("sample", logger=None)

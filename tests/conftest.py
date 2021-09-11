import runez
from runez.conftest import cli, logged, temp_folder  # noqa: fixtures
from runez.http import GlobalHttpCalls

from portable_python.cli import main


GlobalHttpCalls.forbid()

# Ensure common logging setup is done throughout all tests (even tests not invoking cli)
runez.log.setup(debug=True, console_format="%(levelname)s %(message)s", locations=None)

cli.default_main = main


def dummy_tarball(basename, content=None):
    runez.write("sample/README", content, logger=None)
    runez.compress("sample", "build/downloads/%s" % basename, logger=None)
    runez.delete("sample", logger=None)

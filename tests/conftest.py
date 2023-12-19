import runez
from runez.conftest import cli, logged, temp_folder
from runez.http import GlobalHttpCalls

from portable_python.cli import main

GlobalHttpCalls.forbid()

# These are fixtures, satisfying linters with an assert
assert logged
assert temp_folder

# Ensure common logging setup is done throughout all tests (even tests not invoking cli)
runez.log.setup(debug=True, console_format="%(levelname)s %(message)s", locations=None)

cli.default_main = main


def dummy_tarball(folders, basename, content=None):
    runez.write("sample/README", content, logger=None)
    runez.compress("sample", folders.sources / basename, logger=None)
    runez.delete("sample", logger=None)

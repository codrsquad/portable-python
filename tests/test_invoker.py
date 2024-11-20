import re
import sys


def test_invoker(cli):
    cli.run("inspect", "invoker", "-v", "-mall")

    # Invoker may not be completely clean, but it has to have at least one OK .so usage
    m = re.search(r"^\.so files: .+, (\d+) OK", cli.logged.stdout.contents(), re.MULTILINE)
    assert m
    reported = int(m.group(1))
    assert reported > 0


def test_module_invocation(cli):
    cli.exercise_main("src/portable_python/external/_inspect.py")
    cli.exercise_main("-mportable_python", "src/portable_python/cli.py")


def test_relativize(cli):
    cli.run("lib-auto-correct", sys.executable)
    assert cli.succeeded

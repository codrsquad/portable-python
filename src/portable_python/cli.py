import json
import logging
import os

import click
import runez
from runez.pyenv import PythonDepot
from runez.render import PrettyTable

from portable_python import LOG
from portable_python.builder import BuildSetup


@runez.click.group()
@runez.click.version()
@runez.click.color()
@runez.click.debug("-v")
@runez.click.dryrun("-n")
def main(debug):
    """
    Build (optionally portable) python binaries
    """
    runez.system.AbortException = SystemExit
    runez.log.setup(
        debug=debug,
        console_format="%(levelname)s %(message)s",
        console_level=logging.INFO,
        default_logger=LOG.info,
        locations=None,
    )


@main.command()
@click.option("--build", "-b", default="build", metavar="PATH", show_default=True, help="Build folder to use")
@click.option("--dist", "-d", default="dist", metavar="PATH", show_default=True, help="Folder where to put compiled binary tarball")
@click.option("--modules", "-m", metavar="CSV", help="External modules to include")
@click.option("--prefix", "-p", metavar="PATH", help="Build a shared-libs python targeting given prefix folder")
@click.option("--x-finalize", hidden=True, is_flag=True, help="Internal, for debugger runs")
@click.argument("pytarget")
def build(build, dist, modules, prefix, x_finalize, pytarget):
    """Build a python binary"""
    setup = BuildSetup(pytarget, prefix=prefix, modules=modules, build_folder=build, dist_folder=dist)
    setup.compile(clean=not x_finalize)


@main.command()
@click.option("--modules", "-m", help="Modules to inspect")
@click.argument("pythons", nargs=-1)
def inspect(modules, pythons):
    """Overview of python internals"""
    inspector = PythonInspector(pythons, modules)
    print(runez.joined(inspector.report(), delimiter="\n"))


class PythonInspector:

    def __init__(self, specs, modules):
        self.inspector_path = os.path.join(os.path.dirname(__file__), "_inspect.py")
        self.specs = runez.flattened(specs, keep_empty=None, split=",")
        self.modules = modules
        self.depot = PythonDepot(use_path=False)
        self.reports = [self.inspection_report(p) for p in self.specs]

    def report(self):
        for r in self.reports:
            if r.report:
                if r.python.problem:
                    yield runez.short("%s: %s" % (runez.blue(r.spec), runez.red(r.python.problem)))

                else:
                    yield "%s:" % runez.blue(r.python)
                    yield r.represented() or ""

    def inspection_report(self, spec):
        python = self.depot.find_python(spec)
        report = None
        if python.problem:
            report = dict(problem=python.problem)

        else:
            r = runez.run(python.executable, self.inspector_path, self.modules, fatal=False, logger=print if runez.DRYRUN else LOG.debug)
            if not runez.DRYRUN:
                report = json.loads(r.output) if r.succeeded else dict(exit_code=r.exit_code, error=r.error, output=r.output)

        return InspectionReport(spec, python, report)


class InspectionReport:

    def __init__(self, spec, python, report):
        self.spec = spec
        self.python = python
        self.report = report

    def __repr__(self):
        return str(self.python)

    @staticmethod
    def color(text):
        if text.startswith("*"):
            return runez.orange(text)

        if text == "built-in":
            return runez.blue(text)

        if text.startswith(("lib/", "lib64/")):
            return runez.green(text)

        return text

    def represented(self):
        if self.report:
            t = PrettyTable(2)
            t.header[0].align = "right"
            for k, v in sorted(self.report.items()):
                v = runez.short(v or "*empty*")
                t.add_row(k, self.color(v))

            return "%s\n" % t


if __name__ == "__main__":
    from portable_python.cli import main  # noqa, re-import with proper package

    main()

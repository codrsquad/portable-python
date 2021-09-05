import logging
import sys

import click
import runez

from portable_python import BuildSetup, CLEANABLE_CHOICES, LOG
from portable_python.inspect import PythonInspector
from portable_python.versions import PythonVersions


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
    runez.log.timeit.logger = LOG.info
    runez.log.setup(
        debug=debug,
        console_format="%(levelname)s %(message)s",
        console_level=logging.INFO,
        default_logger=LOG.info,
        locations=None,
    )


@main.command()
@click.option("--build", "-b", default="build", metavar="PATH", show_default=True, help="Build folder to use")
@click.option("--clean", "-c", multiple=True, metavar="CSV", help="State what to cleanup, one of: %s" % CLEANABLE_CHOICES)
@click.option("--dist", "-d", default="dist", metavar="PATH", show_default=True, help="Folder where to put compiled binary tarball")
@click.option("--modules", "-m", metavar="CSV", help="External modules to include")
@click.option("--prefix", "-p", metavar="PATH", help="Build a shared-libs python targeting given prefix folder")
@click.option("--target", hidden=True, help="Target system, useful only for --dryrun for now, example: darwin-x86_64")
@click.option("--x-debug", is_flag=True, hidden=True, help="For debugging, allows to build one module at a time")
@click.argument("python_spec")
def build(build, clean, dist, modules, prefix, x_debug, target, python_spec):
    """Build a python binary"""
    setup = BuildSetup(python_spec, build_base=build, dist_folder=dist, modules=modules, prefix=prefix, target=target)
    setup.set_requested_clean(clean)
    setup.compile(x_debug=x_debug)


@main.command()
@click.option("--modules", "-m", help="Modules to inspect")
@click.option("--verbose", "-v", is_flag=True, multiple=True, default=None, help="Show full so report")
@click.argument("pythons", nargs=-1)
def inspect(modules, verbose, pythons):
    """Inspect a python installation for non-portable dynamic lib usage"""
    verbose = len(verbose)
    exit_code = 0
    count = 0
    for spec in runez.flattened(pythons, split=","):
        if count:
            print()

        count += 1
        if spec != "invoker":
            spec = runez.resolved_path(spec)

        inspector = PythonInspector(spec, modules)
        print(inspector.represented(verbose=verbose))
        if modules is None and not inspector.full_so_report.is_valid:
            exit_code = 1

    sys.exit(exit_code)


@main.command()
@click.argument("family", nargs=-1)
def list(family):
    """List supported versions"""
    if not family:
        family = list(PythonVersions.families.keys())

    indent = "" if len(family) == 1 else "  "
    for family_name in family:
        if indent:
            if family_name != family[0]:
                print()

            print(f"{family_name}:")

        fam = PythonVersions.family(family_name, fatal=False)
        if fam:
            for v in fam.versions:
                print(f"{indent}{v}")

        else:
            print("%s%s" % (indent, runez.red("not supported")))


@main.command()
@click.option("--modules", "-m", metavar="CSV", help="External modules to include")
@click.option("--target", hidden=True, help="Target system, useful only for --dryrun for now, example: darwin-x86_64")
@click.argument("python_spec", required=False)
def scan(modules, target, python_spec):
    """Scan all buildable modules, see if system already has equivalent"""
    setup = BuildSetup(python_spec, modules=modules, target=target)
    print(runez.bold(setup.python_spec))
    print(setup.python_builder.modules.report())


if __name__ == "__main__":
    from portable_python.cli import main  # noqa, re-import with proper package

    main()

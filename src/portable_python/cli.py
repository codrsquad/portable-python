import logging

import click
import runez
from runez.render import PrettyTable

from portable_python import BuildSetup, LOG, PythonInspector, TargetSystem
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
@click.option("--dist", "-d", default="dist", metavar="PATH", show_default=True, help="Folder where to put compiled binary tarball")
@click.option("--modules", "-m", metavar="CSV", help="External modules to include")
@click.option("--prefix", "-p", metavar="PATH", help="Build a shared-libs python targeting given prefix folder")
@click.option("--static/--no-static", is_flag=True, default=False, show_default=True, help="Keep static library?")
@click.option("--target", hidden=True, help="Target system, useful only for --dryrun for now, example: darwin-x86_64")
@click.option("--x-debug", is_flag=True, hidden=True, help="For debugging, allows to build one module at a time")
@click.argument("python_spec")
def build(build, dist, modules, prefix, static, x_debug, target, python_spec):
    """Build a python binary"""
    setup = BuildSetup(python_spec, modules=modules, build_folder=build, dist_folder=dist, target=target)
    setup.prefix = prefix
    setup.static = static
    setup.compile(x_debug=x_debug)
    if setup.python_builder.install_folder.is_dir():
        inspector = PythonInspector(setup.python_builder.install_folder)
        print(inspector.report())


@main.command()
@click.option("--modules", "-m", help="Modules to inspect")
@click.argument("pythons", nargs=-1)
def inspect(modules, pythons):
    """Overview of python internals"""
    inspector = PythonInspector(pythons, modules)
    print(inspector.report())


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
@click.option("--target", hidden=True, help="Target system, useful only for --dryrun for now, example: darwin-x86_64")
@click.argument("family", nargs=-1)
def scan(target, family):
    """Scan all buildable modules, see if system already has equivalent"""
    if not family:
        family = ["cpython"]

    family = runez.flattened(family, keep_empty=None, split=",", unique=True)
    indent = "  " if len(family) > 1 else ""
    for family_name in family:
        if indent:
            print(runez.bold("%s%s:" % ("" if family_name == family[0] else "\n", family_name)))

        fam = PythonVersions.family(family_name, fatal=False)
        if not fam:
            print("%s%s" % (indent, runez.red("unknown")))
            continue

        ts = TargetSystem(target)
        reasons = fam.builder.get_scan_report(ts)
        table = PrettyTable(2)
        table.header[0].align = "right"
        rows = []
        for mod in fam.builder.available_modules:
            rows.append((mod.m_name, reasons[mod.m_name]))

        table.add_rows(*rows)
        print(table)


if __name__ == "__main__":
    from portable_python.cli import main  # noqa, re-import with proper package

    main()

import logging

import click
import runez
from runez.render import PrettyTable

from portable_python import LOG, PythonInspector
from portable_python.builder import BuildSetup, TargetSystem


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
@click.option("--static", is_flag=True, help="Try building a static executable (experimental, work in progress)")
@click.option("--target", help="Target system, useful only for --dryrun for now, example: darwin-x86_64")
@click.option("--x-debug", hidden=True, is_flag=True, help="For debugging, allows to build one module at a time")
@click.argument("python_spec")
def build(build, dist, modules, prefix, static, x_debug, target, python_spec):
    """Build a python binary"""
    setup = BuildSetup(python_spec, modules=modules, build_folder=build, dist_folder=dist, target=target)
    setup.prefix = prefix
    setup.static = static
    setup.compile(x_debug=x_debug)
    bin_folder = setup.python_builder.bin_folder
    if bin_folder.is_dir():
        inspector = PythonInspector(bin_folder.parent)
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
        family = BuildSetup.supported.all_family_names

    indent = "" if len(family) == 1 else "  "
    for family_name in family:
        if indent:
            if family_name != family[0]:
                print()

            print(f"{family_name}:")

        fam = BuildSetup.supported.family(family_name, fatal=False)
        if fam:
            for v in fam.versions:
                print(f"{indent}{v}")

        else:
            print("%s%s" % (indent, runez.red("not supported")))


@main.command()
@click.argument("target", required=False)
def scan(target):
    """Scan all buildable modules, see if system already has equivalent"""
    ts = TargetSystem(target)
    BuildSetup.module_builders.ensure_imported()
    table = PrettyTable(2)
    table.header[0].align = "right"
    for name in sorted(BuildSetup.module_builders.available):
        mod = BuildSetup.module_builders.available.get(name)
        if not mod.telltale:
            report = runez.brown("has no telltale file")

        elif not ts.is_applicable(mod):
            report = runez.brown(f"not applicable to {ts}")

        else:
            path = mod.existing_telltale(ts)
            if path:
                report = "%s, %s" % (runez.orange("skipped"), runez.dim("has %s" % runez.short(path)))

            else:
                report = "%s, no %s" % (runez.green("needed"), mod.telltale)

        table.add_row(name, report)

    print(table)


if __name__ == "__main__":
    from portable_python.cli import main  # noqa, re-import with proper package

    main()

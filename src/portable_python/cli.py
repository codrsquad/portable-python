import logging
import os
import sys

import click
import runez
from runez.pyenv import PythonDepot
from runez.render import PrettyTable

from portable_python import BuildSetup, PPG, PythonInspector


LOG = logging.getLogger(__name__)


@runez.click.group()
@runez.click.version()
@runez.click.color()
@runez.click.debug("-v")
@runez.click.dryrun("-n")
@click.option("--config", "-c", metavar="PATH", default="portable-python.yml", show_default=True, help="Path to config file to use")
@click.option("--target", "-t", hidden=True, help="For internal use / testing")
def main(debug, config, target):
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
    PPG.grab_config(path=config, base_folder=os.environ.get("PP_BASE") or os.getcwd(), target=target)


@main.command()
@click.option("--modules", "-m", metavar="CSV", help="External modules to include")
@click.option("--prefix", "-p", metavar="PATH", help="Use given --prefix for python installation (not portable)")
@click.argument("python_spec")
def build(modules, prefix, python_spec):
    """Build a portable python binary"""
    setup = BuildSetup(python_spec, modules=modules, prefix=prefix)
    setup.compile()


@main.command()
@click.option("--modules", "-m", metavar="CSV", help="External modules to include")
@click.argument("python_spec", required=False)
def build_report(modules, python_spec):
    """Show status of buildable modules, which will be auto-compiled"""
    setup = BuildSetup(python_spec, modules=modules)
    print(runez.bold(setup.python_spec))
    report = setup.python_builder.modules.report()
    print(report)
    setup.validate_module_selection()


@main.command()
def diagnostics():
    """Show diagnostics info"""
    depot = PythonDepot(use_path=True)
    depot.scan_path_env_var()

    def _diagnostics():
        yield "invoker python", depot.invoker
        yield from runez.SYS_INFO.diagnostics()

    config = PPG.config.represented()
    print(PrettyTable.two_column_diagnostics(_diagnostics(), depot.representation(), config))


@main.command()
@click.option("--modules", "-m", help="Modules to inspect")
@click.option("--verbose", "-v", is_flag=True, multiple=True, default=None, help="Show full so report")
@click.option("--prefix", "-p", is_flag=True, help="Build was done with --prefix (not portable)")
@click.argument("pythons", nargs=-1)
def inspect(modules, verbose, prefix, pythons):
    """Inspect a python installation for non-portable dynamic lib usage"""
    verbose = len(verbose)
    if not verbose and (not modules or modules == "all"):
        verbose = 1

    exit_code = 0
    count = 0
    pythons = runez.flattened(pythons, split=",")
    for spec in pythons:
        if count:
            print()

        count += 1
        if spec != "invoker":
            spec = runez.resolved_path(spec)

        inspector = PythonInspector(spec, modules=modules)
        if inspector.python.problem:
            print("%s: %s" % (runez.blue(runez.short(inspector.python.executable)), runez.red(inspector.python.problem)))
            exit_code = 1
            continue

        if verbose > 1 or len(pythons) > 1:
            print(runez.blue(inspector.python))

        print(inspector.represented(verbose=verbose))
        if not modules or modules == "all":
            problem = inspector.full_so_report.get_problem(portable=not prefix)
            if problem:
                LOG.error(f"Build problem: {problem}")
                exit_code = 1

    sys.exit(exit_code)


@main.command(name="list")
@click.option("--json", is_flag=True, help="Json output")
@click.argument("family", default="cpython")
def list_cmd(json, family):
    """List latest versions"""
    fam = PPG.family(family, fatal=False)
    if not fam:
        runez.abort("Python family '%s' is not yet supported" % runez.red(family))

    if json:
        print(runez.represented_json(fam.available_versions))
        return

    print("%s:" % runez.bold(family))
    for mm, v in fam.available_versions.items():
        print("  %s: %s" % (runez.bold(mm), v))


def _find_recompress_source(dist, path):
    path = runez.to_path(path)
    if path.exists() or path.is_absolute():
        return path.absolute() if path.exists() else None

    candidates = ["{path}", "build/{path}", "build/cpython-{path}/{path}"]
    for candidate in candidates:
        cp = candidate.format(path=path)
        for p in (dist / cp, dist.parent / cp):
            if p.exists():
                return p.absolute()


@runez.log.timeit
def recompress_folder(dist, path, extension):
    """Recompress folder"""
    dest = runez.SYS_INFO.platform_id.composed_basename("cpython", path.name, extension=extension)
    dest = dist / dest
    runez.compress(path, dest, logger=print)
    return dest


@runez.log.timeit
def recompress_archive(dist, path, extension):
    stem = path.name.rpartition(".")[0]
    if stem.endswith(".tar"):
        stem = stem.rpartition(".")[0]

    dest = "%s.%s" % (stem, extension)
    dest = dist / dest
    if dest == path:
        dest = "%s.%s" % (stem + "-recompressed", extension)
        dest = dist / dest

    with runez.TempFolder() as _:
        tmp_folder = runez.to_path("tmp")
        runez.decompress(path, tmp_folder, simplify=True, logger=print)
        runez.compress(tmp_folder, dest.name, arcname=dest.name, logger=print)
        runez.move(dest.name, dest, logger=print)

    return dest


@main.command()
@click.argument("path", required=True)
@click.argument("ext", required=True, type=click.Choice(runez.SYS_INFO.platform_id.supported_compression))
def recompress(path, ext):
    """
    Re-compress an existing binary tarball, or folder

    \b
    Mildly useful for comparing sizes from different compressions
    """
    extension = runez.SYS_INFO.platform_id.canonical_compress_extension(ext)
    dist = PPG.config.dist_folder
    with runez.Anchored(dist.parent):
        actual_path = _find_recompress_source(dist, path)
        if not actual_path:
            runez.abort("'%s' does not exist" % runez.red(runez.short(path)))

        if actual_path.is_dir():
            dest = recompress_folder(dist, actual_path, extension)

        else:
            dest = recompress_archive(dist, actual_path, extension)

        print("Size of %s: %s" % (runez.short(actual_path), runez.bold(runez.represented_bytesize(actual_path))))
        print("Size of %s: %s" % (runez.short(dest), runez.bold(runez.represented_bytesize(dest))))


if __name__ == "__main__":
    from portable_python.cli import main  # noqa, re-import with proper package

    main()

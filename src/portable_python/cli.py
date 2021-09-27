import logging

import click
import runez
from runez.pyenv import PythonDepot, PythonSpec
from runez.render import PrettyTable

from portable_python import BuildSetup, PPG
from portable_python.inspector import LibAutoCorrect, PythonInspector


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
    PPG.grab_config(config, target=target)


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
    with runez.Anchored("."):
        depot = PythonDepot(use_path=True)
        depot.scan_path_env_var()

        def _diagnostics():
            yield "invoker python", depot.invoker
            yield from runez.SYS_INFO.diagnostics()

        config = PPG.config.represented()
        print(PrettyTable.two_column_diagnostics(_diagnostics(), depot.representation(), config))


@main.command()
@click.option("--modules", "-m", help="Modules to inspect")
@click.option("--verbose", "-v", is_flag=True, help="Show full so report")
@click.option("--prefix", "-p", is_flag=True, help="Build was done with --prefix (not portable)")
@click.argument("path")
def inspect(modules, verbose, prefix, path):
    """Inspect a python installation for non-portable dynamic lib usage"""
    if path != "invoker":
        path = runez.resolved_path(path)

    inspector = PythonInspector(path, modules=modules)
    runez.abort_if(inspector.python.problem, "%s: %s" % (runez.red(path), inspector.python.problem))
    print(runez.blue(inspector.python))
    print(inspector.represented(verbose=verbose))
    if not modules or modules == "all":
        problem = inspector.full_so_report.get_problem(portable=not prefix)
        runez.abort_if(problem)


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


def _find_recompress_source(folders, path):
    candidate = runez.to_path(path)
    if candidate.exists() or candidate.is_absolute():
        return candidate.absolute() if candidate.exists() else None

    candidates = [folders.base_folder, folders.build_folder, folders.dist, folders.destdir]
    for candidate in candidates:
        if candidate:
            candidate = runez.to_path(candidate) / path
            if candidate.exists():
                return candidate.absolute()


@runez.log.timeit
def recompress_folder(folders, path, extension):
    """Recompress folder"""
    dest = runez.SYS_INFO.platform_id.composed_basename("cpython", path.name, extension=extension)
    dest = folders.dist / dest
    runez.compress(path, dest, logger=print)
    return dest


@runez.log.timeit
def recompress_archive(folders, path, extension):
    stem = path.name.rpartition(".")[0]
    if stem.endswith(".tar"):
        stem = stem.rpartition(".")[0]

    dest = "%s.%s" % (stem, extension)
    dest = folders.dist / dest
    if dest == path:
        dest = "%s.%s" % (stem + "-recompressed", extension)
        dest = folders.dist / dest

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
    pspec = PythonSpec.to_spec(path)
    folders = PPG.get_folders(base=".", family=pspec and pspec.family, version=pspec and pspec.version)
    with runez.Anchored(folders.base_folder):
        actual_path = _find_recompress_source(folders, path)
        if not actual_path:
            runez.abort("'%s' does not exist" % runez.red(runez.short(path)))

        if actual_path.is_dir():
            dest = recompress_folder(folders, actual_path, extension)

        else:
            dest = recompress_archive(folders, actual_path, extension)

        print("Size of %s: %s" % (runez.short(actual_path), runez.bold(runez.represented_bytesize(actual_path))))
        print("Size of %s: %s" % (runez.short(dest), runez.bold(runez.represented_bytesize(dest))))


@main.command()
@click.option("--commit", is_flag=True, help="Effectively perform the changes")
@click.option("--prefix", "-p", metavar="PATH", help="--prefix the program was built with (default: same as scanned path)")
@click.argument("path", required=True)
def lib_auto_correct(commit, prefix, path):
    """
    Scan a python installation, auto-correct exes/libraries to use relative paths

    This is mostly for testing purposes, applies the same method done internally by this tool.
    Allows to exercise just the lib-auto-correct part without having to wait for full build to complete.
    """
    if not runez.DRYRUN:
        runez.log.set_dryrun(not commit)

    path = runez.resolved_path(path)
    if not prefix:
        python = PPG.find_python(path)
        runez.abort_if(python.problem)
        r = runez.run(python.executable, "-c", "import sysconfig; print(sysconfig.get_config_var('prefix'))", dryrun=False)
        prefix = runez.resolved_path(r.output)

    lib_auto_correct = LibAutoCorrect(prefix, runez.to_path(path))
    lib_auto_correct.run()


if __name__ == "__main__":
    from portable_python.cli import main  # noqa, re-import with proper package

    main()

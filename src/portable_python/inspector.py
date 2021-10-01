import collections
import enum
import json
import logging
import os
import re

import runez
from runez.render import PrettyTable

from portable_python.tracking import Trackable, Tracker
from portable_python.versions import PPG


LOG = logging.getLogger(__name__)
RX_DYNLIB = re.compile(r"^.*\.(so(\.[0-9.]+)?|dylib)$")


class LibType(enum.Enum):
    """Categorization for dynamic libs, value being the color we want to show them as"""

    base = ""
    lib_static = "static"
    libpython_so = "dynamic"
    missing = "red"
    other = "brown"
    system = "blue"


class TempChmod:
    """
    Temporarily chmod a given file.
    Some libs do not have the writable flag, and some do. We need them to writeable while we auto-correct them.
    """

    def __init__(self, path, chmod=0o755):
        self.path = path
        self.chmod = chmod
        self.old_chmod = None

    def __enter__(self):
        if not runez.DRYRUN:
            current = self.path.stat().st_mode & 0o777
            if current != self.chmod:
                self.old_chmod = current
                self.path.chmod(self.chmod)

        return self

    def __exit__(self, *_):
        if self.old_chmod is not None:
            self.path.chmod(self.old_chmod)


class LibAutoCorrect:
    """Automatically correct all absolute paths in exes/dynamic libs"""

    def __init__(self, prefix, install_folder):
        """
        Args:
            prefix (str): Prefix used in ./configure
            install_folder (pathlib.Path): Installation folder to scan (all paths will be relative to this)
        """
        self.prefix = prefix
        self.install_folder = install_folder
        self._file_corrector = getattr(self, "_auto_correct_%s" % PPG.target.platform)

    def run(self):
        self._scan(self.install_folder)

    def _scan(self, folder):
        for path in sorted(runez.ls_dir(folder)):
            if not path.is_symlink():
                if path.is_dir():
                    self._scan(path)

                elif is_dyn_lib(path) or runez.is_executable(path):
                    self._file_corrector(path)

    def _auto_correct_linux(self, path):
        """
        On linux, we change the /<prefix> rpath to be relative via $ORIGIN
        """
        r = runez.run("patchelf", "--print-rpath", path, fatal=False, dryrun=False, logger=False)
        if r.output and self.prefix in r.output:
            with TempChmod(path, chmod=0o755):
                relative_location = path.relative_to(self.install_folder).parent
                new_origin = os.path.relpath("lib", relative_location)
                runez.run("patchelf", "--set-rpath", f"$ORIGIN/{new_origin}", path)

    def _auto_correct_macos(self, path):
        """
        On macos, we use install_name_tool, example:
            install_name_tool -add_rpath @executable_path/../lib .../bin/python
            install_name_tool -change /<prefix>/lib/libpython3.9.dylib @rpath/libpython3.9.dylib .../bin/python

        Note that this is here is not necessary thanks to the '-Wl,-install_name,@executable_path/..' patch
        It is here just as fallback (double-checks that all exes/libs are indeed relative/portable)
        """
        prefixed_folder = path.relative_to(self.install_folder)
        prefixed_folder = runez.to_path(f"{self.prefix}/{prefixed_folder}").parent
        abs_paths = collections.defaultdict(list)
        r = runez.run("otool", "-L", path, dryrun=False, logger=None)
        if r.output:
            for line in r.output.splitlines():
                line = line.strip()
                if not line.endswith(":") and line.startswith(self.prefix):
                    ref_path = line.split()[0]
                    relative_path = os.path.relpath(ref_path, prefixed_folder)
                    if relative_path != path.name:
                        # See https://stackoverflow.com/questions/9690362/osx-dll-has-a-reference-to-itself
                        top_level = runez.joined(self._shared_ref_top_level(relative_path), delimiter=os.sep) or "."
                        abs_paths[top_level].append(ref_path)

        if abs_paths:
            with TempChmod(path, chmod=0o755):
                for top_level, ref_paths in abs_paths.items():
                    rpath = "@loader_path" if is_dyn_lib(path) else "@executable_path"
                    runez.run("install_name_tool", "-add_rpath", f"{rpath}/{top_level}", path)
                    for ref_path in ref_paths:
                        relative_to_scanned = os.path.join(prefixed_folder, top_level)
                        relative_path = os.path.relpath(ref_path, relative_to_scanned)
                        runez.run("install_name_tool", "-change", ref_path, f"@rpath/{relative_path}", path)

    @staticmethod
    def _shared_ref_top_level(relative_path):
        parts = runez.to_path(relative_path).parts
        if len(parts) > 1:
            parts = parts[:-1]  # Remove basename
            for part in parts:
                yield part
                if part != "..":
                    return


class ModuleInfo:

    _regex = re.compile(r"^(.*?)\s*(\S+/(lib(64)?/.*))$")

    def __init__(self, inspector: "PythonInspector", name: str, payload: dict):
        self.inspector = inspector
        self.name = name
        self.payload = payload
        self.filepath = runez.to_path(payload.get("path"))
        self.note = payload.get("note")
        self.version = payload.get("version")
        self.version_field = payload.get("version_field")

    def __repr__(self):
        return runez.short(self.filepath)

    @runez.cached_property
    def additional_info(self):
        path = self.filepath
        if path:
            if is_dyn_lib(path):
                info = SoInfo(self.inspector, path)
                return info

            if path.name.startswith("__init__."):
                path = path.parent

            return self.inspector.relative_path(path)

        return self.note

    def report_rows(self):
        version = self.version
        if version:
            version = str(version)
            if version == "built-in":
                version = runez.blue(version)

            elif version.startswith("*"):
                version = runez.orange(version)

            else:
                version = runez.bold(version)

        info = self.additional_info
        if hasattr(info, "represented"):
            info = info.represented()

        yield self.name, runez.joined(version, info)


class CLibInfo(Trackable):

    def __init__(self, inspector: "PythonInspector", path: str, version: str, basename: str):
        self.inspector = inspector
        if not basename:
            basename = os.path.basename(path)

        self.basename = basename
        self.tracked_category = get_lib_type(self.inspector.install_folder, path, basename)
        if self.tracked_category is LibType.missing:
            self.relative_path = basename

        else:
            self.relative_path = inspector.relative_path(path)

        if not version and not basename.startswith("libpython"):
            m = re.match(r"^.*?([\d.]+)[^\d]*$", basename)
            if m:
                version = m.group(1).strip(".")

        self.version = version
        self.filepath = runez.to_path(path)

    def __repr__(self):
        return self.short_name

    @runez.cached_property
    def short_name(self):
        if self.tracked_category is LibType.other:
            return self.relative_path

        short_name = self.basename
        if not short_name.startswith("libpython"):
            if short_name.startswith("lib"):
                short_name = short_name[3:]

            short_name = short_name.partition(".")[0]

        return short_name

    def represented(self, verbose=False):
        tc = self.tracked_category
        if verbose:
            yield runez.joined("[%s]" % runez.colored(tc.name, color=tc.value), self.relative_path, self.version, delimiter=" ")

        else:
            yield runez.colored(runez.joined(self.short_name, self.version, delimiter=":"), color=tc.value)


class SoInfo(Trackable):

    def __init__(self, inspector: "PythonInspector", path):
        self.inspector = inspector
        self.path = runez.to_path(path)
        self.relative_path = inspector.relative_path(self.path)
        self.extension = self.path.name.rpartition(".")[2]
        self.lib_tracker = Tracker(LibType, ".so")
        program, output = self._dot_so_listing(self.path)
        self.is_failed = "_failed" in self.path.name
        self.short_name = "%s*" % self.path.name.partition(".")[0]
        if self.is_failed:
            self.short_name += "_failed"  # pragma: no cover

        if program and output:
            func = getattr(self, "parse_%s" % program)
            func(output)

        else:
            self.is_failed = True
            self.short_name += "!"

        self.short_name += ".%s" % self.extension

    def __repr__(self):
        return self.short_name

    def __iter__(self):
        yield from self.lib_tracker.items

    @staticmethod
    def _dot_so_listing(path):
        for cmd in ("otool -L", "ldd"):
            cmd = runez.flattened(cmd, split=" ")
            program = cmd[0]
            if runez.which(program):
                r = runez.run(*cmd, path, fatal=False, logger=None)
                if not r.succeeded:
                    logging.warning("%s exited with code %s for %s: %s" % (program, r.exit_code, path, r.full_output))
                    return program, None

                return program, r.output

        return None, None

    @property
    def is_problematic(self):
        return self.is_failed or bool(self.lib_tracker.category[LibType.missing] or self.lib_tracker.category[LibType.other])

    @runez.cached_property
    def size(self):
        return self.path.stat().st_size if self.path.exists() else 0

    def parse_otool(self, output):
        first_line = None
        for line in output.splitlines():
            line = line.strip()
            if line:
                if first_line is None:
                    first_line = line.strip(":")

                else:
                    m = re.match(r"^(\S+).+current version ([0-9.]+).*$", line.strip())
                    if m:
                        path = m.group(1)
                        # See https://stackoverflow.com/questions/9690362/osx-dll-has-a-reference-to-itself
                        if not first_line.endswith(path):
                            version = m.group(2)
                            self.add_ref(path, version=version)

    def parse_ldd(self, output):
        for line in output.splitlines():
            line = line.strip()
            if line and line != "statically linked":
                if "=>" in line:
                    basename, _, path = line.partition("=")
                    basename = basename.strip()
                    path = path[1:].partition("(")[0].strip()

                else:
                    path, _, _ = line.partition(" ")
                    basename = None

                self.add_ref(path.strip(), basename=basename)

    def add_ref(self, path, version=None, basename=None):
        info = CLibInfo(self.inspector, path, version, basename)
        self.lib_tracker.add(info)

    def represented(self, verbose=None):
        report = []
        if verbose:
            path = self.inspector.relative_path(self.path)
            delimiter = "\n"

        else:
            path = self.short_name
            delimiter = " "

        types = [LibType.missing, LibType.libpython_so, LibType.other, LibType.system]
        if verbose:
            types.append(LibType.base)

        report.append(runez.green(path))
        for tp in types:
            c = self.lib_tracker.category[tp]
            if c.items:
                r = c.represented(verbose)
                if verbose:
                    r = "  %s" % runez.joined(r, delimiter="\n  ")

                elif tp is LibType.missing:
                    r = "%s: %s" % (runez.red("missing"), runez.joined(r, delimiter=delimiter))

                report.append(r)

        return runez.joined(report, delimiter=delimiter)


def is_dyn_lib(path):
    return RX_DYNLIB.match(path.name)


def find_libs(folder):
    for path in runez.ls_dir(folder):
        if is_dyn_lib(path) or path.name.endswith(".a"):
            yield path

        elif path.is_dir() and path.name.startswith(("config-", "lib-dynload", "python")):
            yield from find_libs(path)


def get_lib_type(install_folder, path, basename):
    if basename.startswith("libpython") and path.startswith(install_folder):
        return LibType.libpython_so

    if not path or path == "not found":
        return LibType.missing

    if PPG.target.is_base_lib(path, basename):
        return LibType.base

    if PPG.target.is_system_lib(path, basename):
        return LibType.system

    return LibType.other


class PythonInspector:

    default = "_bz2,_ctypes,_curses,_decimal,_dbm,_gdbm,_lzma,_tkinter,_sqlite3,_ssl,_uuid,pip,readline,pyexpat,setuptools,zlib"
    additional = "_asyncio,_functools,_tracemalloc,dbm.gnu,ensurepip,ossaudiodev,spwd,sys,tkinter,venv,wheel"

    def __init__(self, spec, modules=None):
        self.spec = spec
        self.modules = self.resolved_names(modules)
        self.module_names = runez.flattened(self.modules, split=",")
        self.python = PPG.find_python(self.spec)
        arg = self.resolved_names(self.modules)
        script = os.path.join(os.path.dirname(__file__), "external/_inspect.py")
        r = runez.run(self.python.executable, script, arg, fatal=False, logger=print if runez.DRYRUN else logging.debug)
        self.output = r.output if r.succeeded else "exit code: %s\n%s" % (r.exit_code, r.full_output)
        self.payload = None
        if self.output and self.output.startswith("{"):
            self.payload = json.loads(self.output)

        self.reported_prefix = self.payload and self.payload.get("prefix")
        self.srcdir = runez.to_path(self.payload and self.payload.get("srcdir"))
        self.lib_folder = _find_parent_subfolder(self.srcdir, "lib")
        self.install_folder = self.lib_folder and str(self.lib_folder.parent)

    def __repr__(self):
        return str(self.python)

    def resolved_names(self, names):
        if not names:
            return self.default

        if names == "all":
            return "%s,%s" % (self.default, self.additional)

        if names[0] == "+":
            names = "%s,%s" % (self.default, names[1:])

        return names

    @runez.cached_property
    def full_so_report(self):
        return FullSoReport(self)

    @runez.cached_property
    def module_info(self):
        if self.payload:
            return {k: ModuleInfo(self, k, v) for k, v in self.payload.get("report", {}).items()}

    def relative_path(self, path):
        with runez.Anchored(self.install_folder):
            p = runez.short(path, size=4096)
            m = re.match(r"^.*\.\.\./(.*)$", p)
            if m:
                p = m.group(1)

            return p

    def libpython_report(self, items):
        if not items:
            return runez.green("-not used-")

        rel_paths = [getattr(x, "relative_path", x) for x in items]
        full_paths = [runez.to_path(self.install_folder) / x for x in rel_paths]
        return runez.joined(PPG.config.represented_filesize(*full_paths), rel_paths)

    def represented(self, verbose=False):
        report = []
        if self.module_info:
            table = PrettyTable(2)
            table.header[0].align = "right"
            table.add_row("prefix", runez.short(self.reported_prefix, size=120))
            for v in self.module_info.values():
                table.add_rows(*v.report_rows())

            table.add_row("libpython*.a", self.libpython_report(self.full_so_report.lib_static))
            table.add_row("libpython*.so", self.libpython_report(self.full_so_report.libpython_so))
            table.add_row("install size", PPG.config.represented_filesize(self.install_folder))

            if runez.log.debug:
                table.add_row("install dir", runez.short(self.install_folder))
                table.add_row("lib", runez.short(self.lib_folder))
                table.add_row("srcdir", runez.short(self.srcdir))

            report.append(table)
            if verbose:
                report.append(self.full_so_report)
                if self.full_so_report.problematic:  # pragma: no cover (don't have a handy problematic python test case)
                    pb = self.full_so_report.problematic.represented(verbose=runez.log.debug)
                    report.append(runez.joined(pb, delimiter="\n"))
                    report.append("\n-- Library users:")
                    for what, users in self.full_so_report.lib_tracker.users.items():
                        color = what.tracked_category.value or "green"
                        overview = "%s %s: %s" % (runez.colored(what, color), runez.plural(users, "user"), runez.joined(users))
                        report.append(runez.short(overview))

                if runez.log.debug:
                    pb = self.full_so_report.ok.represented(verbose=True)
                    report.append(runez.joined(pb, delimiter="\n"))

        report = runez.joined(report or self.output, delimiter="\n")
        return runez.joined(report, delimiter="\n")


def _find_parent_subfolder(folder, basename):
    while folder and len(folder.parts) > 1:
        if folder.name == basename:
            return folder

        folder = folder.parent


class FullSoReport:

    def __init__(self, inspector: PythonInspector):
        self.inspector = inspector
        self.size = 0
        self.lib_tracker = Tracker(LibType)
        self.ok = Tracker(LibType, "OK")
        self.problematic = Tracker(LibType, "problematic")
        self.libpython_so = []
        self.lib_static = []
        for path in find_libs(self.inspector.lib_folder):
            if path.name.endswith(".a"):  # pragma: no cover
                self.lib_static.append(self.inspector.relative_path(path))
                continue

            info = SoInfo(inspector, path)
            if path.name.startswith("libpython"):  # pragma: no cover (would need to do a fully build with libpython.so...)
                self.libpython_so.append(info)

            self.lib_tracker.add(info)
            self.size += info.size
            target = self.problematic if info.is_problematic else self.ok
            target.add(info)

    def __repr__(self):
        return runez.joined(".so files: %s" % runez.represented_bytesize(self.size), self.problematic, self.ok, delimiter=", ")

    def get_problem(self, portable) -> str:
        if portable:
            uses_system = [x.relative_path for x in self.lib_tracker.category[LibType.system].items]
            if uses_system:
                allowed = PPG.config.get_value("allowed-system-libs")
                if allowed:
                    allowed = re.compile(allowed)
                    uses_system = [x for x in uses_system if not allowed.match(x)]

                if uses_system:
                    return "Uses system libs: %s" % runez.joined(uses_system)

        problem = runez.joined(self.problematic)
        if not problem and not runez.DRYRUN and not self.ok:
            problem = "Internal error: no OK libs found"

        return problem

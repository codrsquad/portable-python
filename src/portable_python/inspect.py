import enum
import json
import logging
import os
import platform
import re

import runez
from runez.render import PrettyTable

from portable_python.tracking import Trackable, Tracker
from portable_python.versions import PythonVersions


class TargetSystem:
    """Models target platform / architecture we're compiling for"""

    architecture: str = None
    platform: str = None
    sys_include = None  # Include dirs to search for telltale presence

    base_names: set = None  # Base system libraries that are considered OK to reference for a portable build
    rx_sys_lib = None
    rx_base_path = None

    def __init__(self, target=None):
        arch = plat = None
        if target:
            plat, _, arch = target.partition("-")

        self.architecture = arch or platform.machine()
        self.platform = plat or platform.system().lower()

        base_paths = ["@rpath/.+"]
        if self.is_linux:
            self.sys_include = ["/usr/include", f"/usr/include/{self.architecture}-{self.platform}-gnu"]
            self.base_names = {
                # Similar to https://github.com/pypa/auditwheel/blob/master/auditwheel/policy/manylinux-policy.json
                "libc.so.6", "libcrypt.so.1", "libdl.so.2", "libm.so.6", "libnsl.so.1", "libpthread.so.0", "librt.so.1", "libutil.so.1",
            }
            self.rx_sys_lib = re.compile(r"^(/usr)?/lib\d*/.+$")
            base_paths.append(r"linux-vdso\.so.*")  # Special linux virtual dynamic shared object
            base_paths.append(r"/lib\d*/ld-linux-.+")

        elif self.is_macos:
            self.sys_include = "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include"
            self.base_names = set()
            self.rx_sys_lib = re.compile(r"^/(usr/lib\d*|System/Library)/.+$")
            base_paths.append(r"/usr/lib/libSystem\.B\.dylib")

        self.rx_base_path = re.compile(r"^(%s)$" % runez.joined(base_paths, delimiter="|"))

    def __repr__(self):
        return "%s-%s" % (self.platform, self.architecture)

    def get_lib_type(self, install_folder, path, basename):
        if basename.startswith("libpython") and path.startswith(install_folder):
            return LibType.libpython

        if not path or path == "not found":
            return LibType.missing

        if self.rx_base_path.match(path) or basename in self.base_names:
            return LibType.base

        if self.rx_sys_lib.match(path):
            return LibType.system

        return LibType.other

    @property
    def is_linux(self):
        return self.platform == "linux"

    @property
    def is_macos(self):
        return self.platform == "darwin"


class LibType(enum.Enum):
    """Categorization for dynamic libs, value being the color we want to show them as"""

    base = ""
    libpython = "bold"
    missing = "red"
    other = "brown"
    system = "blue"


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
        return runez.short(self.filepath)  # pragma: no cover, for debugger

    @runez.cached_property
    def additional_info(self):
        path = self.filepath
        if path:
            if is_dyn_lib(path):
                info = SoInfo(self.inspector, path)
                return info

            if path.name.startswith("__init__."):
                path = path.parent

            path = self.inspector.relative_path(path)
            return runez.green(path)

        if self.note and "No module named" not in self.note:
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
        self.tracked_category = self.inspector.target.get_lib_type(self.inspector.install_folder, path, basename)
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

    def represented(self, verbose=None):
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
            self.short_name += "_failed"

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
        for line in output.splitlines():
            m = re.match(r"^(\S+).+current version ([0-9.]+).*$", line.strip())
            if m:
                self.add_ref(m.group(1), version=m.group(2))

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

        types = [LibType.missing, LibType.libpython, LibType.other, LibType.system]
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
    return path.name.endswith((".so", ".dylib"))


class PythonInspector:

    default = "_bz2,_ctypes,_curses,_dbm,_gdbm,_lzma,_tkinter,_sqlite3,_ssl,_uuid,pip,readline,setuptools,wheel,zlib"
    additional = "_asyncio,_functools,_tracemalloc,dbm.gnu,ensurepip,ossaudiodev,spwd,tkinter,venv"

    def __init__(self, spec, modules=None):
        self.spec = spec
        self.modules = self.resolved_names(modules)
        self.target = TargetSystem()
        self.module_names = runez.flattened(self.modules, split=",")
        self.python = PythonVersions.find_python(self.spec)
        arg = self.resolved_names(self.modules)
        script = os.path.join(os.path.dirname(__file__), "external/_inspect.py")
        r = runez.run(self.python.executable, script, arg, fatal=False, logger=print if runez.DRYRUN else logging.debug)
        self.output = r.output if r.succeeded else "exit code: %s\n%s" % (r.exit_code, r.full_output)
        self.payload = None
        if self.output and self.output.startswith("{"):
            self.payload = json.loads(self.output)

        self.srcdir = runez.to_path(self.payload and self.payload.get("srcdir"))
        self.lib_dynload = _find_parent_subfolder(self.srcdir, "lib-dynload")
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

    def find_so_files(self):
        for folder in (self.lib_folder, self.lib_dynload):
            for path in runez.ls_dir(folder):
                if is_dyn_lib(path):
                    yield path

    def relative_path(self, path):
        with runez.Anchored(self.install_folder):
            p = runez.short(path, size=4096)
            m = re.match(r"^.*\.\.\./(.*)$", p)
            if m:
                p = m.group(1)

            return p

    def represented(self, verbose=0):
        if self.python.problem:
            return "%s: %s" % (runez.blue(runez.short(self.python.executable)), runez.red(self.python.problem))

        report = []
        if self.module_info:
            table = PrettyTable(2)
            table.header[0].align = "right"
            for v in self.module_info.values():
                table.add_rows(*v.report_rows())

            if verbose > 1:
                table.add_row("install dir", runez.short(self.install_folder))
                table.add_row("lib", runez.short(self.lib_folder))
                table.add_row("lib-dynload", runez.short(self.lib_dynload))
                table.add_row("srcdir", runez.short(self.srcdir))

            lp = self.full_so_report.libpythons
            if lp:
                lp = runez.joined(x.relative_path for x in lp)

            table.add_row("libpython", lp or runez.green("-not used-"))
            report.append(table)
            report.append(self.full_so_report)
            if self.full_so_report.problematic:
                pb = self.full_so_report.problematic.represented(verbose)
                report.append(runez.joined(pb, delimiter="\n"))

        if verbose or self.full_so_report.problematic:
            report.append("\n-- Library users:")
            for what, users in self.full_so_report.lib_tracker.users.items():
                color = what.tracked_category.value or "green"
                overview = "%s %s: %s" % (runez.colored(what, color), runez.plural(users, "user"), runez.joined(users))
                report.append(runez.short(overview))

        if verbose > 1:
            pb = self.full_so_report.ok.represented(verbose)
            report.append(runez.joined(pb, delimiter="\n"))

        report = runez.joined(report, delimiter="\n") or self.output
        return runez.joined(runez.blue(self.python), report, delimiter=":\n")


def _find_parent_subfolder(folder, *base_names, max_up=3):
    if folder:
        if folder.name in base_names:
            return folder

        for basename in base_names:
            ld = folder / basename
            if ld.is_dir():
                return ld

        if max_up > 0:
            return _find_parent_subfolder(folder.parent, *base_names, max_up=max_up - 1)


class FullSoReport:

    def __init__(self, inspector: PythonInspector):
        self.inspector = inspector
        self.size = 0
        self.lib_tracker = Tracker(LibType)
        self.ok = Tracker(LibType, "OK")
        self.problematic = Tracker(LibType, "problematic")
        self.libpythons = []
        for path in inspector.find_so_files():
            info = SoInfo(inspector, path)
            if path.name.startswith("libpython"):
                self.libpythons.append(info)

            self.lib_tracker.add(info)
            self.size += info.size
            if info.is_problematic:
                self.problematic.add(info)

            else:
                self.ok.add(info)

    def __repr__(self):
        return runez.joined(".so files: %s" % runez.represented_bytesize(self.size), self.problematic, self.ok, delimiter=", ")

    @property
    def is_valid(self):
        c = self.lib_tracker.category[LibType.system]
        if self.inspector.target.is_linux and c:
            return False

        return self.ok and not self.problematic

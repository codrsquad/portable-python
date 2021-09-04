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


class SysLibInfo:
    """
    Base system libraries that are considered OK to reference for a portable build
    Similar to https://github.com/pypa/auditwheel/blob/master/auditwheel/policy/manylinux-policy.json
    """

    def __init__(self, target=None):
        self.target = target or TargetSystem()
        base_paths = ["@rpath/.+"]
        if self.target.is_linux:
            self.basenames = {"libc.so.6", "libcrypt.so.1", "libm.so.6", "libdl.so.2", "libpthread.so.0", "librt.so.1", "libnsl.so.1"}
            self.rx_syslib = re.compile(r"^(/usr)?/lib\d*/.+$")
            base_paths.append(r"linux-vdso\.so.*")  # Special linux virtual dynamic shared object
            base_paths.append(r"/lib\d*/ld-linux-.+")

        elif self.target.is_macos:
            self.basenames = {}
            self.rx_syslib = re.compile(r"^/(usr/lib\d*|System/Library)/.+$")
            base_paths.append(r"/usr/lib/libSystem\.B\.dylib")

        self.rx_base_path = re.compile(r"^(%s)$" % runez.joined(base_paths, delimiter="|"))

    def get_lib_type(self, path, basename):
        if not path or path == "not found":
            return LibType.missing

        if self.rx_base_path.match(path) or basename in self.basenames:
            return LibType.base

        if self.rx_syslib.match(path):
            return LibType.system

        return LibType.other


class LibType(enum.Enum):
    """Categorization for used .so-s, value being the color we want to show them as"""

    base = ""
    missing = "red"
    other = "brown"
    system = "blue"


class TargetSystem:
    """Models target platform / architecture we're compiling for"""

    def __init__(self, target=None):
        arch = plat = None
        if target:
            plat, _, arch = target.partition("-")

        self.architecture = arch or platform.machine()
        self.platform = plat or platform.system().lower()
        if self.is_macos:
            self.sys_include = "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include"

        else:
            self.sys_include = ["/usr/include", f"/usr/include/{self.architecture}-{self.platform}-gnu"]

    def __repr__(self):
        return "%s-%s" % (self.platform, self.architecture)

    @property
    def is_linux(self):
        return self.platform == "linux"

    @property
    def is_macos(self):
        return self.platform == "darwin"


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
            if path.name.endswith(".so"):
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
        self.relative_path = inspector.relative_path(path)
        if not basename:
            basename = os.path.basename(path)

        self.basename = basename
        self.tracked_category = self.inspector.sys_lib_info.get_lib_type(path, basename)
        if not version:
            m = re.match(r"^.*?([\d.]+)[^\d]*$", basename)
            if m:
                version = m.group(1).strip(".")

        self.version = version
        self.filepath = runez.to_path(path)

    def __str__(self):
        return runez.joined(self.short_name, self.version)  # pragma: no cover, for debugger

    @runez.cached_property
    def short_name(self):
        if self.tracked_category is LibType.other:
            return self.relative_path

        short_name = self.basename
        if short_name.startswith("lib"):
            short_name = short_name[3:]

        return short_name.partition(".")[0]

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
        self.lib_tracker = Tracker(LibType)
        program, output = self._dot_so_listing(self.path)
        self.is_failed = "_failed" in self.path.name
        self.short_name = self.path.name.partition(".")[0]
        if self.is_failed:
            self.short_name += "_failed"

        if program and output:
            func = getattr(self, "parse_%s" % program)
            func(output)

        else:
            self.is_failed = True
            self.short_name += "!"

    def __str__(self):
        return runez.joined(self.represented())

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

    def represented(self, verbose=False):
        report = []
        if verbose:
            path = self.inspector.relative_path(self.path, lib_dynload=False)
            delimiter = "\n"

        else:
            path = "%s*.so" % self.short_name
            delimiter = " "

        types = [LibType.missing, LibType.other, LibType.system]
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


class PythonInspector:

    default = "_bz2,_ctypes,_curses,_dbm,_gdbm,_lzma,_tkinter,_sqlite3,_ssl,_uuid,pip,readline,setuptools,wheel,zlib"
    additional = "_asyncio,_functools,_tracemalloc,dbm.gnu,ensurepip,ossaudiodev,spwd,tkinter,venv"

    def __init__(self, spec, modules=None, target=None):
        self.spec = spec
        self.modules = self.resolved_names(modules)
        self.sys_lib_info = SysLibInfo(target)
        self.module_names = runez.flattened(self.modules, split=",")
        self.python = PythonVersions.find_python(self.spec)

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
    def module_info(self):
        if self.payload:
            return {k: ModuleInfo(self, k, v) for k, v in self.payload.get("report", {}).items()}

    @runez.cached_property
    def output(self):
        arg = self.resolved_names(self.modules)
        script = os.path.join(os.path.dirname(__file__), "external/_inspect.py")
        r = runez.run(self.python.executable, script, arg, fatal=False, logger=print if runez.DRYRUN else logging.debug)
        return r.output if r.succeeded else "exit code: %s\n%s" % (r.exit_code, r.full_output)

    @runez.cached_property
    def payload(self):
        if self.output and self.output.startswith("{"):
            return json.loads(self.output)

    @runez.cached_property
    def srcdir(self):
        """'srcdir' as reported by inspected python's sysconfig"""
        if self.payload:
            return runez.to_path(self.payload.get("srcdir"))

    @runez.cached_property
    def lib_dynload(self):
        return _find_parent_subfolder(self.srcdir, "lib-dynload")

    @runez.cached_property
    def lib_folder(self):
        return _find_parent_subfolder(self.srcdir, "lib")

    @runez.cached_property
    def full_so_report(self):
        return FullSoReport(self)

    def relative_path(self, path, lib_dynload=True):
        with runez.Anchored(lib_dynload and self.lib_dynload, self.python.folder.parent):
            p = runez.short(path, size=4096)
            m = re.match(r"^.*\.\.\./(.*)$", p)
            if m:
                p = m.group(1)

            return p

    def represented(self, verbose=False):
        if self.python.problem:
            return "%s: %s" % (runez.blue(runez.short(self.python.executable)), runez.red(self.python.problem))

        report = []
        if verbose:
            # Temporary, inspecting remote and unusual lib/libpython.so
            folders = [self.lib_folder, self.lib_dynload]
            report.append("Scanning %s" % folders)
            for folder in folders:
                for path in runez.ls_dir(folder):
                    if path.name.endswith(".so"):
                        program, output = SoInfo._dot_so_listing(path)
                        if program and output:
                            report.append("Sample %s output on %s:" % (program, path))
                            report.append(output)
                            report.append("----")
                            if len(report) > 7:
                                break

        if self.module_info:
            table = PrettyTable(2)
            table.header[0].align = "right"
            table.add_row("srcdir", self.srcdir)
            table.add_row("lib", self.lib_folder)
            table.add_row("lib-dynload", self.lib_dynload)
            for v in self.module_info.values():
                table.add_rows(*v.report_rows())

            report.append(table)
            report.append(self.full_so_report)
            pb = self.full_so_report.problematic.represented(verbose)
            report.append(runez.joined(pb, delimiter="\n"))

        if verbose:
            pb = self.full_so_report.ok.represented(verbose)
            report.append(runez.joined(pb, delimiter="\n"))

        report = runez.joined(report, delimiter="\n") or self.output
        return runez.joined(runez.blue(self.python), report, delimiter=":\n")


def _find_parent_subfolder(folder, *basenames, max_up=3):
    if folder:
        if folder.name in basenames:
            return folder

        for basename in basenames:
            ld = folder / basename
            if ld.is_dir():
                return ld

        if max_up > 0:
            return _find_parent_subfolder(folder.parent, *basenames, max_up=max_up - 1)


class FullSoReport:

    def __init__(self, inspector: PythonInspector):
        self.inspector = inspector
        self.size = 0
        self.lib_tracker = Tracker(LibType, ".so")
        self.ok = Tracker(LibType, "OK")
        self.problematic = Tracker(LibType, "problematic")
        for path in runez.ls_dir(inspector.lib_dynload):
            if path.name.endswith(".so"):
                info = SoInfo(inspector, path)
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
        if self.inspector.sys_lib_info.target.is_linux and c:
            return False

        return self.ok and not self.problematic

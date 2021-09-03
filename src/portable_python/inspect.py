import json
import logging
import os
import platform
import re

import runez
from runez.render import PrettyTable

from portable_python.versions import PythonVersions


def _rcolor(text, color_on, color=None):
    """
    Args:
        text (str): Text to optionally color
        color_on (bool | callable | None): Color to use, or flag (de)activating coloring
        color (callable | None): Color to use if coloring is active

    Returns:
        (callable): Color function to use
    """
    if callable(color_on):
        color = color_on

    elif not color_on or color is None:
        color = str

    return color(text)


def _rep(items, color, indent, name):
    if items:
        if name.endswith(":"):
            yield _rcolor(name, color)

        elif indent:
            yield "%s%s:" % (indent, name)

        for item in sorted(items):
            x = "%s%s" % (indent or "", item.represented(color=color, indent=indent))
            yield x


class Representable:

    def __repr__(self):
        return self.represented(color=False)

    def represented(self, color=True, indent=None):
        """
        Args:
            color (callable | None):  Use colors if true-ish
            indent (str | None): Compact representation when None, non-compact otherwise

        Returns:
            (str): Textual representation
        """


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

    def is_base_lib(self, path, basename):
        """A base lib is OK to use by a portable program"""
        return self.rx_base_path.match(path) or basename in self.basenames

    def is_system_lib(self, path):
        """A system lib is NOT ok to use by a portable program"""
        return self.rx_syslib.match(path)


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
        self.filepath = payload.get("path")
        self.note = payload.get("note")
        self.version = payload.get("version")
        self.version_field = payload.get("version_field")

    @staticmethod
    def represented_version(version):
        if version:
            version = str(version)
            if version == "built-in":
                return runez.blue(version)

            if version.startswith("*"):
                return runez.orange(version)

            return runez.bold(version)

    @runez.cached_property
    def additional_info(self):
        if self.filepath:
            path = runez.to_path(self.filepath)
            if path.name.endswith(".so"):
                info = SoInfo(self.filepath, self.inspector.sys_lib_info)
                return info

            if path.name.startswith("__init__."):
                path = path.parent

            # 3.6 does not have Path.relative_to()
            pp = str(self.inspector.python.folder.parent)
            cp = str(path)
            if cp.startswith(pp):
                path = runez.to_path(cp[len(pp) + 1:])

            return runez.green(path)

        if self.note and "No module named" not in self.note:
            return self.note

    def report_rows(self):
        version = self.represented_version(self.version)
        info = self.additional_info
        if isinstance(info, SoInfo):
            info = info.represented()

        yield self.name, runez.joined(version, info, keep_empty=None)


class CLibInfo(Representable):

    def __init__(self, path, color, version, short_name=None):
        self.path = path
        self.color = color
        self.version = version
        self.short_name = short_name

    def __eq__(self, other):
        return isinstance(other, CLibInfo) and self.path == other.path and self.version == other.version

    def __hash__(self):
        return hash((self.path, self.version))

    def __lt__(self, other):
        if isinstance(other, CLibInfo):
            return (self.path, self.version) < (other.path, other.version)

    def represented(self, color=True, indent=None):
        if indent:
            r = "%s%s" % (indent, os.path.basename(self.path))

        else:
            r = self.short_name or self.path

        m = re.match(r"^.*\.\.\.\./(.*)$", r)
        if m:
            r = m.group(1)

        if self.version:
            r += ":%s" % self.version

        return _rcolor(r, color, self.color)


class SoInfo(Representable):

    def __init__(self, path, sys_lib_info=None):
        self.path = runez.to_path(path)
        self.sys_lib_info = sys_lib_info or SysLibInfo()
        self.is_failed = "_failed" in self.path.name
        self.base_libs = []
        self.system_libs = []
        self.other_libs = []
        self.missing_libs = []
        for cmd in ("otool -L", "ldd"):
            cmd = runez.flattened(cmd, split=" ")
            program = cmd[0]
            if runez.which(program):
                r = runez.run(*cmd, self.path, fatal=False, logger=None)
                if not r.succeeded:
                    logging.warning("%s exited with code %s for %s: %s" % (program, r.exit_code, path, r.full_output))
                    self.is_failed = True
                    break

                func = getattr(self, "parse_%s" % program)
                func(r.output)
                break

        self.short_name = runez.joined(os.path.basename(path).partition(".")[0], keep_empty=None)
        if self.is_failed:
            self.short_name += "_failed"

    def __eq__(self, other):
        return isinstance(other, SoInfo) and self.path == other.path

    def __lt__(self, other):
        return isinstance(other, SoInfo) and self.short_name < other.short_name

    def represented(self, color=True, indent=None):
        delimiter = "\n" if indent else " "
        name = "%s%s" % (indent, self.path.name) if indent else "%s*.so" % self.short_name
        name = _rcolor(name, color, self.is_failed and runez.red or runez.green)
        x = runez.joined(
            name,
            _rep(self.system_libs, color and runez.blue, indent, "system libs"),
            _rep(self.other_libs, color and runez.brown, indent, "other libs"),
            _rep(self.missing_libs, color and runez.red, indent, "missing:"),
            keep_empty=None,
            delimiter=delimiter,
        )
        return x

    @property
    def is_problematic(self):
        return self.is_failed or self.missing_libs or self.other_libs

    @runez.cached_property
    def size(self):
        path = runez.to_path(self.path)
        return path.stat().st_size if path.exists() else 0

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
        if not basename:
            basename = os.path.basename(path)

        if not version:
            m = re.match(r"^.*?([\d.]+)[^\d]*$", basename)
            if m:
                version = m.group(1).strip(".")

        short_name = basename
        if short_name.startswith("lib"):
            short_name = short_name[3:]

        short_name = short_name.partition(".")[0]
        if path == "not found":
            self.missing_libs.append(CLibInfo(basename, runez.red, version, short_name))
            return

        if self.sys_lib_info.is_base_lib(path, basename):
            self.base_libs.append(path)
            return

        if self.sys_lib_info.is_system_lib(path):
            self.system_libs.append(CLibInfo(path, runez.blue, version, short_name))
            return

        self.other_libs.append(CLibInfo(path, runez.brown, version))


class PythonInspector(Representable):

    default = "_bz2,_ctypes,_curses,_dbm,_gdbm,_lzma,_tkinter,_sqlite3,_ssl,_uuid,pip,readline,setuptools,wheel,zlib"
    additional = "_asyncio,_functools,_tracemalloc,dbm.gnu,ensurepip,ossaudiodev,spwd,tkinter,venv"

    def __init__(self, spec, modules=None, target=None):
        self.spec = spec
        self.modules = self.resolved_names(modules)
        self.sys_lib_info = SysLibInfo(target)
        self.module_names = runez.flattened(self.modules, keep_empty=None, split=",")
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
    def full_so_report(self):
        if self.payload:
            folder = runez.to_path(self.payload.get("so"))
            if folder and folder.exists():
                return FullSoReport(folder, self.sys_lib_info)

    def represented(self, color=True, indent=None):
        if self.python.problem:
            return "%s: %s" % (runez.blue(runez.short(self.python.executable)), runez.red(self.python.problem))

        table = None
        if self.module_info:
            table = PrettyTable(2)
            table.header[0].align = "right"
            for v in self.module_info.values():
                table.add_rows(*v.report_rows())

            table = [table, self.full_so_report.represented(color=color, indent=indent)]

        return runez.joined(runez.blue(self.python), table or self.output, keep_empty=None, delimiter=":\n")


class FullSoReport(Representable):

    def __init__(self, folder, sys_lib_info):
        self.folder = folder
        self.sys_lib_info = sys_lib_info
        self.ok = []
        self.problematic = []
        self.uses_sytem_lib = []
        self.size = 0
        self.system_libs = set()
        for path in runez.ls_dir(folder):
            if path.name.endswith(".so"):
                info = SoInfo(path, self.sys_lib_info)
                self.size += info.size
                self.system_libs.update(info.system_libs)
                if info.system_libs:
                    self.uses_sytem_lib.append(info)

                if info.is_problematic:
                    self.problematic.append(info)

                else:
                    self.ok.append(info)

    @property
    def is_valid(self):
        if self.sys_lib_info.target.is_linux and self.system_libs:
            return False

        return self.ok and not self.problematic

    def represented(self, color=True, indent=None, full=False):
        msg = runez.joined(
            ".so files: %s" % runez.represented_bytesize(self.size),
            "%s problematic" % len(self.problematic),
            "%s OK" % len(self.ok),
            delimiter=", "
        )
        msg = runez.joined(
            msg,
            _rep(self.problematic, color, None, "problematic lib"),
            indent is not None and _rep(self.uses_sytem_lib, color, indent, "using system lib"),
            keep_empty=None,
            delimiter="\n"
        )
        if indent:
            msg = runez.joined(msg, _rep(self.ok, color, indent, "OK lib"), delimiter="\n")

        return msg
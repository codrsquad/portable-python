"""
Designed to be used via portable-python CLI.
Can be used programmatically too, example usage:

    from portable_python import BuildSetup

    setup = BuildSetup("cpython:3.9.6")
    setup.compile()
"""

import contextlib
import json
import logging
import multiprocessing
import os
import platform
import re
from typing import Dict, List

import runez
from runez.http import RestClient
from runez.render import Header, PrettyTable

from portable_python.versions import PythonVersions


LOG = logging.getLogger(__name__)
REST_CLIENT = RestClient()


class BuildSetup:
    """
    This class drives the compilation, external modules first, then the target python itself.
    All modules are compiled in the same manner, follow the same conventional build layout.
    """

    # Optional extra settings (not taken as part of constructor)
    static = False

    # Internal, used to ensure files under build/.../logs/ sort alphabetically in the same order they were compiled
    log_counter = 0

    def __init__(self, python_spec, build_base="build", dist_folder="dist", modules=None, prefix=None, target=None):
        if not python_spec:
            python_spec = "cpython:%s" % PythonVersions.cpython.latest

        self.python_spec = PythonVersions.validated_spec(python_spec)
        self.build_base = runez.to_path(build_base, no_spaces=True).absolute()
        self.dist_folder = runez.to_path(dist_folder).absolute()
        self.desired_modules = modules
        self.prefix = prefix
        self.target_system = TargetSystem(target)
        self.build_folder = self.build_base / self.python_spec.canonical.replace(":", "-")
        self.deps_folder = self.build_folder / "deps"
        builder = PythonVersions.family(self.python_spec.family).builder
        self.python_builder = builder(self)

    def __repr__(self):
        return runez.short(self.build_folder)

    @runez.log.timeit("Overall compilation", color=runez.bold)
    def compile(self, x_debug=None):
        """Compile selected python family and version"""
        self.log_counter = 0
        with runez.Anchored(self.build_base.parent, self.dist_folder.parent):
            LOG.info("Modules selected: %s" % runez.joined(self.python_builder.modules.selected, delimiter=", "))
            runez.ensure_folder(self.build_folder, clean=not x_debug)
            self.python_builder.compile(x_debug)


class ModuleCollection:
    """Models a collection of sub-modules, with auto-detection and reporting as to what is active and why"""

    candidates: List["ModuleBuilder"] = None
    desired: str = None
    selected: List["ModuleBuilder"] = None
    reasons: Dict[str, str] = None

    def __init__(self, parent_module: "ModuleBuilder", desired=None):
        self.selected = []
        self.candidates = []
        self.desired = desired
        self.reasons = {}
        module_by_name = {}
        candidates = parent_module.candidate_modules()
        if candidates:
            for module in candidates:
                module = module(parent_module)
                self.candidates.append(module)
                module_by_name[module.m_name] = module
                should_use, reason = module.auto_use_with_reason()
                self.reasons[module.m_name] = reason
                if should_use:
                    self.selected.append(module)

        if not desired:
            return

        explicitly_disabled = runez.red("explicitly disabled")
        explicitly_requested = runez.blue("explicitly requested")
        if desired == "none":
            self.selected = []
            self.reasons = {k: explicitly_disabled for k in self.reasons}
            return

        if desired == "all":
            self.selected = self.candidates
            self.reasons = {k: explicitly_requested for k in self.reasons}
            return

        desired = runez.flattened(desired, keep_empty=None, split=",")
        unknown = [x for x in desired if x.strip("+-") not in self.reasons]
        if unknown:
            runez.abort("Unknown modules: %s" % runez.joined(unknown, delimiter=", ", stringify=runez.red))

        selected = []
        if "+" in self.desired or "-" in self.desired:
            selected = [x.m_name for x in self.selected]

        for name in desired:
            remove = name[0] == "-"
            if name[0] in "+-":
                name = name[1:]

            if remove:
                if name in selected:
                    self.reasons[name] = explicitly_disabled
                    selected.remove(name)

            elif name not in selected:
                self.reasons[name] = explicitly_requested
                selected.append(name)

        self.selected = [module_by_name[x] for x in selected]

    def __repr__(self):
        if not self.candidates:
            return "no sub-modules"

        if self.desired:
            return self.desired

        return "auto-detected: %s" % runez.plural(self.selected, "module")

    @staticmethod
    def get_module_name(module):
        if not isinstance(module, str):
            module = module.__name__.lower()

        return module

    def active_module(self, name):
        name = self.get_module_name(name)
        for module in self.selected:
            if name == module.m_name:
                return module

    def report(self):
        table = PrettyTable(2)
        # table.header[0].align = "right"
        rows = list(self.report_rows())
        table.add_rows(*rows)
        return str(table)

    def report_rows(self, indent=0):
        indent_str = " +%s " % ("-" * indent) if indent else ""
        for module in self.candidates:
            yield "%s%s" % (indent_str, module.m_name), module.version, self.reasons[module.m_name]
            yield from module.modules.report_rows(indent + 1)


class ModuleBuilder:
    """Common behavior for all external (typically C) modules to be compiled"""

    m_build_cwd: str = None  # Optional: relative (to unpacked source) folder where to run configure/make from

    setup: BuildSetup
    parent_module: "ModuleBuilder" = None
    _log_handler = None

    def __init__(self, parent_module):
        """
        Args:
            parent_module (BuildSetup | ModuleBuilder): Associated parent
        """
        self.m_name = ModuleCollection.get_module_name(self.__class__)
        desired = None
        if isinstance(parent_module, BuildSetup):
            self.setup = parent_module
            desired = parent_module.desired_modules

        else:
            self.setup = parent_module.setup
            self.parent_module = parent_module

        self.modules = ModuleCollection(self, desired=desired)
        self.set_default_xenv("ARCHFLAGS", ("-arch ", self.target.architecture))
        if self.target.is_macos:
            self.set_default_xenv("MACOSX_DEPLOYMENT_TARGET", default="10.14")

        self.m_src_build = self.setup.build_folder / "build" / self.m_name

    def __repr__(self):
        return "%s:%s" % (self.m_name, self.version)

    @classmethod
    def candidate_modules(cls) -> list:
        """All possible candidate external modules for this builder"""

    def auto_use_with_reason(self):
        """
        Returns:
            (bool, str): True/False: auto-select module, None: won't build on target system; str states reason why or why not
        """
        telltale = getattr(self, "m_telltale", runez.UNSET)
        if telltale is runez.UNSET:
            return True, runez.dim("sub-module of %s" % self.parent_module)

        if not telltale:
            return False, runez.blue("on demand")

        if telltale is True:
            return True, runez.green("always compiled")  # pragma: no cover, provisional

        path = self._find_telltale(telltale)
        if path:
            return False, "%s, %s" % (runez.orange("skipped"), runez.dim("has %s" % runez.short(path)))

        return True, "%s, no %s" % (runez.green("needed"), telltale)

    def _find_telltale(self, telltale):
        for tt in runez.flattened(telltale, keep_empty=None):
            for sys_include in runez.flattened(self.target.sys_include):
                path = tt.format(include=sys_include, arch=self.target.architecture, platform=self.target.platform)
                if os.path.exists(path):
                    return path

    def active_module(self, name):
        return self.modules.active_module(name)

    @property
    def target(self):
        """Shortcut to setup's target system"""
        return self.setup.target_system

    @property
    def url(self):
        """Url of source tarball, if any"""
        return ""

    @property
    def version(self):
        """Version to use"""
        if self.parent_module:
            return self.parent_module.version

    @property
    def deps(self):
        """Folder <build>/.../deps/, where all externals modules get installed"""
        return self.setup.deps_folder

    @property
    def deps_lib(self):
        return self.deps / "lib"

    def set_default_xenv(self, name, value=None, default=None):
        """Set xenv_ attribute, if not already defined by descendant"""
        field_name = "xenv_%s" % name
        if not hasattr(self, field_name):
            if value is None:
                value = os.environ.get(name, default)

            if value:
                setattr(self, field_name, value)

    def xenv_PATH(self):
        yield self.checked_deps_folder("bin")
        yield "/usr/bin"
        yield "/bin"

    def checked_deps_folder(self, path, prefix=""):
        path = self.deps / path
        if path.is_dir():
            return f"{prefix}{path}"

    def run(self, program, *args, fatal=True):
        return runez.run(program, *args, passthrough=self._log_handler or True, fatal=fatal)

    def run_configure(self, program, *args, prefix=None):
        """
        Calling ./configure is similar across all components.
        This allows to have descendants customize each part relatively elegantly
        """
        if prefix is None:
            prefix = self.deps

        if prefix:
            prefix = f"--prefix={prefix}"

        program = program.split()
        cmd = runez.flattened(*program, prefix, *args, keep_empty=None)
        return self.run(*cmd)

    def run_make(self, *args, program="make", cpu_count=None):
        cmd = program.split()
        if cpu_count is None:
            cpu_count = multiprocessing.cpu_count()

        if cpu_count:
            cmd.append("-j%s" % cpu_count)

        self.run(*cmd, *args)

    @contextlib.contextmanager
    def captured_logs(self):
        try:
            self.setup.log_counter += 1
            logs_path = self.setup.build_folder / "logs" / f"{self.setup.log_counter:02}-{self.m_name}.log"
            if not runez.DRYRUN:
                runez.touch(logs_path, logger=None)
                self._log_handler = logging.FileHandler(logs_path)
                self._log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
                self._log_handler.setLevel(logging.DEBUG)
                logging.root.addHandler(self._log_handler)

            yield

        finally:
            if self._log_handler:
                logging.root.removeHandler(self._log_handler)
                self._log_handler = None

    def compile(self, x_debug):
        """Effectively compile this external module"""
        for submodule in self.modules.selected:
            submodule.compile(x_debug)

        print(Header.aerated(str(self)))
        with self.captured_logs():
            if x_debug and self.m_src_build.is_dir():
                # For quicker iteration: debugging directly finalization
                self._finalize()
                return

            if self.url:
                # Modules without a url just drive sub-modules compilation typically
                path = self.setup.build_folder.parent / "downloads" / os.path.basename(self.url)
                if not path.exists():
                    REST_CLIENT.download(self.url, path)

                runez.decompress(path, self.m_src_build)

            for var_name in sorted(dir(self)):
                if var_name.startswith("xenv_"):
                    # By convention, inject all xenv_* values as env vars
                    value = getattr(self, var_name)
                    var_name = var_name[5:]
                    delimiter = os.pathsep if var_name.endswith("PATH") else " "
                    if value:
                        if callable(value):
                            value = value()  # Allow for generators

                        value = runez.joined(value, delimiter=delimiter, keep_empty=None)  # All yielded values are auto-joined
                        if value:
                            LOG.info("env %s=%s" % (var_name, runez.short(value, size=2048)))
                            os.environ[var_name] = value

            func = getattr(self, "_do_%s_compile" % self.target.platform, None)
            if not func:
                runez.abort("Compiling on platform '%s' is not yet supported" % runez.red(self.target.platform))

            with runez.log.timeit("Compiling %s" % self.m_name, color=runez.bold):
                folder = self.m_src_build
                if self.m_build_cwd:
                    folder = folder / self.m_build_cwd

                with runez.CurrentFolder(folder):
                    self._prepare()
                    func()
                    self._finalize()

    def _prepare(self):
        """Ran before _do_*_compile()"""

    def _do_darwin_compile(self):
        """Compile on macos variants"""
        return self._do_linux_compile()

    def _do_linux_compile(self):
        """Compile on linux variants"""

    def _finalize(self):
        """Ran after _do_*_compile()"""


class PythonBuilder(ModuleBuilder):

    @property
    def c_configure_prefix(self):
        if self.setup.prefix:
            return self.setup.prefix.format(python_version=self.version)

        return f"/{self.version.text}"

    @property
    def bin_folder(self):
        """Folder where compiled python exe resides"""
        return self.install_folder / "bin"

    @property
    def build_base(self):
        """Base folder where we'll compile python, with optional prefixed-layour (for debian-like packaging)"""
        folder = self.setup.build_folder
        if self.setup.prefix:
            folder = folder / "root"

        return folder

    @property
    def install_folder(self):
        """Folder where the python we compile gets installed"""
        return self.build_base / self.c_configure_prefix.strip("/")

    @property
    def tarball_path(self):
        dest = "%s-%s-%s.tar.gz" % (self.setup.python_spec.family, self.version, self.target)
        return self.setup.dist_folder / dest

    @property
    def version(self):
        return self.setup.python_spec.version

    def _prepare(self):
        # Some libs get funky permissions for some reason
        for path in runez.ls_dir(self.deps_lib):
            if not path.name.endswith(".la"):
                expected = 0o755 if path.is_dir() else 0o644
                current = path.stat().st_mode & 0o777
                if current != expected:
                    LOG.info("Corrected permissions for %s (was %s)" % (runez.short(path), oct(current)))
                    path.chmod(expected)


class ModuleInfo:

    _regex = re.compile(r"^(.*?)\s*(\S+/(lib(64)?/.*))$")

    def __init__(self, inspector, name, payload):
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

    @property
    def additional_info(self):
        if self.filepath:
            path = runez.to_path(self.filepath)
            if path.name.endswith(".so"):
                info = SoInfo(self.filepath)
                return info.report()

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
        yield self.name, runez.joined(version, info, keep_empty=None)


class SoInfo:

    _aliases = dict(ctypes="ffi,c.", curses="ncurses", readline="edit,curses,ncurses", tkinter="tcl,X11", zlib="z.")

    def __init__(self, path):
        self.path = path
        self.short_name = os.path.basename(path).partition(".")[0]
        self.top_levels = {}
        self.used_libs = []
        self.versions = {}
        self.notes = []
        otool = runez.run("otool", "-L", self.path, fatal=False, logger=None)
        ldd = runez.run("ldd", self.path, fatal=False, logger=None)
        self.extract_info(otool.output, ldd.output)

    def __repr__(self):
        return self.short_name

    def extract_info(self, otool, ldd):
        if otool:
            for line in otool.splitlines():
                line = line.strip()
                if line:
                    m = re.match(r"^(\S+).+current version ([0-9.]+).*$", line)
                    if m:
                        self.add_ref(m.group(1), m.group(2))

        elif ldd:
            for line in ldd.splitlines():
                line = line.strip()
                if line:
                    parts = line.split()
                    count = len(parts)
                    if count == 2:
                        path = parts[0]
                        if path.startswith("linux-vdso"):
                            continue

                    else:
                        path = parts[2]

                    if path == "not":
                        self.notes.append(runez.red(runez.joined(parts[:-1])))
                        continue

                    m = re.match(r"^.*?([\d.]+)[^\d]*$", os.path.basename(path))
                    version = m.group(1) if m else "?"
                    self.add_ref(path, version.strip("."))

    def report(self):
        result = [runez.green("%s*.so" % self.short_name)]
        if self.notes:
            result.extend(self.notes)

        for k in sorted(set(self.invalid_top_levels())):
            result.append(runez.red(k))

        return runez.joined(result)

    def invalid_top_levels(self):
        for k, v in self.top_levels.items():
            if v != "lib":
                m = re.match(r"^.*\.\.\.\./(.*)$", k)
                if m:
                    k = m.group(1)

                yield k

    def associated_name(self, basename):
        if basename.startswith("lib"):
            basename = basename[3:]

        pyname = self.short_name.strip("_")
        names = runez.flattened(pyname, self._aliases.get(pyname), keep_empty=None, split=",", unique=True)
        for name in names:
            if basename.startswith(name):
                return name.strip(".")

    def add_ref(self, path, version):
        basename = os.path.basename(path)
        associated = self.associated_name(basename)
        if associated:
            self.notes.append(runez.blue("%s:%s" % (associated, version)))

        self.used_libs.append(path)
        top_level = runez.to_path(path).parts[1:3]
        top_level = runez.joined(top_level, delimiter="/")
        if top_level.startswith(("lib", "System", "usr/lib")):
            top_level = "lib"

        self.top_levels[path] = top_level
        self.versions[path] = version


class PythonInspector:

    default = "_bz2,_ctypes,_curses,_dbm,_gdbm,_lzma,_tkinter,_sqlite3,_ssl,_uuid,pip,readline,setuptools,wheel,zlib"
    additional = "_asyncio,_functools,_tracemalloc,dbm.gnu,ensurepip,ossaudiodev,spwd,tkinter,venv"

    def __init__(self, spec, modules=None):
        self.spec = spec
        self.modules = self.resolved_names(modules)
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
            return {k: ModuleInfo(self, k, v) for k, v in self.payload.items()}

    @runez.cached_property
    def output(self):
        arg = self.resolved_names(self.modules)
        script = os.path.join(os.path.dirname(__file__), "_inspect.py")
        r = runez.run(self.python.executable, script, arg, fatal=False, logger=print if runez.DRYRUN else LOG.debug)
        return r.output if r.succeeded else "exit code: %s\n%s" % (r.exit_code, r.full_output)

    @runez.cached_property
    def payload(self):
        if self.output and self.output.startswith("{"):
            return json.loads(self.output)

    def report(self):
        if self.python.problem:
            return "%s: %s" % (runez.blue(runez.short(self.python.executable)), runez.red(self.python.problem))

        table = None
        if self.module_info:
            table = PrettyTable(2)
            table.header[0].align = "right"
            for v in self.module_info.values():
                table.add_rows(*v.report_rows())

        return runez.joined(runez.blue(self.python), table or self.output, keep_empty=None, delimiter=":\n")


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

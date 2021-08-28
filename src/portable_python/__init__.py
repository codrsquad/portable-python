import contextlib
import json
import logging
import os
import pathlib
import platform
import re

import runez
from runez.http import RestClient
from runez.pyenv import PythonDepot
from runez.render import Header, PrettyTable

from portable_python.versions import PythonVersions


LOG = logging.getLogger(__name__)
REST_CLIENT = RestClient()


class BuildSetup:
    """General build settings"""

    prefix = None
    static = True
    _log_counter = 0

    def __init__(self, python_spec, modules=None, build_folder="build", dist_folder="dist", target=None):
        self.python_spec = PythonVersions.validated_spec(python_spec)
        fam = PythonVersions.family(self.python_spec.family)
        if self.python_spec.version not in fam.versions:
            LOG.warning("%s is not in the supported list, your mileage may vary" % self.python_spec)

        self.target_system = TargetSystem(target)
        build_folder = runez.to_path(build_folder, no_spaces=True).absolute()
        self.build_folder = build_folder / str(self.python_spec).replace(":", "-")
        self.dist_folder = runez.to_path(dist_folder).absolute()
        self.deps_folder = self.build_folder / "deps"
        self.downloads_folder = build_folder / "downloads"
        self.logs_folder = self.build_folder / "logs"
        self.anchors = {build_folder.parent, self.dist_folder.parent}
        self.attached_modules_order = []
        self.attached_modules_map = {}
        builder = PythonVersions.get_builder(self.python_spec.family)
        self.python_builder = self.attach_module(builder)  # type: PythonBuilder
        desired = self.python_builder.get_modules(modules)
        self.active_modules = self.attach_modules(desired)

    def __repr__(self):
        return runez.short(self.build_folder)

    def attach_modules(self, modules, parent=None):
        result = []
        changed = 0
        for module in modules:
            if not isinstance(module, ModuleBuilder):
                changed += 1
                module = self.attach_module(module)  # type: ModuleBuilder
                if module.parent is not parent:
                    assert module.parent is None
                    module.parent = parent

            result.append(module)

        return result if changed else modules

    def attach_module(self, module):
        current = self.attached_modules_map.get(module.m_name)
        if not current:
            assert issubclass(module, ModuleBuilder)
            current = module()
            current.setup = self
            current.set_default_xenv("archflags", ("-arch ", self.target_system.architecture))
            if self.target_system.is_macos:
                current.set_default_xenv("macosx_deployment_target", default="10.14")

            self.attached_modules_order.append(current)
            self.attached_modules_map[current.m_name] = current
            current.m_src_build = self.build_folder / "build"
            if current.url:
                current.m_src_build = current.m_src_build / current.m_name

        return current

    def fix_lib_permissions(self):
        """Some libs get funky permissions for some reason"""
        for path in runez.ls_dir(self.deps_folder / "lib"):
            expected = 0o755 if path.is_dir() else 0o644
            current = path.stat().st_mode & 0o777
            if current != expected:
                LOG.info("Corrected permissions for %s" % runez.short(path))
                path.chmod(expected)

    def _get_logs_path(self, name):
        """Log file to use for a compilation, name is such that alphabetical sort conserves the order in which compilations occurred"""
        runez.ensure_folder(self.logs_folder, logger=None)
        self._log_counter += 1
        basename = f"{self._log_counter:02}-{name}.log"
        path = self.logs_folder / basename
        runez.delete(path, logger=None)
        return path

    def get_module(self, mod):
        for module in self.active_modules:
            if mod.m_name == module.m_name:
                return module

    @runez.log.timeit("Overall compilation", color=runez.bold)
    def compile(self, x_debug=None):
        with runez.Anchored(*self.anchors):
            runez.ensure_folder(self.build_folder, clean=not x_debug)
            count = runez.plural(self.active_modules, "external module")
            names = runez.joined(self.active_modules)
            LOG.debug("Compiling %s: %s" % (count, names))
            for m in self.active_modules:
                m.compile(x_debug)

            self.python_builder.compile(x_debug)


class ModuleBuilder:
    """Common behavior for all external (typically C) modules to be compiled"""

    parent: "ModuleBuilder" = None
    setup: BuildSetup = None
    depends_on = None  # type: list

    m_name: str = None  # Module name
    m_src_build: pathlib.Path = None  # Folder where this module's source code is unpacked and built
    m_telltale = None  # File(s) that tell us OS already has a usable equivalent of this module

    c_configure_cwd: str = None  # Optional: relative (to unpacked source) folder where to run configure/make from

    _log_handler = None

    def __repr__(self):
        return "%s:%s" % (self.m_name, self.version)

    @classmethod
    def auto_use_with_reason(cls, target: "TargetSystem"):
        if not cls.m_telltale:
            return False, runez.brown("only on demand (no auto-detection available)")

        for telltale in runez.flattened(cls.m_telltale, keep_empty=None):
            path = target.formatted_path(telltale)
            if os.path.exists(path):
                return False, "%s, %s" % (runez.orange("skipped"), runez.dim("has %s" % runez.short(path)))

        return True, "%s, no %s" % (runez.green("needed"), cls.m_telltale)

    @property
    def target(self):
        return self.setup.target_system

    @property
    def url(self):
        """Url of source tarball"""
        return ""

    @property
    def version(self):
        """Version to use"""
        if self.parent:
            return self.parent.version

    @property
    def deps(self):
        """Path where deps are installed"""
        return self.setup.deps_folder

    @property
    def download_path(self):
        """Path where source tarball for this module resides"""
        if self.url:
            return self.setup.downloads_folder / os.path.basename(self.url)

    def exported_env_vars(self):
        """Environment variables to set -> all generators of this object prefixed with 'xenv_'"""
        for name in sorted(dir(self)):
            if name.startswith("xenv_"):
                yield name

    def set_default_xenv(self, name, value=None, default=None):
        """Set xenv_ attribute, if not already defined by descendant"""
        k = "xenv_%s" % name.lower()
        if not hasattr(self, k):
            if value is None:
                value = os.environ.get(name.upper(), default)

            if value:
                setattr(self, k, value)

    def xenv_path(self):
        yield self.checked_deps_folder("bin")
        yield "/usr/bin"
        yield "/bin"

    def checked_deps_folder(self, path, prefix=""):
        path = self.deps / path
        if path.is_dir():
            return f"{prefix}{path}"

    def run(self, program, *args):
        return runez.run(program, *args, passthrough=self._log_handler or True)

    def run_configure(self, program, *args, prefix=None):
        """
        Calling ./configure is similar across all components.
        This allows to have descendants customize each part relatively elegantly
        """
        if prefix is None:
            prefix = self.deps

        if prefix:
            prefix = f"--prefix={prefix}"

        cmd = runez.flattened(program, prefix, *args, keep_empty=None, split=" ")
        return self.run(*cmd)

    @staticmethod
    def setenv(key, value):
        LOG.debug("env %s=%s" % (key, runez.short(value, size=2048)))
        os.environ[key] = value

    def _setup_env(self):
        for func_name in self.exported_env_vars():
            name = func_name[5:].upper()
            delimiter = os.pathsep if name.endswith("PATH") else " "
            value = getattr(self, func_name)
            if value:
                if callable(value):
                    value = value()

                value = runez.joined(value, delimiter=delimiter, keep_empty=None)
                if value:
                    self.setenv(name, value)

    @contextlib.contextmanager
    def captured_logs(self):
        try:
            logs_path = self.setup._get_logs_path(self.m_name)
            if not runez.DRYRUN:
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
        if not runez.DRYRUN and self.m_src_build.is_dir():
            if x_debug:
                # For quicker iteration: debugging directly finalization
                self._finalize()

            return

        print(Header.aerated(self))
        with self.captured_logs():
            if self.depends_on:
                self.depends_on = self.setup.attach_modules(self.depends_on, parent=self)
                for module in self.depends_on:
                    module.compile(x_debug)

            self.unpack()
            self._setup_env()
            self._prepare()
            func = getattr(self, "_do_%s_compile" % self.target.platform, None)
            if not func:
                runez.abort("Compiling on platform '%s' is not yet supported" % runez.red(self.target.platform))

            with runez.log.timeit("Compiling %s" % self.m_name, color=runez.bold):
                folder = self.m_src_build
                if self.c_configure_cwd:
                    folder = folder / self.c_configure_cwd

                with runez.CurrentFolder(folder):
                    func()
                    self._finalize()

    def _prepare(self):
        """Ran at the beginning of compile()"""

    def _finalize(self):
        """Called after (a possibly skipped) compile(), useful for --x-debug"""

    def download(self):
        if self.url:
            if self.download_path.exists():
                LOG.info("Already downloaded: %s" % self.url)

            else:
                REST_CLIENT.download(self.url, self.download_path)

    def unpack(self):
        if self.url:
            self.download()
            runez.decompress(self.download_path, self.m_src_build)

    def _do_darwin_compile(self):
        """Compile on macos variants"""
        return self._do_linux_compile()

    def _do_linux_compile(self):
        """Compile on linux variants"""


class PythonBuilder(ModuleBuilder):

    available_modules: list = None  # Available modules for this python family
    _available_module_names = None

    @classmethod
    def available_module_names(cls):
        if cls._available_module_names is None:
            cls._available_module_names = [m.m_name for m in cls.available_modules]

        return cls._available_module_names

    @classmethod
    def is_known_module_name(cls, module_name):
        return module_name in cls.available_module_names()

    def get_modules(self, module_names):
        if not module_names:
            return self._auto_detected_modules()

        if module_names == "none":
            return []

        if module_names == "all":
            return list(self.available_modules)

        selected = []
        unknown = []
        if "+" in module_names or "-" in module_names:
            selected = [x.m_name for x in self._auto_detected_modules()]

        for name in runez.flattened(module_names, keep_empty=None, split=","):
            remove = False
            if name[0] in "+-":
                remove = name[0] == "-"
                name = name[1:]

            if not self.is_known_module_name(name):
                unknown.append(name)

            elif remove:
                if name in selected:
                    selected.remove(name)

            elif name not in selected:
                selected.append(name)

        if unknown:
            runez.abort("Unknown modules: %s" % runez.joined(unknown, delimiter=", ", stringify=runez.red))

        # Ensure we yield same pre-determined order as returned by available_modules()
        result = []
        for mod in self.available_modules:
            if mod.m_name in selected:
                result.append(mod)

        return result

    def _auto_detected_modules(self):
        selected = []
        for mod in self.available_modules:
            should_use, _ = mod.auto_use_with_reason(self.target)
            if should_use:
                selected.append(mod)

        return selected

    @classmethod
    def get_scan_report(cls, target):
        reasons = {}  # type: dict[str, str] # Reason each module was selected by auto-detection
        for mod in cls.available_modules:
            reasons[mod.m_name] = mod.auto_use_with_reason(target)[1]

        return reasons

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


class PythonInspector:

    def __init__(self, specs, modules=None):
        self.inspector_path = os.path.join(os.path.dirname(__file__), "_inspect.py")
        self.specs = runez.flattened(specs, keep_empty=None, split=",")
        self.modules = modules
        self.depot = PythonDepot(use_path=False)
        self.reports = [self._spec_report(p) for p in self.specs]

    def report(self):
        return runez.joined(self.report_rows(), delimiter="\n")

    def report_rows(self):
        for r in self.reports:
            yield from r.report_rows()

    def _spec_report(self, spec):
        python = self.depot.find_python(spec)
        report = None
        if not python.problem:
            report = self._python_report(python.executable)

        return InspectionReport(spec, python, report)

    def _python_report(self, exe):
        r = runez.run(exe, self.inspector_path, self.modules, fatal=False, logger=print if runez.DRYRUN else LOG.debug)
        if not runez.DRYRUN:
            return r


class InspectionReport:

    def __init__(self, spec, python, report):
        self.spec = spec
        self.python = python
        self.report = report

    def __repr__(self):
        return str(self.python)

    @staticmethod
    def lib_version_via_otool(path):
        aliases = dict(ctypes="libffi", readline="curses,libedit", tkinter="tcl", zlib="libz")
        if path and os.path.exists(path):
            r = runez.run("otool", "-L", path, fatal=False, logger=None)
            if r.succeeded:
                m = re.match(r"^_?([^.]+).*$", os.path.basename(path))
                if m:
                    name = m.group(1).lower()
                    names = set(runez.flattened(name, aliases.get(name), keep_empty=None, split=","))
                    for line in r.output.splitlines():
                        m = re.match(r"^\s*(\S+).+current version ([0-9.]+).*$", line)
                        if m:
                            lb = m.group(1).lower()
                            if any(x in lb for x in names):
                                yield m.group(2)

    @staticmethod
    def lib_version(path):
        if path and path.endswith(".so"):
            v = runez.joined(InspectionReport.lib_version_via_otool(path), keep_empty=None)
            if v:
                return v

    @staticmethod
    def color(text):
        if text.startswith("*"):
            return runez.orange(text)

        if text == "built-in":
            return runez.blue(text)

        m = re.match(r"^(.*?)\s*(\S+/(lib(64)?/.*))$", text)
        if m:
            before = m.group(1)
            version = InspectionReport.lib_version(m.group(2))
            text = runez.green(m.group(3))
            if version:
                text = "%s %s" % (text, runez.blue(version))

            if before:
                v = re.sub(r"\w*version\w*=", "", before, flags=re.IGNORECASE)
                if v != before:
                    before = runez.bold(v)

                text = "%s %s" % (before, text)

        return text

    def report_rows(self):
        if self.python.problem:
            yield "%s: %s" % (runez.blue(runez.short(self.spec)), runez.red(self.python.problem))

        elif self.report is not None:
            yield "%s:" % runez.blue(self.python)
            if self.report.succeeded and self.report.output and self.report.output.startswith("{"):
                payload = json.loads(self.report.output)
                t = PrettyTable(2)
                t.header[0].align = "right"
                for k, v in sorted(payload.items()):
                    t.add_row(k, self.color(str(v or "*empty*")))

                yield t
                return

            report = []
            for k in ("exit_code", "output", "error"):
                v = getattr(self.report, k)
                if v:
                    report.append(("-- %s:" % k, str(v)))

            report = report[0][1] if len(report) == 1 else [runez.joined(x) for x in report]
            yield runez.joined(self.shortened_lines(report), delimiter="\n")

    @staticmethod
    def shortened_lines(text, size=2048):
        for item in runez.flattened(text):
            for line in item.splitlines():
                yield runez.short(line, size=size)


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
            self.sys_include = "/usr/include"

    def __repr__(self):
        return "%s-%s" % (self.platform, self.architecture)

    def formatted_path(self, path) -> str:
        return path.format(include=self.sys_include, arch=self.architecture, platform=self.platform)

    @property
    def is_linux(self):
        return self.platform == "linux"

    @property
    def is_macos(self):
        return self.platform == "darwin"

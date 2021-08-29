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
    """
    This class drives the compilation, external modules first, then the target python itself.
    All modules are compiled in the same manner, follow the same conventional build layout.
    """

    prefix = None
    static = True
    log_counter = 0

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
        self.anchors = {build_folder.parent, self.dist_folder.parent}
        self.attached_modules_order = []
        self.attached_modules_map = {}
        builder = PythonVersions.get_builder(self.python_spec.family)
        self.python_builder = self._attach_module(builder)  # type: PythonBuilder
        selected = self.python_builder.resolved_modules(modules)
        self.selected_modules = self.attach_modules(selected)

    def __repr__(self):
        return runez.short(self.build_folder)

    def active_module(self, name):
        """
        Args:
            name (type | str): Name to lookup

        Returns:
            (ModuleBuilder): Corresponding builder object, if selected for compilation
        """
        name = getattr(name, "m_name", name)
        for module in self.selected_modules:
            if name == module.m_name:
                return module

    def attach_modules(self, modules, parent=None):
        """Instances of 'modules' attached (if need be) to this setup object"""
        result = []
        for module in modules:
            if not isinstance(module, ModuleBuilder):
                module = self._attach_module(module)  # type: ModuleBuilder
                if module.parent is not parent:
                    assert module.parent is None
                    module.parent = parent

            assert module.setup is self
            result.append(module)

        return result

    @runez.log.timeit("Overall compilation", color=runez.bold)
    def compile(self, x_debug=None):
        """Compile selected python family and version"""
        with runez.Anchored(*self.anchors):
            runez.ensure_folder(self.build_folder, clean=not x_debug)
            count = runez.plural(self.selected_modules, "external module")
            names = runez.joined(self.selected_modules)
            LOG.debug("Compiling %s: %s" % (count, names))
            for m in self.selected_modules:
                m.compile(x_debug)

            self.python_builder.compile(x_debug)

    def _attach_module(self, module):
        current = self.attached_modules_map.get(module.m_name)
        if not current:
            assert issubclass(module, ModuleBuilder)
            current = module()
            current.setup = self
            current.set_default_xenv("ARCHFLAGS", ("-arch ", self.target_system.architecture))
            if self.target_system.is_macos:
                current.set_default_xenv("MACOSX_DEPLOYMENT_TARGET", default="10.14")

            self.attached_modules_order.append(current)
            self.attached_modules_map[current.m_name] = current
            current.m_src_build = self.build_folder / "build"
            if current.url:
                current.m_src_build = current.m_src_build / current.m_name

        return current


class ModuleBuilder:
    """Common behavior for all external (typically C) modules to be compiled"""

    m_name: str = None  # Module name as can be referenced from CLI, typically lowercase of class name
    m_telltale = None  # File(s) that tell us OS already has a usable equivalent of this module
    m_build_cwd: str = None  # Optional: relative (to unpacked source) folder where to run configure/make from

    parent: "ModuleBuilder" = None
    setup: BuildSetup = None
    m_src_build: pathlib.Path = None  # Folder where this module's source code is unpacked and built
    _log_handler = None

    def __repr__(self):
        return "%s:%s" % (self.m_name, self.version)

    @classmethod
    def auto_use_with_reason(cls, target):
        """
        Args:
            target (TargetSystem): Target system we're building for

        Returns:
            (bool, str): True/False: auto-select module, None: won't build on target system; str states reason why or why not
        """
        if not cls.m_telltale:
            return False, runez.brown("only on demand (no auto-detection available)")

        if cls.m_telltale is True:
            return True, runez.green("always compiled")

        for telltale in runez.flattened(cls.m_telltale, keep_empty=None):
            for sys_include in runez.flattened(target.sys_include):
                path = telltale.format(include=sys_include, arch=target.architecture, platform=target.platform)
                if os.path.exists(path):
                    return False, "%s, %s" % (runez.orange("skipped"), runez.dim("has %s" % runez.short(path)))

        return True, "%s, no %s" % (runez.green("needed"), cls.m_telltale)

    def required_submodules(self) -> list:
        """Optional dependent/required sub-modules to be compiled"""

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
        if self.parent:
            return self.parent.version

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

        cmd = runez.flattened(program, prefix, *args, keep_empty=None, split=" ")
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
        print(Header.aerated(str(self)))
        with self.captured_logs():
            submodules = self.required_submodules()
            if submodules:
                # Compile sub-modules first
                submodules = self.setup.attach_modules(submodules, parent=self)
                LOG.info("Required submodules: %s" % submodules)
                for module in submodules:
                    module.compile(x_debug)

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
                            LOG.debug("env %s=%s" % (var_name, runez.short(value, size=2048)))
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

    available_modules: list = None  # Available modules for this python family
    _available_module_names = None

    @classmethod
    def available_module_names(cls):
        if cls._available_module_names is None:
            cls._available_module_names = set(m.m_name for m in cls.available_modules)

        return cls._available_module_names

    @classmethod
    def is_known_module_name(cls, module_name):
        return module_name in cls.available_module_names()

    def resolved_modules(self, module_names):
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
            remove = name[0] == "-"
            if name[0] in "+-":
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

    def _prepare(self):
        # Some libs get funky permissions for some reason
        for path in runez.ls_dir(self.deps_lib):
            if not path.name.endswith(".la"):
                expected = 0o755 if path.is_dir() else 0o644
                current = path.stat().st_mode & 0o777
                if current != expected:
                    LOG.info("Corrected permissions for %s (was %s)" % (runez.short(path), oct(current)))
                    path.chmod(expected)


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
        """
        TODO: ldd foo.so
        linux-vdso.so.1 (0x00007ffdcfb89000)
        libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007fa621f48000)
        /lib64/ld-linux-x86-64.so.2 (0x00007fa622353000)
        """
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
            self.sys_include = ["/usr/include", f"/usr/include/{self.architecture}-{self.platform}-gnu"]

    def __repr__(self):
        return "%s-%s" % (self.platform, self.architecture)

    @property
    def is_linux(self):
        return self.platform == "linux"

    @property
    def is_macos(self):
        return self.platform == "darwin"

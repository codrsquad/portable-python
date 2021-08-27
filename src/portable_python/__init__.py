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
        self.python_builder = PythonVersions.get_builder(self.python_spec.family)()
        self.python_builder.attach(self)
        active, _ = self.python_builder.get_modules(self.target_system, module_names=modules)
        active = [x() for x in active]
        for x in active:
            x.attach(self)

        self.active_modules = active

    def __repr__(self):
        return runez.short(self.build_folder)

    def fix_lib_permissions(self, mode=0o644):
        """Some libs get funky permissions for some reason"""
        # for path in runez.ls_dir(self.deps_folder / "libs"):
        #     if path.name.endswith((".a", ".la")):
        #         current = path.stat().st_mode & 0o777
        #         if current != mode:
        #             path.chmod(mode)

    def _get_logs_path(self, name):
        """Log file to use for a compilation, name is such that alphabetical sort conserves the order in which compilations occurred"""
        runez.ensure_folder(self.logs_folder, logger=None)
        self._log_counter += 1
        basename = f"{self._log_counter:02}-{name}.log"
        path = self.logs_folder / basename
        runez.delete(path, logger=None)
        return path

    def get_module(self, name):
        for module in self.active_modules:
            if name == module.module_builder_name():
                return module

    def compile(self, x_debug=None):
        with runez.Anchored(*self.anchors):
            runez.ensure_folder(self.build_folder, clean=not x_debug)
            LOG.debug("Compiling %s" % runez.plural(self.active_modules, "external module"))
            for m in self.active_modules:
                m.compile(x_debug)

            self.python_builder.compile(x_debug)


class ModuleBuilder:
    """Common behavior for all external (typically C) modules to be compiled"""

    setup = None  # type: BuildSetup
    m_src_build: pathlib.Path = None  # Folder where this module's source code is unpacked and built

    c_configure_cwd: str = None  # Optional: relative (to unpacked source) folder where to run configure/make from
    c_configure_program = "./configure"
    telltale = None  # File(s) that tell us OS already has a usable equivalent of this module

    _log_handler = None

    def __repr__(self):
        return "%s %s" % (self.module_builder_name(), self.version)

    def attach(self, setup):
        self.setup = setup
        self.m_src_build = setup.build_folder / "build" / self.module_builder_name()

    @classmethod
    def module_builder_name(cls):
        return cls.__name__.lower()

    @classmethod
    def auto_use_with_reason(cls, target):
        if not cls.telltale:
            return False, runez.brown("only on demand (no auto-detection available)")

        for telltale in runez.flattened(cls.telltale, keep_empty=None):
            path = target.formatted_path(telltale)
            if os.path.exists(path):
                return False, "%s, %s" % (runez.orange("skipped"), runez.dim("has %s" % runez.short(path)))

        return True, "%s, no %s" % (runez.green("needed"), cls.telltale)

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
        return ""

    @property
    def deps(self):
        """Path where deps are installed"""
        return self.setup.deps_folder

    @property
    def download_path(self):
        """Path where source tarball for this module resides"""
        return self.setup.downloads_folder / os.path.basename(self.url)

    def exported_env_vars(self):
        """Environment variables to set -> all generators of this object prefixed with 'xenv_'"""
        for name in sorted(dir(self)):
            if name.startswith("xenv_"):
                yield name

    def xenv_archflags(self):
        """Help some components figure out architecture"""
        yield "-arch", self.target.architecture

    def xenv_macosx_deployment_target(self):
        if self.target.is_macos:
            yield "10.14"

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

    @property
    def c_configure_prefix(self):
        """--prefix to use for the ./configure program"""
        return self.deps

    def c_configure_args(self):
        """CLI args to pass to pass to ./configure"""
        yield f"--prefix={self.c_configure_prefix}"

    def run_configure(self):
        """
        Calling ./configure is similar across all components.
        This allows to have descendants customize each part relatively elegantly
        """
        if self.c_configure_program:
            args = runez.flattened(self.c_configure_program.split(), self.c_configure_args(), keep_empty=None)
            return self.run(*args)

    def run_make_install(self):
        self.run("make")
        self.run("make", "install")

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
            with runez.log.timeit("Compiling %s" % self.module_builder_name(), color=runez.bold):
                logs_path = self.setup._get_logs_path(self.module_builder_name())
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
        print(Header.aerated(self.module_builder_name()))
        with self.captured_logs():
            if not x_debug or not self.m_src_build.is_dir():
                # Build folder would exist only if we're doing an --x-debug run
                self.unpack()
                self._setup_env()
                self._prepare()
                func = getattr(self, "_do_%s_compile" % self.target.platform, None)
                if not func:
                    runez.abort("Compiling on platform '%s' is not yet supported" % runez.red(self.target.platform))

                func()

            self._finalize()

    def _prepare(self):
        """Ran at the beginning of compile()"""

    def _finalize(self):
        """Called after (a possibly skipped) compile(), useful for --x-debug"""
        self.setup.fix_lib_permissions()

    def download(self):
        if self.download_path.exists():
            LOG.info("Already downloaded: %s" % self.url)

        else:
            REST_CLIENT.download(self.url, self.download_path)

    def unpack(self):
        self.download()
        runez.decompress(self.download_path, self.m_src_build)

    def _do_darwin_compile(self):
        """Compile on macos variants"""
        return self._do_linux_compile()

    def _do_linux_compile(self):
        """Compile on linux variants"""
        folder = self.m_src_build
        if self.c_configure_cwd:
            folder = folder / self.c_configure_cwd

        with runez.CurrentFolder(folder):
            self.run_configure()
            self.run_make_install()


class PythonBuilder(ModuleBuilder):

    @classmethod
    def get_modules(cls, target, module_names=None):
        selected = []  # Module classes, either auto-detected or as stated/implied by 'module_names'
        reasons = {}  # type: dict[str, str] # Reason each module was selected, if auto-detected
        if module_names != "none":
            all_modules = cls.available_modules()
            all_modules = {m.module_builder_name(): m for m in all_modules}
            if module_names != "all":
                module_names = runez.flattened(module_names, keep_empty=None, split=",")
                for name in module_names:
                    if name not in all_modules:
                        runez.abort("Unknown module '%s'" % runez.red(name))

            for name, mod in all_modules.items():
                should_use, reason = mod.auto_use_with_reason(target)
                reasons[name] = reason
                if not module_names and should_use is None:  # pragma: no cover
                    LOG.info("Skipping %s: %s" % (name, reason))
                    continue

                if module_names == "all":
                    should_use = should_use is not None

                elif module_names:
                    should_use = name in module_names

                if should_use:
                    selected.append(mod)

        return selected, reasons

    @classmethod
    def available_modules(cls) -> list:
        """Available modules for this python family"""

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

    def run_make_install(self):
        self.run("make")
        self.run("make", "install", f"DESTDIR={self.build_base}")


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
            if r.report:
                if r.python.problem:
                    yield runez.short("%s: %s" % (runez.blue(r.spec), runez.red(r.python.problem)))

                else:
                    yield "%s:" % runez.blue(r.python)
                    yield r.represented() or ""

    def _spec_report(self, spec):
        python = self.depot.find_python(spec)
        report = dict(problem=python.problem) if python.problem else self._python_report(python.executable)
        return InspectionReport(spec, python, report)

    def _python_report(self, exe):
        r = runez.run(exe, self.inspector_path, self.modules, fatal=False, logger=print if runez.DRYRUN else LOG.debug)
        if not runez.DRYRUN:
            if r.succeeded and r.output and r.output.startswith("{"):
                return json.loads(r.output)

            return dict(exit_code=r.exit_code, error=r.error, output=r.output)


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

        else:
            text = runez.short(text)

        return text

    def represented(self):
        if self.report:
            t = PrettyTable(2)
            t.header[0].align = "right"
            for k, v in sorted(self.report.items()):
                t.add_row(k, self.color(v or "*empty*"))

            return "%s\n" % t


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

"""
Designed to be used via portable-python CLI.
Can be used programmatically too, example usage:

    from portable_python import BuildSetup

    setup = BuildSetup("cpython:3.9.6")
    setup.compile()
"""

import contextlib
import enum
import logging
import multiprocessing
import os
from typing import Dict, List

import runez
from runez.http import RestClient
from runez.pyenv import PythonSpec
from runez.render import Header, PrettyTable

from portable_python.config import Config
from portable_python.inspector import PythonInspector
from portable_python.versions import PythonVersions


LOG = logging.getLogger(__name__)
REST_CLIENT = RestClient()


class Cleanable(enum.Enum):

    bin = "clean bin/ folder, all files except bin/python and bin/pip"
    pip = "clean bin/pip*"
    libpython = "clean lib/*/libpython*"


CLEANABLE_CHOICES = runez.joined([x.name for x in Cleanable], delimiter=", ")


class BuildSetup:
    """
    This class drives the compilation, external modules first, then the target python itself.
    All modules are compiled in the same manner, follow the same conventional build layout.
    """

    # Optional extra settings (not taken as part of constructor)
    requested_clean = set()

    # Internal, used to ensure files under build/.../logs/ sort alphabetically in the same order they were compiled
    log_counter = 0

    def __init__(self, python_spec=None, config=None, modules=None, prefix=None):
        """
        Args:
            python_spec (str | PythonSpec | None): Python to build (family and version)
            config (str): Path to config to use
            modules (str | None): Modules to build (default: from config, or auto-detect)
            prefix (str | None): --prefix to use
        """
        if not python_spec or python_spec == "latest":
            python_spec = "cpython:%s" % PythonVersions.cpython.latest

        pspec = PythonSpec.to_spec(python_spec)
        if not pspec.version or not pspec.version.is_valid:
            runez.abort("Invalid python spec: %s" % runez.red(pspec))

        if pspec.version.text not in pspec.text or len(pspec.version.given_components) < 3:
            runez.abort("Please provide full desired version: %s is not good enough" % runez.red(pspec))

        self.python_spec = pspec
        self.config = Config(config)
        self.desired_modules = modules
        self.prefix = prefix
        self.build_folder = self.config.main_build_folder / self.python_spec.canonical.replace(":", "-")
        self.deps_folder = self.build_folder / "deps"
        self.x_debug = os.environ.get("PP_X_DEBUG")
        configured_ext = self.config.get_value("ext")
        ext = runez.SYS_INFO.platform_id.canonical_compress_extension(configured_ext, short_form=True)
        if not ext:
            runez.abort("Invalid extension '%s'" % runez.red(configured_ext))  # pragma: no cover

        dest = self.config.target.composed_basename(pspec.family, pspec.version, extension=ext)
        self.tarball_path = self.dist_folder / dest
        builder = PythonVersions.family(self.python_spec.family).get_builder()
        self.python_builder = builder(self)

    def __repr__(self):
        return runez.short(self.build_folder)

    @property
    def dist_folder(self):
        return self.config.dist_folder

    def set_requested_clean(self, text):
        self.requested_clean = set()
        for x in runez.flattened(text, split=","):
            v = getattr(Cleanable, x, None)
            if not v:
                help = {x.name: x.value for x in Cleanable}
                msg = ["  %s: %s" % (runez.green(k), v) for k, v in sorted(help.items())]
                msg = runez.joined("Pick one of:", msg, delimiter="\n")
                runez.abort("'%s' is not a valid value for --clean\n\n%s" % (runez.red(x), msg))

            self.requested_clean.add(v)

    @runez.log.timeit("Overall compilation")
    def compile(self):
        """Compile selected python family and version"""
        self.log_counter = 0
        with runez.Anchored(self.config.base_folder):
            modules = list(self.python_builder.modules)
            msg = "[%s]" % self.python_builder.modules
            if modules:
                msg += " -> %s" % runez.joined(modules, delimiter=", ")

            LOG.info("Modules selected: %s" % msg)
            LOG.info("Platform: %s" % self.config.target)
            runez.ensure_folder(self.build_folder, clean=not self.x_debug)
            self.python_builder.compile()
            if not runez.DRYRUN or self.python_builder.install_folder.is_dir():
                py_inspector = PythonInspector(self.python_builder.install_folder)
                print(py_inspector.represented())
                if not py_inspector.full_so_report.is_valid:
                    runez.abort("Build failed", fatal=not runez.DRYRUN)

            runez.compress(self.python_builder.install_folder, self.tarball_path)


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

        explicitly_disabled = runez.orange("explicitly disabled")
        explicitly_requested = runez.green("explicitly requested")
        if desired == "none":
            self.selected = []
            self.reasons = {k: explicitly_disabled for k in self.reasons}
            return

        if desired == "all":
            self.selected = self.candidates
            self.reasons = {k: explicitly_requested for k in self.reasons}
            return

        desired = runez.flattened(desired, split=",")
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

    def __iter__(self):
        for module in self.selected:
            yield from module.modules
            yield module

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
    m_debian = None
    m_include: str = None  # Optional: subfolder to automatically list in CPATH when this module is active

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
            msg = runez.blue("on demand")
            if self.target.is_linux and self.m_debian:
                msg += " (with debian %s)" % self.m_debian

            return False, msg

        telltale = runez.flattened(telltale)
        by_platform = []
        while telltale and telltale[0][0] in "-+":
            by_platform.append(telltale.pop(0))

        for pp in by_platform:
            if pp == "-%s" % self.target.platform:
                msg = runez.blue("on demand on %s" % self.target.platform)
                if self.target.is_linux and self.m_debian:
                    msg += " (with debian %s)" % self.m_debian

                return False, msg

            if pp == "+%s" % self.target.platform:
                return True, runez.green("mandatory on %s" % self.target.platform)

        path = self._find_telltale(telltale)
        telltale = runez.joined(telltale)
        if self.target.is_linux and self.m_debian:
            if path:
                return True, "%s (on top of %s, for static compile)" % (runez.green("needed on linux"), self.m_debian)

            return True, "%s for static compile" % runez.red("!needs %s" % self.m_debian)

        if path:
            return False, "%s, %s" % (runez.orange("skipped"), runez.dim("has %s" % runez.short(path)))

        return True, "%s, no %s" % (runez.green("needed"), telltale)

    def _find_telltale(self, telltales):
        for tt in telltales:
            for sys_include in runez.flattened(self.target.sys_include):
                path = tt.format(include=sys_include)
                if os.path.exists(path):
                    return path

    def active_module(self, name):
        return self.modules.active_module(name)

    @property
    def config(self):
        return self.setup.config

    @property
    def target(self):
        """Shortcut to setup's target system"""
        return self.config.target

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

    def xenv_ARCHFLAGS(self):
        yield "-arch ", self.target.arch

    def xenv_CPATH(self):
        if self.modules.selected:
            # By default, set CPATH only for modules that have sub-modules (descendants can override this easily)
            folder = self.deps / "include"
            yield folder
            for module in self.modules:
                if module.m_include:
                    yield folder / module.m_include

    def xenv_LDFLAGS(self):
        yield f"-L{self.deps_lib}"

    def xenv_PATH(self):
        yield f"{self.deps}/bin"
        yield "/usr/bin"
        yield "/bin"

    def xenv_PKG_CONFIG_PATH(self):
        yield f"{self.deps_lib}/pkgconfig"

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
        cmd = runez.flattened(*program, prefix, *args)
        return self.run(*cmd)

    def run_make(self, *args, program="make", cpu_count=None):
        cmd = program.split()
        if cpu_count is None:
            cpu_count = multiprocessing.cpu_count()

        if cpu_count and cpu_count > 2:
            cmd.append("-j%s" % (cpu_count // 2))

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

    def compile(self):
        """Effectively compile this external module"""
        for submodule in self.modules.selected:
            submodule.compile()

        print(Header.aerated(str(self)))
        with self.captured_logs():
            if self.setup.x_debug:
                if "direct-finalize" in self.setup.x_debug:
                    # For quicker iteration: debugging directly finalization
                    self._finalize()
                    return

            if self.url:
                # Modules without a url just drive sub-modules compilation typically
                # Split on '#' for urls that include a checksum, such as #sha256=... fragment
                basename = runez.basename(self.url, extension_marker="#")
                path = self.setup.build_folder.parent / "downloads" / basename
                if not path.exists():
                    REST_CLIENT.download(self.url, path)

                runez.decompress(path, self.m_src_build, simplify=True)

            env_vars = self._get_env_vars()
            for var_name, value in env_vars.items():
                LOG.info("env %s=%s" % (var_name, runez.short(value, size=2048)))
                os.environ[var_name] = value

            func = getattr(self, "_do_%s_compile" % self.target.platform, None)
            if not func:
                runez.abort("Compiling on platform '%s' is not yet supported" % runez.red(self.target.platform))

            with runez.log.timeit("Compiling %s" % self.m_name):
                folder = self.m_src_build
                if self.m_build_cwd:
                    folder = folder / self.m_build_cwd

                with runez.CurrentFolder(folder):
                    self._prepare()
                    func()
                    self._finalize()

    def _get_env_vars(self):
        """Yield all found env vars, first found wins"""
        result = {}
        for k, v in self._find_all_env_vars():
            if v is not None:
                if k not in result:
                    result[k] = v

        return result

    def _find_all_env_vars(self):
        """Env vars defined in code take precedence, the config can provide extra ones"""
        for var_name in sorted(dir(self)):
            if var_name.startswith("xenv_"):
                # By convention, xenv_* values are used as env vars
                value = getattr(self, var_name)
                var_name = var_name[5:]
                delimiter = os.pathsep if var_name.endswith("PATH") else " "
                if value:
                    if callable(value):
                        value = value()  # Allow for generators

                    value = runez.joined(value, delimiter=delimiter)  # All yielded values are auto-joined
                    if value:
                        yield var_name, value

        env = self.config.get_value("env")
        if env:
            for k, v in env.items():
                if v is not None:
                    yield k, str(v)

    def _prepare(self):
        """Ran before _do_*_compile()"""

    def _do_macos_compile(self):
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
    def build_root(self):
        """Base folder where we'll compile python, with optional prefixed-layout (for debian-like packaging)"""
        folder = self.setup.build_folder
        if self.setup.prefix:
            folder = folder / "root"

        return folder

    @property
    def install_folder(self):
        """Folder where the python we compile gets installed"""
        return self.build_root / self.c_configure_prefix.strip("/")

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

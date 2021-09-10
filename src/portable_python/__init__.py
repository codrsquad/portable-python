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
from typing import List

import runez
from runez.http import RestClient
from runez.pyenv import PythonSpec
from runez.render import Header, PrettyTable

from portable_python.inspector import PythonInspector
from portable_python.versions import PPG


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

    def __init__(self, python_spec=None, modules=None, prefix=None):
        """
        Args:
            python_spec (str | PythonSpec | None): Python to build (family and version)
            modules (str | None): Modules to build (default: from config)
            prefix (str | None): --prefix to use
        """
        if not python_spec or python_spec == "latest":
            python_spec = "cpython:%s" % PPG.cpython.latest

        python_spec = PythonSpec.to_spec(python_spec)
        if not python_spec.version or not python_spec.version.is_valid:
            runez.abort("Invalid python spec: %s" % runez.red(python_spec))

        if python_spec.version.text not in python_spec.text or len(python_spec.version.given_components) < 3:
            runez.abort("Please provide full desired version: %s is not good enough" % runez.red(python_spec))

        self.python_spec = python_spec
        self.desired_modules = modules
        self.prefix = prefix
        self.build_folder = PPG.config.main_build_folder / python_spec.canonical.replace(":", "-")
        self.deps_folder = self.build_folder / "deps"
        self.x_debug = os.environ.get("PP_X_DEBUG")
        configured_ext = PPG.config.get_value("ext")
        ext = runez.SYS_INFO.platform_id.canonical_compress_extension(configured_ext, short_form=True)
        if not ext:
            runez.abort("Invalid extension '%s'" % runez.red(configured_ext))  # pragma: no cover

        dest = PPG.target.composed_basename(python_spec.family, python_spec.version, extension=ext)
        self.tarball_path = PPG.config.dist_folder / dest
        builder = PPG.family(python_spec.family).get_builder()
        self.python_builder = builder(self)  # type: PythonBuilder

    def __repr__(self):
        return runez.short(self.build_folder)

    def set_requested_clean(self, text):
        self.requested_clean = set()
        for x in runez.flattened(text, split=","):
            v = getattr(Cleanable, x, None)
            if not v:
                hlp = {x.name: x.value for x in Cleanable}
                msg = ["  %s: %s" % (runez.green(k), v) for k, v in sorted(hlp.items())]
                msg = runez.joined("Pick one of:", msg, delimiter="\n")
                runez.abort("'%s' is not a valid value for --clean\n\n%s" % (runez.red(x), msg))

            self.requested_clean.add(v)

    def validate_module_selection(self, fatal=True):
        issues = []
        for module in self.python_builder.modules.selected:
            outcome, _ = module.linker_outcome(True)
            if outcome is LinkerOutcome.failed:
                issues.append(module)

        if issues:
            return runez.abort("Problematic modules: %s" % runez.joined(issues), fatal=fatal)

    @runez.log.timeit("Overall compilation")
    def compile(self):
        """Compile selected python family and version"""
        self.log_counter = 0
        with runez.Anchored(PPG.config.base_folder):
            self.validate_module_selection(fatal=not runez.DRYRUN)
            modules = self.python_builder.modules
            LOG.info(runez.joined(modules, list(modules)))
            LOG.info("Platform: %s" % PPG.target)
            runez.ensure_folder(self.build_folder, clean=not self.x_debug)
            self.python_builder.compile()
            if not runez.DRYRUN or self.python_builder.install_folder.is_dir():
                py_inspector = PythonInspector(self.python_builder.install_folder)
                print(py_inspector.represented())
                problem = py_inspector.full_so_report.problem
                if problem:
                    runez.abort("Build failed: %s" % problem, fatal=not runez.DRYRUN)

            runez.compress(self.python_builder.install_folder, self.tarball_path)


class ModuleCollection:
    """Models a collection of sub-modules, with auto-detection and reporting as to what is active and why"""

    candidates: List["ModuleBuilder"] = None
    desired: str = None
    selected: List["ModuleBuilder"] = None

    def __init__(self, parent_module: "ModuleBuilder", desired=None):
        self.selected = []
        self.candidates = []
        self.desired = desired
        module_by_name = {}
        candidates = parent_module.candidate_modules()
        if candidates:
            for module in candidates:
                module = module(parent_module)
                self.candidates.append(module)
                module_by_name[module.m_name] = module

        if not desired or desired == "none":
            return

        if desired == "all":
            self.selected = self.candidates
            return

        desired = runez.flattened(desired, split=True)
        desired = runez.flattened(desired, split=",")
        unknown = [x for x in desired if x not in module_by_name]
        if unknown:
            runez.abort("Unknown modules: %s" % runez.joined(unknown, delimiter=", ", stringify=runez.red))

        self.selected = [module_by_name[x] for x in desired]

    def __repr__(self):
        return "selected: %s (%s)" % (self.desired, runez.plural(self.selected, "module"))

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
        table = PrettyTable(4, missing="")
        rows = list(self.report_rows())
        table.add_rows(*rows)
        return str(table)

    def report_rows(self, indent=0):
        indent_str = " +%s " % ("-" * indent) if indent else ""
        for module in self.candidates:
            name = module.m_name
            is_selected = module in self.selected
            note = module.scan_note()
            outcome, problem = module.linker_outcome(is_selected)
            if isinstance(outcome, LinkerOutcome):
                outcome = runez.colored(outcome.name, outcome.value)

            elif outcome is runez.UNSET:
                outcome = None

            yield "%s%s" % (indent_str, name), module.version, outcome, problem or note
            yield from module.modules.report_rows(indent + 1)


class LinkerOutcome(enum.Enum):

    absent = "orange"
    failed = "red"
    shared = "blue"
    static = "green"


# noinspection PyPep8Naming
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
        if isinstance(parent_module, BuildSetup):
            self.setup = parent_module

        else:
            self.setup = parent_module.setup
            self.parent_module = parent_module

        self.modules = self.selected_modules()
        self.m_src_build = self.setup.build_folder / "build" / self.m_name
        self.resolved_telltale = self._find_telltale()

    def __repr__(self):
        return "%s:%s" % (self.m_name, self.version)

    @classmethod
    def candidate_modules(cls) -> list:
        """All possible candidate external modules for this builder"""

    def selected_modules(self):
        return ModuleCollection(self, desired="all")

    def linker_outcome(self, is_selected):
        if self.resolved_telltale is runez.UNSET:
            return runez.UNSET, None

        if self.resolved_telltale:
            outcome = LinkerOutcome.static if is_selected else LinkerOutcome.shared
            return outcome, None

        debian = self.m_debian
        if PPG.target.is_linux and debian:
            if debian.startswith("!"):
                return LinkerOutcome.failed, "%s, can't compile without %s" % (runez.red("broken"), debian[1:])

            if debian.startswith("+") and is_selected:
                return LinkerOutcome.failed, "%s, can't compile without %s" % (runez.red("broken"), debian[1:])

            return LinkerOutcome.absent, None

        outcome = LinkerOutcome.static if is_selected else LinkerOutcome.absent
        return outcome, None

    def scan_note(self):
        if self.resolved_telltale is runez.UNSET:
            return runez.dim("sub-module of %s" % self.parent_module)

        if self.resolved_telltale:
            return "has %s" % self.resolved_telltale

        return "no %s" % getattr(self, "m_telltale")

    def _find_telltale(self):
        telltales = getattr(self, "m_telltale", runez.UNSET)
        if telltales is runez.UNSET:
            return telltales

        for tt in runez.flattened(telltales):
            for sys_include in runez.flattened(PPG.target.sys_include):
                path = tt.format(include=sys_include)
                if os.path.exists(path):
                    return path

    def active_module(self, name):
        return self.modules.active_module(name)

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

    # noinspection PyMethodMayBeStatic
    def xenv_ARCHFLAGS(self):
        yield "-arch ", PPG.target.arch

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

            func = getattr(self, "_do_%s_compile" % PPG.target.platform, None)
            if not func:
                runez.abort("Compiling on platform '%s' is not yet supported" % runez.red(PPG.target.platform))

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

        env = PPG.config.get_value("env")
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

    def selected_modules(self):
        desired = self.setup.desired_modules or PPG.config.get_value("%s-modules" % self.m_name)
        return ModuleCollection(self, desired=desired)

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

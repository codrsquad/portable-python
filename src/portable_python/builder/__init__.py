import contextlib
import logging
import os
import pathlib
import time

import runez
from runez.http import RestClient
from runez.inspector import auto_import_siblings
from runez.pyenv import PythonSpec, Version
from runez.render import Header

from portable_python import LOG


REST_CLIENT = RestClient()


CPYTHON_VERSIONS = """
3.9.6
3.9.5
3.8.9
3.7.9
3.6.9
"""


class PythonVersions:
    """Known/supported versions for a given family (cpython, pypi, conda, ...) of pythons"""

    def __init__(self, family, versions):
        self.family = family
        self.versions = [Version(v) for v in versions.split()]

    def __repr__(self):
        return "%s [%s]" % (self.family, runez.plural(self.versions, "version"))

    @property
    def latest(self) -> Version:
        """Latest version for this family"""
        return self.versions[0]


class SupportedPythonVersions:
    """
    Supported python version - known to build correctly with this tool
    We don't try and support the entire history of releases, just a handful of latest non-EOL versions

    Cpython only for now, but could support more (pypi, conda?) in the future
    """

    def __init__(self):
        self.family_list = []
        self.family_by_name = {}
        self.cpython = self._add("cpython", CPYTHON_VERSIONS)

    def _add(self, family_name, versions):
        fam = PythonVersions(family_name, versions)
        self.family_list.append(fam)
        self.family_by_name[family_name] = fam
        return fam

    @property
    def all_family_names(self):
        return [x.family for x in self.family_list]

    def family(self, family_name, fatal=True) -> PythonVersions:
        fam = self.family_by_name.get(family_name)
        if fatal and not fam:
            runez.abort(f"Python family '{family_name}' is not yet supported")

        return fam

    def validate(self, python_spec: PythonSpec):
        if not python_spec.version or not python_spec.version.is_valid:
            runez.abort("Invalid python spec: %s" % runez.red(python_spec))

        fam = self.family(python_spec.family)
        if python_spec.version not in fam.versions:
            LOG.warning("%s is not in the supported list, your mileage may vary" % python_spec)


class AvailableBuilders:

    def __init__(self, category):
        self.category = category
        self.available = {}

    def __repr__(self):
        return runez.plural(self.available, "%s builder" % self.category)

    def declare(self, decorated):
        name = decorated.module_builder_name()
        self.available[name] = decorated
        return decorated

    def get_builder(self, name, setup=None):
        auto_import_siblings()
        v = self.available.get(name)
        if not v:
            runez.abort("Unknown module '%s'" % runez.red(name))

        if setup:
            v = v()
            v.attach(setup)

        return v


class TargetSystem:
    """Models target platform / architecture we're compiling for"""

    def __init__(self, target=None):
        import platform

        arch = plat = None
        if target:
            plat, _, arch = target.partition("-")

        self.architecture = arch or platform.machine()
        self.platform = plat or platform.system().lower()

    def __repr__(self):
        return "%s-%s" % (self.platform, self.architecture)

    @runez.cached_property
    def sdk_folder(self):
        if self.is_macos:
            return "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk"

    @runez.cached_property
    def sys_include(self):
        if self.sdk_folder:
            return f"{self.sdk_folder}/usr/include"

        return "/usr/include"

    @property
    def is_linux(self):
        return self.platform == "linux"

    @property
    def is_macos(self):
        return self.platform == "darwin"


class ModuleCollection:

    def __init__(self, target: TargetSystem, module_names=None):
        auto_import_siblings()
        self.target = target
        self.selected = []  # Module classes, either auto-detected or as stated/implied by 'module_names'
        self.reason = {}  # type: dict[str, str] # Reason each module was selected, if auto-detected
        if module_names == "none":
            self.selected = []

        elif module_names == "all":
            for name, mod in BuildSetup.module_builders.available.items():
                should_use, reason = mod.auto_use_with_reason(target)
                if should_use is not None:
                    self.selected.append(mod)

                else:  # pragma: no cover
                    LOG.info("Skipping %s: %s" % (name, reason))

        elif module_names:
            self.selected = runez.flattened(module_names, keep_empty=None, split=",", transform=BuildSetup.module_builders.get_builder)

        else:
            for mod in BuildSetup.module_builders.available.values():
                should_use, reason = mod.auto_use_with_reason(target)
                self.reason[mod.module_builder_name()] = reason
                if should_use:
                    self.selected.append(mod)

    def attached(self, setup):
        for mod in self.selected:
            should_use, reason = mod.auto_use_with_reason(setup.target_system)
            if should_use is None:  # pragma: no cover
                runez.abort("Can't build %s: %s" % (mod.module_builder_name(), reason))

            mod = mod()
            mod.attach(setup)
            yield mod


class BuildSetup:
    """General build settings"""

    module_builders = AvailableBuilders("external module")
    prefix = None
    python_builders = AvailableBuilders("python")
    static = True
    supported = SupportedPythonVersions()
    _log_counter = 0

    def __init__(self, python_spec, modules=None, build_folder="build", dist_folder="dist", target=None):
        python_spec = PythonSpec.to_spec(python_spec)
        self.supported.validate(python_spec)
        self.python_spec = python_spec
        self.target_system = TargetSystem(target)
        build_folder = runez.to_path(build_folder, no_spaces=True).absolute()
        self.build_folder = build_folder / str(self.python_spec).replace(":", "-")
        self.dist_folder = runez.to_path(dist_folder).absolute()
        self.deps_folder = self.build_folder / "deps"
        self.downloads_folder = build_folder / "downloads"
        self.logs_folder = self.build_folder / "logs"
        self.anchors = {build_folder.parent, self.dist_folder.parent}
        self.python_builder = self.python_builders.get_builder(self.python_spec.family, setup=self)
        self.modules = ModuleCollection(self.target_system, module_names=modules)
        self.active_modules = list(self.modules.attached(self))

    def __repr__(self):
        return runez.short(self.build_folder)

    @staticmethod
    def ls_dir(path):
        """A --dryrun friendly version of Path.iterdir"""
        if path.is_dir():
            yield from path.iterdir()

    def fix_lib_permissions(self, mode=0o644):
        """Some libs get funky permissions for some reason"""
        # for path in self.ls_dir(self.deps_folder / "libs"):
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

    setup: BuildSetup = None
    build_folder: pathlib.Path = None

    c_configure_cwd: str = None  # Optional: relative (to unpacked source) folder where to run configure/make from
    c_configure_program = "./configure"
    telltale = None  # File(s) that tell us OS already has a usable equivalent of this module

    _log_handler = None

    def __repr__(self):
        return "%s %s" % (self.module_builder_name(), self.version)

    def attach(self, setup):
        self.setup = setup
        self.build_folder = setup.build_folder / "build" / self.module_builder_name()

    @classmethod
    def module_builder_name(cls):
        return cls.__name__.lower()

    @classmethod
    def auto_use_with_reason(cls, target: TargetSystem):
        if not cls.telltale:
            return False, runez.brown("only on demand (no auto-detection available)")

        for telltale in runez.flattened(cls.telltale, keep_empty=None):
            path = telltale.format(include=target.sys_include)
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
        prefix = self.c_configure_prefix
        if prefix:
            yield "--prefix=/%s" % str(prefix).strip("/")

    def run_configure(self):
        """
        Calling ./configure is similar across all components.
        This allows to have descendants customize each part relatively elegantly
        """
        if self.c_configure_program:
            args = runez.flattened(self.c_configure_program.split(), self.c_configure_args(), keep_empty=None)
            return self.run(*args)

    def make_args(self):
        """Optional args to pass to make"""

    def make_install_args(self):
        """Optional args to pass to make install"""

    def run_make_install(self):
        if self.make_args:
            args = runez.flattened(self.make_args(), keep_empty=None)
            self.run("make", *args)

        if self.make_install_args:
            args = runez.flattened(self.make_install_args(), keep_empty=None)
            self.run("make", "install", *args)

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
        started = time.time()
        print(Header.aerated(self.module_builder_name()))
        with self.captured_logs():
            if not x_debug or not self.build_folder.is_dir():
                # Build folder would exist only if we're doing an --x-debug run
                self.unpack()
                self._setup_env()
                self._prepare()
                func = getattr(self, "_do_%s_compile" % self.target.platform, None)
                if not func:
                    runez.abort("Compiling on platform '%s' is not yet supported" % runez.red(self.target.platform))

                func()

            self._finalize()
            LOG.info("Compiled %s %s in %s" % (self.module_builder_name(), self.version, runez.represented_duration(time.time() - started)))

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
        runez.decompress(self.download_path, self.build_folder)

    def _do_darwin_compile(self):
        """Compile on macos variants"""
        return self._do_linux_compile()

    def _do_linux_compile(self):
        """Compile on linux variants"""
        folder = self.build_folder
        if self.c_configure_cwd:
            folder = folder / self.c_configure_cwd

        with runez.CurrentFolder(folder):
            self.run_configure()
            self.run_make_install()


class PythonBuilder(ModuleBuilder):

    def make_install_args(self):
        yield f"DESTDIR={self.install_destdir}"

    @property
    def c_configure_prefix(self):
        if self.setup.prefix:
            return self.setup.prefix.strip("/").format(python_version=self.version)

        return self.version.text

    @property
    def bin_folder(self):
        """Folder where compiled python exe resides"""
        return self.install_destdir / self.c_configure_prefix / "bin"

    @property
    def install_destdir(self):
        """Folder to use for make install DESTDIR="""
        folder = self.setup.build_folder
        if self.setup.prefix:
            folder = folder / "root"

        return folder

    @property
    def tarball_path(self):
        dest = "%s-%s-%s.tar.gz" % (self.setup.python_spec.family, self.version, self.target)
        return self.setup.dist_folder / dest

    @property
    def version(self):
        return self.setup.python_spec.version

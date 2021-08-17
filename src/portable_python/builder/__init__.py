import contextlib
import logging
import os
import pathlib
import platform
import time

import runez
from runez.http import RestClient
from runez.inspector import auto_import_siblings
from runez.pyenv import PythonSpec

from portable_python import LOG


REST_CLIENT = RestClient()


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

    def get_builder(self, setup, name):
        v = self.available.get(name)
        if v:
            v = v()
            v.attach(setup)
            return v


class BuildSetup:
    """General settings"""

    python_builders = AvailableBuilders("python")
    module_builders = AvailableBuilders("external module")
    _log_counter = 0

    def __init__(self, python_spec, prefix=None, modules=None, build_folder="build", dist_folder="dist"):
        self.python_spec = PythonSpec.to_spec(python_spec)
        if not self.python_spec.version or not self.python_spec.version.is_valid:
            runez.abort("Invalid python spec: %s" % runez.red(python_spec))

        self.prefix = prefix
        self.architecture = platform.machine()
        self.platform = platform.system().lower()
        build_folder = runez.to_path(build_folder, no_spaces=True).absolute()
        self.build_folder = build_folder / str(self.python_spec).replace(":", "-")
        self.dist_folder = runez.to_path(dist_folder).absolute()
        self.deps_folder = self.build_folder / "deps"
        self.downloads_folder = build_folder / "downloads"
        self.logs_folder = self.build_folder / "logs"
        self.anchors = {build_folder.parent, self.dist_folder.parent}
        auto_import_siblings()
        self.python_builder = self.python_builders.get_builder(self, self.python_spec.family)
        if not self.python_builder:
            runez.abort("No build implementation for %s" % runez.red(self.python_spec))

        modules = runez.flattened(modules or self.python_builder.default_modules(), keep_empty=None, split=",")
        if modules == ["none"]:
            modules = []

        elif modules == ["all"]:
            modules = list(self.module_builders.available.keys())

        # modules = [self.module_builders.get_builder(self, name) for name in modules]
        self.active_modules = []
        self.skipped_modules = []
        self.unknown_modules = []
        for name in modules:
            m = self.module_builders.get_builder(self, name)
            if not m:
                self.unknown_modules.append(name)
                continue

            skip_reason = m.skip_reason()
            if skip_reason:
                LOG.info("Skipping %s: %s" % (m, skip_reason))
                self.skipped_modules.append(m)

            else:
                self.active_modules.append(m)

    def __repr__(self):
        return runez.short(self.build_folder)

    @staticmethod
    def ls_dir(path):
        """A --dryrun friendly version of Path.iterdir"""
        if path.is_dir():
            yield from path.iterdir()

    @staticmethod
    def fix_lib_permissions(libs, mode=0o644):
        for path in BuildSetup.ls_dir(libs):
            if path.name.endswith((".a", ".la")):
                current = path.stat().st_mode & 0o777
                if current != mode:
                    path.chmod(mode)

    @property
    def is_linux(self):
        return self.platform == "linux"

    @property
    def is_macos(self):
        return self.platform == "darwin"

    def _get_logs_path(self, name):
        """Log file to use for a compilation, name is such that alphabetical sort conserves the order in which compilations occurred"""
        runez.ensure_folder(self.logs_folder, logger=None)
        self._log_counter += 1
        basename = f"{self._log_counter:02}-{name}.log"
        path = self.logs_folder / basename
        runez.delete(path, logger=None)
        return path

    def is_active_module(self, name):
        return any(name == x.module_builder_name() for x in self.active_modules)

    def compile(self, clean=True):
        with runez.Anchored(*self.anchors):
            runez.ensure_folder(self.build_folder, clean=clean)
            if self.unknown_modules:
                return runez.abort("Unknown modules: %s" % runez.joined(self.unknown_modules, delimiter=", ", stringify=runez.red))

            LOG.info("Compiling %s" % runez.plural(self.active_modules, "external module"))
            for m in self.active_modules:
                m.compile()

            self.python_builder.compile()
            self.python_builder.finalize()


class ModuleBuilder:
    """Common behavior for all external (typically C) modules to be compiled"""

    setup: BuildSetup = None
    build_folder: pathlib.Path = None

    needs_platforms: list = None
    needs_modules: list = None

    _log_handler = None

    def __repr__(self):
        return "%s %s" % (self.module_builder_name(), self.version)

    def attach(self, setup):
        self.setup = setup
        self.build_folder = setup.build_folder / "build" / self.module_builder_name()

    @classmethod
    def module_builder_name(cls):
        return cls.__name__.lower()

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

    def skip_reason(self):
        """Reason we're skipping compilation of this module, if any"""
        if self.needs_platforms and self.setup.platform not in self.needs_platforms:
            return "%s only" % runez.joined(self.needs_platforms, delimiter="/")

        if self.needs_modules:
            for m in self.needs_modules:
                if not self.setup.is_active_module(m):
                    return "needs %s" % m

    # def common_flags(self):
    #     if self.setup.is_macos:
    #         yield "-arch"
    #         yield self.setup.architecture
    #         yield "-mmacosx-version-min=10.14"
    #         yield "-isysroot"
    #         yield "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk"

    def xenv_cflags(self):
        # yield from self.common_flags()
        yield "-fPIC"
        yield self.checked_folder(self.deps / "include", prefix="-I")

    def xenv_cppflags(self):
        if self.xenv_cflags:
            yield from self.xenv_cflags()

    def xenv_ldflags(self):
        # yield from self.common_flags()
        yield self.checked_folder(self.deps / "lib", prefix="-L")

    def xenv_macosx_deployment_target(self):
        if self.setup.is_macos:
            yield "10.14"

    def xenv_pkg_config_path(self):
        yield self.checked_folder(self.deps / "share/pkgconfig")
        yield self.checked_folder(self.deps / "lib/pkgconfig")

    def xenv_path(self):
        yield self.checked_folder(self.deps / "bin")
        yield "/usr/bin"
        yield "/bin"

    @staticmethod
    def checked_folder(path, prefix=""):
        if path.is_dir():
            return f"{prefix}{path}"

    def run(self, program, *args):
        res = runez.run(program, *args, passthrough=True, fatal=False)
        if self._log_handler:
            msg = "output:\n%s\n-- stderr: --\n%s\n--------"
            record = logging.LogRecord(__name__, logging.INFO, "", 0, msg, (res.output, res.error), None)
            self._log_handler.emit(record)

        if res.exit_code:
            runez.abort("%s failed: %s exited with code %s" % (self, program, res.exit_code))

        return res

    def setenv(self, key, value):
        LOG.info("%s=%s" % (key, runez.short(value, size=2048)))
        os.environ[key] = value

    def setup_env(self):
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
            if logs_path.parent.is_dir():
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
        if self.build_folder.is_dir():  # Compile only when folder isn't there (it's never there, unless --x-finalize)
            LOG.info("Skipping compilation of %s: build folder already there" % self)
            return

        started = time.time()
        with self.captured_logs():
            self.unpack()
            with runez.CurrentFolder(self.build_folder):
                self.setup_env()
                func = getattr(self, "_do_%s_compile" % self.setup.platform, None)
                if not func:
                    runez.abort("Compiling on platform '%s' is not yet supported" % runez.red(self.setup.platform))

                func()

            BuildSetup.fix_lib_permissions(self.deps / "libs")
            LOG.info("Compiled %s %s in %s" % (self.module_builder_name(), self.version, runez.represented_duration(time.time() - started)))

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

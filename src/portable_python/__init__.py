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
import re
from typing import List

import runez
from runez.http import RestClient
from runez.pyenv import PythonSpec, Version
from runez.render import Header, PrettyTable

from portable_python.versions import PPG


LOG = logging.getLogger(__name__)
REST_CLIENT = RestClient()
RX_BINARY = re.compile(r"^.*\.(dylib|gmo|icns|ico|nib|prof.*|tar)$")


def is_binary_file(path):
    return RX_BINARY.match(path.name)


def patch_folder(folder, regex, replacement, ignore=None):
    """Replace all occurrences of 'old_text' by 'new_text' in all files in 'folder'

    Args:
        folder (pathlib.Path): Folder to scan
        regex: Regex to replace
        replacement (str): Replacement text
        ignore: Regex stating what to ignore
    """
    for path in runez.ls_dir(folder):
        if not path.is_symlink() and (not ignore or not ignore.match(path.name)):
            if path.is_dir():
                patch_folder(path, regex, replacement, ignore=ignore)

            elif not is_binary_file(path):
                patch_file(path, regex, replacement)


def patch_file(path, regex, replacement):
    try:
        with open(path, "rt") as fh:
            text = fh.read()

        new_text = re.sub(regex, replacement, text, flags=re.MULTILINE)
        if text != new_text:
            with open(path, "wt") as fh:
                fh.write(new_text)

            LOG.info("Patched '%s' in %s" % (regex, runez.short(path)))

    except Exception as e:
        with open(path, "rt", errors="ignore") as fh:
            text = fh.read()
            if re.search(regex, text):
                LOG.warning("Can't patch '%s': %s" % (runez.short(path), e))


class FolderMask:
    """
    Unfortunately, python source ./configure and setup.py looks at /usr/local/... we DON'T want that for a portable build
    as that implies machine where our binary would run must also have the /usr/local/... stuff
    TODO: find a less hacky way of doing this, or contribute an upstream option to stop looking at /usr/local/

    On macos, we temporarily mask /usr/local with an empty RAM disk mount...
    This is unfortunately global, and will temporarily mask /usr/local for other workers on the same macos box as well
    """

    def __init__(self, target_folder):
        LOG.info("Applying isolation hack/mask to %s" % target_folder)
        self.target_folder = target_folder
        r = runez.run("hdiutil", "attach", "-nomount", "ram://2048", fatal=Exception)
        self.ram_disk = r.output.strip()
        self.mounted = False

    def mount(self):
        runez.run("newfs_hfs", "-v", "tmp-portable-python", self.ram_disk, fatal=Exception)
        runez.run("mount", "-r", "-t", "hfs", "-o", "nobrowse", self.ram_disk, self.target_folder, fatal=Exception)
        self.mounted = True

    def cleanup(self):
        LOG.info("Cleaning up isolation hack/mask for %s" % self.target_folder)
        if self.mounted:
            runez.run("umount", self.target_folder, fatal=False)

        runez.run("hdiutil", "detach", self.ram_disk, fatal=False)


class BuildContext:
    """
    Context for BuildSetup.compile()
    """

    def __init__(self, setup):
        self.setup = setup
        self.masked_folders = []
        self.has_libintl = os.path.exists("/usr/local/include/libintl.h") or setup.x_debug == "has-libintl"
        v = PPG.config.get_value("isolate-usr-local")
        runez.abort_if(v and v not in ("mount-shadow", "gettext-tiny"), f"Invalid isolation method '{v}'")
        self.isolate_usr_local = v

    def __enter__(self):
        runez.Anchored.add(self.setup.folders.base_folder)
        if self.isolate_usr_local == "mount-shadow":
            # Fail early if this is attempted on linux (where there should be no need for this, with a good docker image)
            runez.abort_if(not PPG.target.is_macos, "/usr/local isolation implemented only for macos currently")

            # Safeguard against accidental isolation hack in non-dryrun test
            runez.abort_if(not runez.DRYRUN and runez.DEV.current_test(), "Folder masking not allowed in tests")

            try:
                for path in ("/usr/local/etc", "/usr/local/include", "/usr/local/lib", "/usr/local/opt"):
                    mask = FolderMask(path)
                    self.masked_folders.append(mask)
                    mask.mount()

            except BaseException:  # pragma: no cover, ensure cleanup if any folder couldn't be masked
                self.cleanup()
                raise

        return self

    def compile(self):
        if self.isolate_usr_local == "gettext-tiny":
            # Provide a dummy libintl.h, this isn't perfect but takes out the main culprit: sneaky libintl
            from portable_python.external import Toolchain

            toolchain = Toolchain(self.setup)
            toolchain.compile()

    def cleanup(self):
        for mask in self.masked_folders:
            mask.cleanup()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        runez.Anchored.pop(self.setup.folders.base_folder)


class BuildSetup:
    """
    This class drives the compilation, external modules first, then the target python itself.
    All modules are compiled in the same manner, follow the same conventional build layout.
    """

    # Internal, used to ensure files under {logs}/ folder sort alphabetically in the same order they were compiled
    log_counter = 0

    def __init__(self, python_spec=None, modules=None, prefix=None):
        """
        Args:
            python_spec (str | PythonSpec | None): Python to build (family and version)
            modules (str | None): Modules to build (default: from config)
            prefix (str | None): --prefix to use
        """
        if isinstance(python_spec, str):
            v = Version.from_text(python_spec)
            if v and not v.is_final:
                # Accept release candidates
                family = python_spec.rpartition(":")[0] or "cpython"
                python_spec = PythonSpec.to_spec(f"{family}:{v.main}")
                python_spec.version = v

        if not python_spec or python_spec == "latest":
            python_spec = "cpython:%s" % PPG.cpython.latest

        python_spec = PythonSpec.to_spec(python_spec)
        if not python_spec.version or not python_spec.version.is_valid:
            runez.abort("Invalid python spec: %s" % runez.red(python_spec))

        if len(python_spec.version.given_components) < 3:
            runez.abort("Please provide full desired version: %s is not good enough" % runez.red(python_spec))

        self.python_spec = python_spec
        self.folders = PPG.get_folders(base=os.getcwd(), family=python_spec.family, version=python_spec.version)
        self.desired_modules = modules
        prefix = self.folders.formatted(prefix)
        self.prefix = prefix
        self.x_debug = os.environ.get("PP_X_DEBUG")
        configured_ext = PPG.config.get_value("ext")
        ext = runez.SYS_INFO.platform_id.canonical_compress_extension(configured_ext, short_form=True)
        if not ext:
            runez.abort("Invalid extension '%s'" % runez.red(configured_ext))

        if prefix:
            dest = prefix.strip("/").replace("/", "-")
            self.tarball_name = PPG.target.composed_basename(dest, extension=ext)

        else:
            self.tarball_name = PPG.target.composed_basename(python_spec.family, python_spec.version, extension=ext)

        builder = PPG.family(python_spec.family).get_builder()
        self.python_builder = builder(self)  # type: PythonBuilder

    def __repr__(self):
        return str(self.folders)

    def validate_module_selection(self, fatal=True):
        issues = []
        selected = self.python_builder.modules.selected
        for module in selected:
            outcome, _ = module.linker_outcome(True)
            if outcome is LinkerOutcome.failed:
                issues.append(module)

        for module in self.python_builder.modules.candidates:
            if module not in selected:
                outcome, _ = module.linker_outcome(is_selected=False)
                if outcome is LinkerOutcome.failed:
                    issues.append(module)

        if issues:
            return runez.abort("Problematic modules: %s" % runez.joined(issues), fatal=fatal)

    def ensure_clean_folder(self, path):
        if path:
            runez.ensure_folder(path, clean=not self.x_debug)

    @runez.log.timeit("Overall compilation")
    def compile(self):
        """Compile selected python family and version"""
        if self.folders.logs:
            self.ensure_clean_folder(self.folders.logs)
            logs_path = self.folders.logs / "00-portable-python.log"
            runez.log.setup(file_location=logs_path.as_posix())

        self.python_builder.validate_setup()
        self.log_counter = 0
        with BuildContext(self) as build_context:
            modules = self.python_builder.modules
            LOG.info("portable-python v%s, current folder: %s" % (runez.get_version(__name__), os.getcwd()))
            LOG.info(runez.joined(modules, list(modules)))
            LOG.info(PPG.config.config_files_report())
            LOG.info("Platform: %s" % PPG.target)
            LOG.info("Build report:\n%s" % self.python_builder.modules.report())
            self.validate_module_selection(fatal=not runez.DRYRUN and not self.x_debug)
            self.ensure_clean_folder(self.folders.components)
            self.ensure_clean_folder(self.folders.deps)
            build_context.compile()
            self.python_builder.compile()
            if self.folders.dist:
                runez.compress(self.python_builder.install_folder, self.folders.dist / self.tarball_name)


class ModuleCollection:
    """Models a collection of sub-modules, with auto-detection and reporting as to what is active and why"""

    candidates: List["ModuleBuilder"] = None
    desired: str = None
    selected: List["ModuleBuilder"] = None

    def __init__(self, parent_module: "ModuleBuilder", desired=None):
        self.selected = []
        self.auto_selected = {}
        self.candidates = []
        self.desired = desired
        self.module_by_name = {}  # type: dict[str, ModuleBuilder]
        candidates = parent_module.candidate_modules()
        if candidates:
            for module in candidates:
                module = module(parent_module)
                self.candidates.append(module)
                self.module_by_name[module.m_name] = module

        if desired == "all":
            self.selected = self.candidates
            return

        desired = [] if desired == "none" else runez.flattened(desired, split=True)
        desired = runez.flattened(desired, split=",")
        unknown = [x for x in desired if x not in self.module_by_name]
        if unknown:
            runez.abort("Unknown modules: %s" % runez.joined(unknown, delimiter=", ", stringify=runez.red))

        for candidate in self.candidates:
            if candidate.m_name not in desired:
                reason = candidate.auto_select_reason()
                if reason:
                    self.auto_selected[candidate.m_name] = reason

        desired.extend(self.auto_selected.keys())
        self.selected = [self.module_by_name[x] for x in desired]

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
        m = self.module_by_name[name]
        return m in self.selected

    def is_usable_module(self, name):
        """Is module with name either selected, or should be usable via its telltale"""
        name = self.get_module_name(name)
        m = self.module_by_name[name]
        return m in self.selected or m.resolved_telltale

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
            if name in self.auto_selected:
                outcome = runez.green("static*")
                note = "[%s] %s" % (runez.bold("auto-selected"), self.auto_selected[name])

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
        self.m_src_build = self.setup.folders.components / self.m_name
        self.resolved_telltale = self._find_telltale()

    def __repr__(self):
        return "%s:%s" % (self.m_name, self.version)

    @classmethod
    def candidate_modules(cls) -> list:
        """All possible candidate external modules for this builder"""

    def selected_modules(self):
        return ModuleCollection(self, desired="all")

    def auto_select_reason(self):
        """
        If this module must be selected (build can't succeed without), descendant should return short explanation why
        """

    def linker_outcome(self, is_selected):
        if self.resolved_telltale is runez.UNSET:
            return runez.UNSET, None

        debian = self.m_debian
        if self.resolved_telltale:
            if is_selected and PPG.target.is_linux and debian and debian.startswith("-"):
                return LinkerOutcome.failed, "%s, can't compile statically with %s present" % (runez.red("broken"), debian[1:])

            outcome = LinkerOutcome.static if is_selected else LinkerOutcome.shared
            return outcome, None

        if PPG.target.is_linux and debian:
            if debian.startswith("!"):
                return LinkerOutcome.failed, "%s, can't compile without %s" % (runez.red("broken"), debian[1:])

            if debian.startswith("+") and is_selected:
                return LinkerOutcome.failed, "%s, can't compile without %s" % (runez.red("broken"), debian[1:])

            if not debian.startswith("-"):
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

        return PPG.find_telltale(telltales)

    def active_module(self, name):
        return self.modules.active_module(name)

    def is_usable_module(self, name):
        """Is module with name either selected or usable as a shared lib, as determined via its telltale"""
        return self.modules.is_usable_module(name)

    def cfg_version(self, default):
        return PPG.config.get_value("%s-version" % self.m_name) or default

    @property
    def url(self):
        """Url of source tarball, if any"""
        return ""

    @property
    def version(self):
        """Version to use"""
        return self.parent_module and self.parent_module.version

    @property
    def deps(self):
        """Folder <build>/.../deps/, where all externals modules get installed"""
        return self.setup.folders.deps

    @property
    def deps_lib(self):
        return self.deps / "lib"

    def xenv_CPATH(self):
        folder = self.deps / "include"
        if folder.exists():
            yield folder
            if self.modules.selected:
                # By default, set CPATH only for modules that have sub-modules (descendants can override this easily)
                for module in self.modules:
                    if module.m_include:
                        yield folder / module.m_include

    def xenv_LDFLAGS(self):
        if self.modules.selected:
            yield f"-L{self.deps_lib}"

    def xenv_PATH(self):
        yield f"{self.deps}/bin"
        yield "/usr/bin"
        yield "/bin"

    def xenv_PKG_CONFIG_PATH(self):
        if self.modules.selected:
            yield f"{self.deps_lib}/pkgconfig"

    def run(self, program, *args, fatal=True):
        return runez.run(program, *args, passthrough=self._log_handler, stdout=None, stderr=None, fatal=fatal)

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

        if cpu_count and cpu_count > 3:
            cmd.append("-j%s" % (cpu_count - 2))

        self.run(*cmd, *args)

    @contextlib.contextmanager
    def captured_logs(self):
        try:
            if self.setup.folders.logs:
                self.setup.log_counter += 1
                logs_path = self.setup.folders.logs / f"{self.setup.log_counter:02}-{self.m_name}.log"
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

        if self.url:
            # Modules without a url just drive sub-modules compilation typically
            print(Header.aerated(str(self)))
            with self.captured_logs():
                if self.setup.x_debug:
                    if "direct-finalize" in self.setup.x_debug:
                        # For quicker iteration: debugging directly finalization
                        self._finalize()
                        return

                # Split on '#' for urls that include a checksum, such as #sha256=... fragment
                basename = runez.basename(self.url, extension_marker="#")
                path = self.setup.folders.sources / basename
                if not path.exists():
                    REST_CLIENT.download(self.url, path)

                runez.decompress(path, self.m_src_build, simplify=True)

                env_vars = self._get_env_vars()
                prev_env_vars = {}
                for var_name, value in env_vars.items():
                    LOG.info("env %s=%s" % (var_name, runez.short(value, size=2048)))
                    prev_env_vars[var_name] = os.environ.get(var_name)
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

                # Restore env vars as they were (to avoid any side effect)
                for k, v in prev_env_vars.items():
                    if v is None:
                        if k in os.environ:
                            del os.environ[k]

                    else:
                        os.environ[k] = v

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

    def __init__(self, parent_module):
        super().__init__(parent_module)
        self.destdir = self.setup.folders.destdir  # Folder passed to 'make install DESTDIR='
        self.c_configure_prefix = self.setup.prefix or self.setup.folders.ppp_marker
        self.install_folder = self.destdir / self.c_configure_prefix.strip("/")
        self.bin_folder = self.install_folder / "bin"

    def validate_setup(self):
        """Descendants can double-check that setup is correct here, in order to fail early if/when applicable"""

    def selected_modules(self):
        desired = self.setup.desired_modules or PPG.config.get_value("%s-modules" % self.m_name)
        return ModuleCollection(self, desired=desired)

    @property
    def version(self):
        return self.setup.python_spec.version

    def xenv_LDFLAGS(self):
        """Python builder does not reuse the common setting"""

    def _prepare(self):
        # Some libs get funky permissions for some reason
        super()._prepare()
        self.setup.ensure_clean_folder(self.install_folder)
        for path in runez.ls_dir(self.deps_lib):
            if not path.name.endswith(".la"):
                expected = 0o755 if path.is_dir() else 0o644
                current = path.stat().st_mode & 0o777
                if current != expected:
                    LOG.info("Corrected permissions for %s (was %s)" % (runez.short(path), oct(current)))
                    path.chmod(expected)

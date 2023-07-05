import datetime
import os
import re

import runez
import yaml
from runez.pyenv import Version

from portable_python import LOG, patch_file, patch_folder, PPG, PythonBuilder
from portable_python.external.tkinter import TkInter
from portable_python.external.xcpython import Bdb, Bzip2, Gdbm, LibFFI, Openssl, Readline, Sqlite, Uuid, Xz, Zlib
from portable_python.inspector import LibAutoCorrect, PythonInspector


# https://github.com/docker-library/python/issues/160
PGO_TESTS = """
-m test.regrtest --pgo test_array test_base64 test_binascii test_binhex test_binop test_bytes test_c_locale_coercion
test_class test_cmath test_codecs test_compile test_complex test_csv test_decimal test_dict test_float test_fstring
test_hashlib test_io test_iter test_json test_long test_math test_memoryview test_pickle test_re test_set test_slice
test_struct test_threading test_time test_traceback test_unicode
"""


# noinspection PyPep8Naming
class Cpython(PythonBuilder):
    """
    Build CPython binaries
    See https://docs.python.org/3/using/configure.html
    """

    xenv_CFLAGS_NODIST = "-Wno-unused-command-line-argument"

    @classmethod
    def candidate_modules(cls):
        return [LibFFI, Zlib, Xz, Bzip2, Readline, Openssl, Sqlite, Bdb, Gdbm, Uuid, TkInter]

    @property
    def url(self):
        """Url of source tarball"""
        if PPG.config.get_value("cpython-use-github"):
            return f"https://github.com/python/cpython/archive/refs/tags/v{self.version}.tar.gz"

        return f"https://www.python.org/ftp/python/{self.version.main}/Python-{self.version}.tar.xz"

    def xenv_LDFLAGS_NODIST(self):
        yield f"-L{self.deps_lib}"
        if PPG.target.is_linux:
            yield "-Wl,-z,origin"
            # rpath intentionally long to give 'patchelf' some room
            yield f"-Wl,-rpath={self.c_configure_prefix}/lib:{self.c_configure_prefix}/lib64"

    def has_configure_opt(self, name, *variants):
        opts = self.c_configure_args_from_config
        if opts:
            variants = runez.flattened(variants)
            if not variants:
                return any(x.startswith(name) for x in opts)

            specs = [name]
            specs.extend("%s=%s" % (name, x) for x in variants)
            return any(x in specs for x in opts)

    @runez.cached_property
    def c_configure_args_from_config(self):
        return runez.flattened(PPG.config.get_value("cpython-configure"))

    def c_configure_args(self):
        configured = self.c_configure_args_from_config
        if configured:
            yield from configured

        if self.active_module(Openssl):
            if self.version >= "3.7" and not self.has_configure_opt("--with-openssl"):
                yield f"--with-openssl={self.deps}"

        if not self.has_configure_opt("--with-system-ffi"):
            if self.active_module(LibFFI):
                yield f"LIBFFI_INCLUDEDIR={self.deps_lib}"
                yield "--with-system-ffi=no"

            else:
                yield "--with-system-ffi"

        if self.version >= "3.10" and not self.has_configure_opt("--disable-test-modules"):
            yield "--disable-test-modules"

        if not self.has_configure_opt("--with-dbmliborder"):
            db_order = [
                self.is_usable_module(Gdbm) and "gdbm",
                self.is_usable_module(Bdb) and "bdb",
                PPG.find_telltale("{include}/ndbm.h") and "ndbm",
            ]
            db_order = runez.joined(db_order, delimiter=":")
            if db_order:
                yield f"--with-dbmliborder={db_order}"

        tkinter = self.active_module(TkInter)
        if tkinter:
            # TODO: this doesn't seem to be enough, on macos cpython's ./configure still picks up the shared macos tcl/tk libs
            version = Version(tkinter.version)
            yield f"--with-tcltk-includes=-I{self.deps}/include"
            yield f"--with-tcltk-libs=-L{self.deps_lib} -ltcl{version.mm} -ltk{version.mm}"

    @runez.cached_property
    def config_folder(self):
        for path in runez.ls_dir(self.install_folder / f"lib/python{self.version.mm}"):
            if path.name.startswith("config-"):
                return path

    def _prepare(self):
        super()._prepare()
        if PPG.target.is_macos:
            # Avoid pollution of static builds via /usr/local on macOS
            rx = re.compile(r"^(Doc|Grammar|Lib|Misc|Modules|PC|Tools|msi|.*\.(md|html|man|pro|rst))$")
            patch_folder(self.m_src_build, r"/usr/local\b", self.deps.as_posix(), ignore=rx)
            setup_py = self.m_src_build / "setup.py"
            if setup_py.exists():
                # Special edge case in macosx_sdk_specified() where /usr/local is fine...
                x = "startswith({q}/usr/{q}) and not path.startswith({q}{p}{q})"
                special_case = x.replace("(", r"\(").replace(")", r"\)").format(q="['\"]", p=self.deps)
                restored = x.format(q="'", p='/usr/local')
                patch_file(setup_py, special_case, restored)

            # Only doable on macOS: patch -install_name so produced exes/libs use a relative path
            install_name = "-Wl,-install_name,@executable_path/.."
            patch_folder(self.m_src_build, r"-Wl,-install_name,\$\(prefix\)", install_name)

    def _do_linux_compile(self):
        self.run_configure("./configure", self.c_configure_args(), prefix=self.c_configure_prefix)
        make_args = []
        if self.version < "3.8":
            pgo_tests = runez.joined(runez.flattened(PGO_TESTS, split=True))
            make_args.append(f"PROFILE_TASK={pgo_tests}")

        self.run_make(*make_args)
        self.run_make("install", f"DESTDIR={self.destdir}")

    def _pip_upgrade(self, *lib_names):
        for lib_name in runez.flattened(lib_names, split=True, unique=True):
            do_install = True
            if lib_name.startswith("?"):
                lib_name = lib_name[1:]
                path = self.install_folder / f"lib/python{self.version.mm}/site-packages/{lib_name}"
                do_install = path.exists()

            if do_install:
                self.run_python("-mpip", "install", "-U", lib_name)

    def _finalize(self):
        is_shared = self.setup.prefix or self.has_configure_opt("--enable-shared", "yes")
        if is_shared:
            lib_auto_correct = LibAutoCorrect(self.c_configure_prefix, self.install_folder, ppp_marker=self.setup.folders.ppp_marker)
            lib_auto_correct.run()

        runez.abort_if(not runez.DRYRUN and not self.bin_python, f"Can't find bin/python in {self.bin_folder}")
        self._pip_upgrade("?pip", "?setuptools", PPG.config.get_value("cpython-pip-install"))
        PPG.config.ensure_main_file_symlinks(self)
        if not self.setup.prefix:
            # See https://manpages.debian.org/stretch/pkg-config/pkg-config.1.en.html#PKG-CONFIG_DERIVED_VARIABLES
            patch_folder(
                self.install_folder / "lib/pkgconfig",
                f"prefix={self.c_configure_prefix}",
                "prefix=${pcfiledir}/../.."
            )
            sys_cfg = self._find_sys_cfg()
            if sys_cfg:
                rs = RelSysConf(sys_cfg, self.c_configure_prefix)
                runez.write(sys_cfg, rs.text)

        for folder in (self.bin_folder, self.config_folder):
            for path in runez.ls_dir(folder):
                if path != self.bin_python and runez.is_executable(path) and not path.is_symlink():
                    self._auto_correct_shebang_file(path)

        PPG.config.cleanup_folder(self, "cpython-clean-1st-pass")
        PPG.config.symlink_duplicates(self.install_folder)
        py_inspector = PythonInspector(self.install_folder)
        print(py_inspector.represented())
        problem = py_inspector.full_so_report.get_problem(portable=not is_shared)
        runez.abort_if(problem and self.setup.x_debug != "direct-finalize", "Build failed: %s" % problem)
        validation_script = PPG.config.resolved_path("cpython-validate-script")
        if validation_script:
            LOG.info("Exercising configured validation script: %s" % runez.short(validation_script))
            self.run_python(validation_script)

        if PPG.config.get_value("cpython-additional-packages"):
            self.run_python("-mpip", "install", *runez.flattened(PPG.config.get_value("cpython-additional-packages")))

        check_venvs = PPG.config.get_value("cpython-check-venvs")
        if check_venvs:
            if check_venvs in ("venv", "all"):
                self._check_venv()

            if check_venvs in ("copies", "all"):
                self._check_venv(copies=True)

        if PPG.config.get_value("cpython-compile-all"):
            self.run_python("-mcompileall", "-q", self.install_folder / "lib")

        info_path = PPG.config.get_value("manifest", "build-info")
        if info_path:
            contents = self._represented_yaml(self.build_information())
            runez.write(self.install_folder / info_path, contents)

        info_path = PPG.config.get_value("manifest", "inspection-report")
        if info_path:
            with runez.colors.ActivateColors(enable=False):
                py_inspector = PythonInspector(self.install_folder, modules="all")
                contents = "%s\n" % py_inspector.represented(verbose=True)
                runez.write(self.install_folder / info_path, contents)

        PPG.config.cleanup_folder(self, "cpython-clean-2nd-pass", "cpython-clean")

    def _check_venv(self, copies=False):
        """Verify that the freshly compiled python can create venvs without issue"""
        folder = "venv"
        args = ["-mvenv"]
        if copies:
            args.append("--copies")
            folder += "-copies"

        folder = self.setup.folders.build_folder / "test-venvs" / folder
        self.run_python(*args, folder)
        self.run_python("-mpip", "--version")

    @staticmethod
    def _represented_yaml(bits):
        content = [yaml.safe_dump(runez.serialize.json_sanitized({x: y}), width=140) for x, y in bits]
        return runez.joined(content, delimiter="\n")

    def build_information(self):
        yield "cpython", {
            "prefix": self.setup.prefix,
            "source": self.url,
            "static": runez.joined(self.modules.selected) or None,
            "target": PPG.target,
            "version": self.version,
        }
        yield "configure-args", runez.joined(runez.short(x) for x in self.c_configure_args())
        compiled_by = os.environ.get("PP_ORIGIN") or PPG.config.get_value("compiled-by")
        bc = self.setup.build_context
        yield "compilation-info", {
            "compiled-by": compiled_by or "https://pypi.org/project/portable-python/",
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "host-platform": runez.SYS_INFO.platform_info,
            "ldd-version": PythonInspector.tool_version("ldd"),
            "portable-python-version": runez.get_version(__package__),
            "special-context": bc.isolate_usr_local and bc,
        }
        additional = PPG.config.get_value("manifest", "additional-info")
        if additional:
            res = {}
            for k, v in additional.items():
                if isinstance(v, str) and v.startswith("$"):
                    v = os.environ.get(v[1:])

                res[k] = v

            yield "additional-info", res

    def _find_sys_cfg(self):
        if self.config_folder:
            for path in runez.ls_dir(self.config_folder.parent):
                if path.name.startswith("_sysconfigdata"):
                    return path

    def _auto_correct_shebang_file(self, path):
        lines = []
        with open(path) as fh:
            try:
                for line in fh:
                    if lines:
                        lines.append(line)
                        continue

                    if not line.startswith("#!") or "bin/python" not in line:
                        return

                    if self.setup.prefix:
                        lines.append(f"#!{self.setup.prefix}/bin/{self.bin_python.name}\n")

                    else:
                        rel_location = os.path.relpath(self.bin_python, path.parent)
                        lines.append("#!/bin/sh\n")
                        lines.append('"exec" "$(dirname $0)/%s" "$0" "$@"\n' % rel_location)

            except UnicodeError:
                return

        if lines:
            LOG.info("Auto-corrected shebang for %s" % runez.short(path))
            with open(path, "wt") as fh:
                for line in lines:
                    fh.write(line)


class RelSysConf:
    """Make _sysconfigdata report paths (eg: prefix) relative to its current location"""

    def __init__(self, path, prefix):
        self.path = path
        self.prefix = prefix
        self.rx_marker = re.compile(r"^build_time_vars\s*=.*")
        self.rx_strings = re.compile(r"(['\"])([^'\"]+)(['\"])")
        self.text = "\n".join(self._process_file())

    def _process_file(self):
        for line in runez.readlines(self.path):
            if self.rx_marker.match(line):
                yield "prefix = __file__.rpartition('/')[0].rpartition('/')[0].rpartition('/')[0]"

            if self.prefix in line:
                line = "".join(self._relativize(line))

            yield line

    def _relativize(self, line):
        start = 0
        for m in self.rx_strings.finditer(line):
            yield line[start:m.start(0)]
            start = m.end(0)
            content = m.group(2)
            if self.prefix in content:
                quote = m.group(1)
                yield "f%s%s%s" % (quote, content.replace(self.prefix, "{prefix}"), quote)

            else:
                yield m.group(0)

        yield line[start:]

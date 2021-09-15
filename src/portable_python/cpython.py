import runez

from portable_python import PPG, PythonBuilder
from portable_python.external.xcpython import Bdb, Bzip2, Gdbm, LibFFI, Openssl, Readline, Sqlite, Uuid, Xz, Zlib
from portable_python.inspector import PythonInspector


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
    See https://docs.python.org/3.11/using/configure.html
    """

    @classmethod
    def candidate_modules(cls):
        return [LibFFI, Zlib, Xz, Bzip2, Readline, Openssl, Sqlite, Bdb, Gdbm, Uuid]

    @property
    def url(self):
        """Url of source tarball"""
        if PPG.config.get_value("cpython-use-github"):
            return f"https://github.com/python/cpython/archive/refs/tags/v{self.version}.tar.gz"

        return f"https://www.python.org/ftp/python/{self.version}/Python-{self.version}.tar.xz"

    # noinspection PyMethodMayBeStatic
    def xenv_CFLAGS_NODIST(self):
        yield "-Wno-unused-command-line-argument"

    def xenv_LDFLAGS_NODIST(self):
        yield f"-L{self.deps_lib}"
        if PPG.target.is_linux:
            yield f"-Wl,-rpath,{self.install_folder}/lib"

    def c_configure_args(self):
        configured = PPG.config.get_value("cpython-configure")
        if configured:
            yield from configured

        if self.version >= "3.10":
            yield "--disable-test-modules"

        if self.active_module(LibFFI):
            yield f"LIBFFI_INCLUDEDIR={self.deps_lib}"
            yield "--with-system-ffi=no"

        db_order = [
            self.active_module(Gdbm) and "gdbm",
            self.active_module(Bdb) and "bdb",
        ]
        db_order = runez.joined(db_order, delimiter=":")
        if db_order:
            yield f"--with-dbmliborder={db_order}"

        if self.version >= "3.7" and self.active_module(Openssl):
            yield f"--with-openssl={self.deps}"

    def _do_linux_compile(self):
        self.run_configure("./configure", self.c_configure_args(), prefix=self.c_configure_prefix)
        make_args = []
        if self.version < "3.8":
            pgo_tests = runez.joined(runez.flattened(PGO_TESTS, split=True))
            make_args.append(f"PROFILE_TASK={pgo_tests}")

        self.run_make(*make_args)
        self.run_make("install", f"DESTDIR={self.destdir}")

    def _finalize(self):
        should_be_runnable_from_install_folder = not PPG.target.is_macos or not self.setup.prefix
        bin_python = PPG.config.find_main_file(self.bin_folder / "python", self.version, fatal=not runez.DRYRUN)
        if should_be_runnable_from_install_folder:
            extras = PPG.config.get_value("cpython-pip-install")
            if extras:
                extras = runez.flattened(extras, split=" ")
                for extra in extras:
                    self.run(bin_python, "-mpip", "install", "-U", extra, fatal=False)

        PPG.config.cleanup_folder(self)
        PPG.config.ensure_main_file_symlinks(self)
        if should_be_runnable_from_install_folder:
            self.run(bin_python, "-mcompileall")

        if not self.setup.prefix:
            for f in runez.ls_dir(self.bin_folder):
                PPG.config.auto_correct_shebang(f, bin_python)

        if should_be_runnable_from_install_folder:
            py_inspector = PythonInspector(self.install_folder)
            print(py_inspector.represented())
            problem = py_inspector.full_so_report.get_problem(portable=not self.setup.prefix)
            if problem:
                runez.abort("Build failed: %s" % problem, fatal=not runez.DRYRUN)

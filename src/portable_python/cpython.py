import os

import runez

from portable_python import PPG, PythonBuilder
from portable_python.external.xcpython import Bdb, Bzip2, Gdbm, LibFFI, Openssl, Readline, Sqlite, Uuid, Xz, Zlib
from portable_python.inspector import auto_correct_shared_libs, PythonInspector


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
        if self.has_configure_opt("--enable-shared", "yes"):
            if PPG.target.is_linux:
                yield f"-Wl,-rpath={self.setup.prefix}/lib"
                # os.environ["ORIGIN"] = "$ORIGIN"
                # yield f"-Wl,-rpath=$ORIGIN/../lib"  # -Wl,-z,origin ?

    def has_configure_opt(self, name, *variants):
        specs = [name]
        specs.extend("%s=%s" % (name, x) for x in variants)
        return any(x in specs for x in self.c_configure_args())

    def c_configure_args(self):
        configured = PPG.config.get_value("cpython-configure")
        if configured:
            yield from configured

        if not self.active_module(LibFFI):
            yield "--with-system-ffi"

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
        auto_correct_shared_libs(self.c_configure_prefix, self.install_folder)
        bin_python = PPG.config.find_main_file(self.bin_folder / "python", self.version, fatal=not runez.DRYRUN)
        if self.setup.prefix and PPG.target.is_linux:
            # TODO: simplify when auto_correct_shared_libs() can fix linux too
            prev = os.environ.get("LD_LIBRARY_PATH")
            os.environ["LD_LIBRARY_PATH"] = runez.joined(f"{self.install_folder}/lib", prev, delimiter=os.pathsep)

        if self.has_configure_opt("--with-ensurepip", "upgrade"):
            self.run(bin_python, "-mpip", "install", "-U", "pip", fatal=False)
            setuptools = self.install_folder / f"lib/python{self.version.mm}/site-packages/setuptools"
            if setuptools.exists():
                self.run(bin_python, "-mpip", "install", "-U", "setuptools", fatal=False)

        extras = PPG.config.get_value("cpython-pip-install")
        if extras:
            extras = runez.flattened(extras, split=" ")
            for extra in extras:
                self.run(bin_python, "-mpip", "install", "-U", extra, fatal=False)

        PPG.config.cleanup_folder(self)
        PPG.config.ensure_main_file_symlinks(self)
        self.run(bin_python, "-mcompileall")

        if not self.setup.prefix:
            for f in runez.ls_dir(self.bin_folder):
                PPG.config.auto_correct_shebang(f, bin_python)

        py_inspector = PythonInspector(self.install_folder)
        print(py_inspector.represented())
        problem = py_inspector.full_so_report.get_problem(portable=not self.setup.prefix)
        if problem:
            runez.abort("Build failed: %s" % problem, fatal=not runez.DRYRUN)

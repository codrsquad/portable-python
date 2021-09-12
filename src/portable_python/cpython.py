import runez

from portable_python import PPG, PythonBuilder
from portable_python.external.xcpython import Bdb, Bzip2, Gdbm, LibFFI, Openssl, Readline, Sqlite, Uuid, Xz, Zlib


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

    def xenv_CFLAGS_NODIST(self):
        yield from super().xenv_CFLAGS_NODIST()
        yield "-Wno-unused-command-line-argument"

    def xenv_LDFLAGS_NODIST(self):
        yield from super().xenv_LDFLAGS_NODIST()
        if PPG.target.is_linux and self.setup.prefix:
            yield f"-Wl,-rpath,{self.setup.prefix}/lib"

    def c_configure_args(self):
        configured = PPG.config.get_value("cpython-configure")
        if configured:
            yield from configured

        if self.setup.prefix:
            yield "--enable-shared"

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

        if self.active_module(Openssl):
            yield f"--with-openssl={self.deps}"     # 3.7+?

    def _do_linux_compile(self):
        self.run_configure("./configure", self.c_configure_args(), prefix=self.c_configure_prefix)
        self.run_make()
        self.run_make("install", f"DESTDIR={self.build_root}")

    def _finalize(self):
        bin_python = PPG.config.find_main_file(self.bin_folder / "python", self.version, fatal=not runez.DRYRUN)
        extras = PPG.config.get_value("cpython-pip-install")
        if extras:
            extras = runez.flattened(extras, split=" ")
            for extra in extras:
                self.run(bin_python, "-mpip", "install", "-U", extra, fatal=False)

        PPG.config.cleanup_folder(self)
        PPG.config.ensure_main_file_symlinks(self)
        if not self.setup.prefix:
            for f in runez.ls_dir(self.bin_folder):
                PPG.config.auto_correct_shebang(f, bin_python)

            self.run(bin_python, "-mcompileall")

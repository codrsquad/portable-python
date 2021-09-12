import runez
from runez.pyenv import Version

from portable_python import PPG, PythonBuilder
from portable_python.external.xcpython import Bdb, Bzip2, Gdbm, LibFFI, Openssl, Readline, Sqlite, TkInter, Uuid, Xz, Zlib


class Cpython(PythonBuilder):
    """Build CPython binaries"""

    @classmethod
    def candidate_modules(cls):
        return [LibFFI, Zlib, Xz, Bzip2, Readline, Openssl, Sqlite, Bdb, Gdbm, TkInter, Uuid]

    @property
    def url(self):
        """Url of source tarball"""
        if PPG.config.get_value("cpython-use-github"):
            return f"https://github.com/python/cpython/archive/refs/tags/v{self.version}.tar.gz"

        return f"https://www.python.org/ftp/python/{self.version}/Python-{self.version}.tar.xz"

    # noinspection PyMethodMayBeStatic
    # noinspection PyPep8Naming
    def xenv_CFLAGS(self):
        yield "-Wno-unused-command-line-argument"

    def c_configure_args(self):
        configured = PPG.config.get_value("cpython-configure")
        if configured:
            yield from configured

        yield "--enable-shared=%s" % ("yes" if self.setup.prefix else "no")
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
            yield f"--with-openssl={self.deps}"

        tkinter = self.active_module(TkInter)
        if tkinter:
            mm = Version.from_text(tkinter.version)
            mm = "%s.%s" % (mm.major, mm.minor)
            yield f"--with-tcltk-includes=-I{self.deps}/include"
            yield f"--with-tcltk-libs=-L{self.deps_lib} -ltcl{mm} -ltk{mm}"

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
        for f in runez.ls_dir(self.bin_folder):
            PPG.config.auto_correct_shebang(f, bin_python)

        PPG.config.ensure_main_file_symlinks(self)
        self.run(bin_python, "-mcompileall")

import runez

from portable_python.builder import BuildSetup, ModuleBuilder


@BuildSetup.module_builders.declare
class Gdbm(ModuleBuilder):

    needs_modules = ["readline"]

    @property
    def url(self):
        return f"https://ftp.gnu.org/gnu/gdbm/gdbm-{self.version}.tar.gz"

    @property
    def version(self):
        return "1.18.1"

    def _do_linux_compile(self):
        # CPython setup.py looks for libgdbm_compat and gdbm-ndbm.h, which require --enable-libgdbm-compat
        self.run("./configure", "--prefix=/deps", "--disable-shared", "--enable-libgdbm-compat")
        self.run("make")
        self.run("make", "install", "DESTDIR=%s" % self.deps.parent)


@BuildSetup.module_builders.declare
class Bdb(ModuleBuilder):
    """See https://docs.python.org/3/library/dbm.html"""

    @property
    def url(self):
        return f"https://ftp.osuosl.org/pub/blfs/conglomeration/db/db-{self.version}.tar.gz"

    @property
    def version(self):
        return "6.2.32"

    def _do_linux_compile(self):
        with runez.CurrentFolder("build_unix"):
            self.run("../dist/configure", "--prefix=/deps", "--enable-dbm", "--disable-shared")
            self.run("make")
            self.run("make", "install", "DESTDIR=%s" % self.deps.parent)


@BuildSetup.module_builders.declare
class Sqlite(ModuleBuilder):

    @property
    def url(self):
        return f"https://github.com/sqlite/sqlite/archive/refs/tags/version-{self.version}.tar.gz"

    @property
    def version(self):
        return "3.36.0"

    def _do_linux_compile(self):
        self.run("./configure", "--prefix=/deps", "--disable-shared")
        self.run("make")
        self.run("make", "install", "DESTDIR=%s" % self.deps.parent)

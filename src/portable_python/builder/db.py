import runez

from portable_python.builder import BuildSetup, ModuleBuilder


@BuildSetup.module_builders.declare
class Gdbm(ModuleBuilder):

    telltale = "{include}/gdbm.h"

    @classmethod
    def auto_use_with_reason(cls, target):
        if target.is_macos:
            # Fails to build on macos, and not needed there (builds fine with system tcl/tk)
            return False, runez.brown("not needed on macos")

        return super().auto_use_with_reason(target)
    @property
    def url(self):
        return f"https://ftp.gnu.org/gnu/gdbm/gdbm-{self.version}.tar.gz"

    @property
    def version(self):
        return "1.18.1"

    def c_configure_args(self):
        # CPython setup.py looks for libgdbm_compat and gdbm-ndbm.h, which require --enable-libgdbm-compat
        yield from super().c_configure_args()
        yield "--enable-libgdbm-compat"


@BuildSetup.module_builders.declare
class Bdb(ModuleBuilder):
    """See https://docs.python.org/3/library/dbm.html"""

    c_configure_cwd = "build_unix"
    c_configure_program = "../dist/configure"

    @property
    def url(self):
        return f"https://ftp.osuosl.org/pub/blfs/conglomeration/db/db-{self.version}.tar.gz"

    @property
    def version(self):
        return "6.2.32"

    def c_configure_args(self):
        yield from super().c_configure_args()
        yield "--enable-dbm"


@BuildSetup.module_builders.declare
class Sqlite(ModuleBuilder):

    telltale = "{include}/sqlite3.h"

    @property
    def url(self):
        return f"https://github.com/sqlite/sqlite/archive/refs/tags/version-{self.version}.tar.gz"

    @property
    def version(self):
        return "3.36.0"

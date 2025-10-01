from typing import ClassVar

import runez

from portable_python import LinkerOutcome, ModuleBuilder, PPG


class Bdb(ModuleBuilder):
    """
    See https://docs.python.org/3/library/dbm.html
    Known issues:
    - macos: fails to build statically, symbol not found: _gdbm_version_number
    - linux: fails to get detected unless both Bdb and Gdbm are selected
    """

    m_build_cwd = "build_unix"
    m_debian = "libgdbm-compat-dev"
    m_telltale = "{include}/dbm.h"

    xenv_CFLAGS = "-fPIC"

    @property
    def url(self):
        return self.cfg_url(self.version) or f"https://ftp.osuosl.org/pub/blfs/conglomeration/db/db-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("6.2.32")

    def c_configure_args(self):
        if config_args := self.cfg_configure(self.deps_lib_dir, self.deps_lib64_dir):
            yield config_args

        else:
            yield "--enable-shared=no"
            yield "--enable-static=yes"
            yield "--enable-dbm"
            yield "--with-pic=yes"

    def _do_linux_compile(self):
        self.run_configure("../dist/configure", self.c_configure_args())
        self.run_make()
        self.run_make("install")


class Bzip2(ModuleBuilder):
    """
    See https://docs.python.org/3/library/bz2.html
    """

    m_telltale = "{include}/bzlib.h"

    def auto_select_reason(self):
        if PPG.target.is_macos and self.setup.python_spec.version < "3.8":
            return "Required for versions prior to 3.8"

    @property
    def url(self):
        return self.cfg_url(self.version) or f"https://sourceware.org/pub/bzip2/bzip2-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("1.0.8")

    def _do_linux_compile(self):
        self.run_make("install", f"PREFIX={self.deps}", "CFLAGS=-fPIC -O2 -g -D_FILE_OFFSET_BITS=64")


class Gdbm(ModuleBuilder):
    """
    See https://docs.python.org/2.7/library/gdbm.html
    Known issues:
    - macos-x86_64: works if selected WITHOUT Bdb (in which case both bdb and gdbm get statically linked)
    - macos-arch64: if selected, then `_dbm` fails to build
    - linux: fails to build unless both Bdb and Gdbm are selected, undefined symbol: gdbm_version_number
    """

    m_debian = "libgdbm-dev"
    m_telltale: ClassVar[list] = ["{include}/gdbm.h"]

    @property
    def url(self):
        return self.cfg_url(self.version) or f"https://ftpmirror.gnu.org/gnu/gdbm/gdbm-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("1.26")

    def c_configure_args(self):
        if config_args := self.cfg_configure(self.deps_lib_dir, self.deps_lib64_dir):
            yield config_args

        else:
            yield "--enable-shared=no"
            yield "--enable-static=yes"
            yield "--enable-libgdbm-compat"
            yield "--with-pic=yes"
            yield "--disable-nls"
            yield "--disable-dependency-tracking"
            yield "--disable-rpath"
            yield "--disable-silent-rules"
            yield "--without-libiconv-prefix"
            yield "--without-libintl-prefix"
            yield "--without-readline"

    def _do_linux_compile(self):
        self.run_configure("./configure", self.c_configure_args())
        self.run_make()
        self.run_make("install")
        runez.move(self.deps / "include/ndbm.h", self.deps / "include/gdbm-ndbm.h")


class LibFFI(ModuleBuilder):
    """
    Known issues:
    - linux: needs libffi-dev installed (even for a static build)
    - macos-arch64: fails to build statically, symbol not found: _ffi_closure_trampoline_table_page
    """

    m_debian = "!libffi-dev"
    m_telltale: ClassVar[list] = ["{include}/ffi.h", "{include}/ffi/ffi.h"]

    xenv_CFLAGS = "-fPIC"

    @property
    def url(self):
        return (
            self.cfg_url(self.version) or f"https://github.com/libffi/libffi/releases/download/v{self.version}/libffi-{self.version}.tar.gz"
        )

    @property
    def version(self):
        return self.cfg_version("3.5.2")

    def c_configure_args(self):
        if config_args := self.cfg_configure(self.deps_lib_dir, self.deps_lib64_dir):
            yield config_args

        else:
            yield "--enable-shared=no"
            yield "--enable-static=yes"
            yield "--with-pic=yes"
            yield PPG.target.is_macos and "--disable-multi-os-directory"
            yield "--disable-docs"

    def _do_linux_compile(self):
        self.run_configure("./configure", self.c_configure_args())
        self.run_make()
        self.run_make("install")


class Openssl(ModuleBuilder):
    """
    See https://wiki.openssl.org/index.php/Compilation_and_Installation
    """

    m_include = "openssl"
    m_telltale = "{include}/openssl/ssl.h"

    def auto_select_reason(self):
        if PPG.target.is_macos:
            return "Required on macos"

    @property
    def url(self):
        if self.version and self.version.startswith("1.1.1"):
            # Not sure why URL suddenly changed for this on github...
            vfolder = self.version.replace(".", "_")
            return (
                self.cfg_url(self.version)
                or f"https://github.com/openssl/openssl/releases/download/OpenSSL_{vfolder}/openssl-{self.version}.tar.gz"
            )

        return f"https://github.com/openssl/openssl/releases/download/openssl-{self.version}/openssl-{self.version}.tar.gz"

    @property
    def version(self):
        # See https://endoflife.date/openssl
        # This default here picks the most conservative longest supported version
        return self.cfg_version("3.0.17")

    def c_configure_args(self):
        if config_args := self.cfg_configure(self.deps_lib_dir, self.deps_lib64_dir):
            yield config_args

        else:
            yield "-v"
            yield "--openssldir=/etc/ssl"
            yield "no-shared", "no-idea", "no-tests"

    def _do_linux_compile(self):
        self.run_configure("./config", self.c_configure_args())
        self.run_make("depend")
        self.run_make()
        self.run_make("install_sw")  # See https://github.com/openssl/openssl/issues/8170


class Ncurses(ModuleBuilder):
    m_include = "ncursesw"

    xenv_CFLAGS = "-fPIC"

    @property
    def url(self):
        return self.cfg_url(self.version) or f"https://ftpmirror.gnu.org/gnu/ncurses/ncurses-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("6.5")

    def c_configure_args(self):
        if config_args := self.cfg_configure(self.deps_lib_dir, self.deps_lib64_dir):
            yield config_args

        else:
            yield "--disable-shared"
            yield "--enable-static"
            yield "--without-ada"
            yield "--disable-db-install"
            yield "--without-manpages"
            yield "--without-progs"
            yield "--without-tests"
            yield f"--with-pkg-config-libdir={self.deps_lib_dir}/pkgconfig"
            yield "--enable-pc-files"
            yield "--with-debug=no"
            yield "--with-gpm=no"
            yield "--enable-widec"
            yield "--enable-symlinks"
            yield "--enable-sigwinch"
            yield "--without-develop"
            if PPG.target.is_linux:
                yield "--with-terminfo-dirs=/etc/terminfo:/lib/terminfo:/usr/share/terminfo"

            if PPG.target.is_macos:
                yield "--with-terminfo-dirs=/usr/share/terminfo"

    def _do_linux_compile(self):
        self.run_configure("./configure", self.c_configure_args())
        self.run_make()
        self.run_make("install")


class Readline(ModuleBuilder):
    """
    See https://github.com/Homebrew/homebrew-core/blob/HEAD/Formula/readline.rb
    Known issues:
    - linux: libreadline-dev must NOT be installed in order for static build to succeed
    """

    m_debian = "-libreadline-dev"
    m_include = "readline"
    m_telltale = "{include}/readline/readline.h"

    xenv_CFLAGS = "-fPIC"

    @classmethod
    def candidate_modules(cls):
        return [Ncurses]

    @property
    def url(self):
        return self.cfg_url(self.version) or f"http://ftpmirror.gnu.org/gnu/readline/readline-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("8.2.13")

    def c_configure_args(self):
        if config_args := self.cfg_configure(self.deps_lib_dir, self.deps_lib64_dir):
            yield config_args

        else:
            yield "--enable-shared=no"
            yield "--enable-static=yes"
            yield "--with-curses"
            yield "--enable-multibyte"
            yield "--disable-install-examples"
            yield "--disable-docs"
            yield "--enable-portable-binary"

    def _do_linux_compile(self):
        self.run_configure("./configure", self.c_configure_args())
        self.run_make()
        self.run_make("install")


class Sqlite(ModuleBuilder):
    """
    Known issues:
    - linux: libsqlite3-dev must be installed in order for static build to succeed
    """

    m_debian = "+libsqlite3-dev"
    m_telltale: ClassVar[list] = ["{include}/sqlite3.h"]

    xenv_CFLAGS = "-fPIC"

    def linker_outcome(self, is_selected):
        if is_selected and not runez.which("tclsh"):
            return LinkerOutcome.failed, "%s (apt install tcl)" % runez.red("needs tclsh")

        return super().linker_outcome(is_selected)

    @property
    def url(self):
        return self.cfg_url(self.version) or f"https://github.com/sqlite/sqlite/archive/refs/tags/version-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("3.50.4")

    def c_configure_args(self):
        if config_args := self.cfg_configure(self.deps_lib_dir, self.deps_lib64_dir):
            yield config_args

        else:
            yield "--disable-shared"
            yield "--disable-tcl"
            yield "--disable-readline"

    def _do_linux_compile(self):
        self.run_configure("./configure", self.c_configure_args())
        self.run_make()
        self.run_make("install")


class Uuid(ModuleBuilder):
    """
    Known issues:
    - linux: uuid-dev must be installed in order for static build to succeed
    """

    m_debian = "+uuid-dev"
    m_include = "uuid"
    m_telltale: ClassVar[list] = ["{include}/uuid/uuid.h"]

    xenv_CFLAGS = "-fPIC"

    @property
    def url(self):
        return self.cfg_url(self.version) or f"https://sourceforge.net/projects/libuuid/files/libuuid-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("1.0.3")

    def c_configure_args(self):
        if config_args := self.cfg_configure(self.deps_lib_dir, self.deps_lib64_dir):
            yield config_args

        else:
            yield "--enable-shared=no"
            yield "--enable-static=yes"
            yield "--with-pic=yes"

    def _do_linux_compile(self):
        self.run_configure("./configure", self.c_configure_args())
        self.run_make()
        self.run_make("install")


class Xz(ModuleBuilder):
    m_telltale = "{include}/lzma.h"

    def auto_select_reason(self):
        if not self.resolved_telltale:
            return "Required when lzma.h is not available"

    @property
    def url(self):
        return self.cfg_url(self.version) or f"https://downloads.sourceforge.net/project/lzmautils/xz-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("5.8.1")

    def c_configure_args(self):
        if config_args := self.cfg_configure(self.deps_lib_dir, self.deps_lib64_dir):
            yield config_args

        else:
            yield "--enable-shared=no"
            yield "--enable-static=yes"
            yield "--with-pic=yes"
            yield "--disable-rpath"
            yield "--disable-dependency-tracking"
            yield "--disable-doc"
            yield "--disable-nls"
            yield "--without-libintl-prefix"

    def _do_linux_compile(self):
        self.run_configure("./configure", self.c_configure_args())
        self.run_make()
        self.run_make("install")


class Zlib(ModuleBuilder):
    """
    Known issues:
    - linux: needs zlib1g-dev installed (even for a static build)
    """

    m_debian = "!zlib1g-dev"
    m_telltale = "{include}/zlib.h"

    xenv_CFLAGS = "-fPIC"

    def auto_select_reason(self):
        if PPG.target.is_macos and self.setup.python_spec.version < "3.8":
            return "Required for versions prior to 3.8"

    @property
    def url(self):
        return self.cfg_url(self.version) or f"https://zlib.net/fossils/zlib-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("1.3.1")

    def c_configure_args(self):
        if config_args := self.cfg_configure(self.deps_lib_dir, self.deps_lib64_dir):
            yield config_args

        else:
            yield "--static"

    def _do_linux_compile(self):
        self.run_configure("./configure", self.c_configure_args())
        self.run_make()
        self.run_make("install")

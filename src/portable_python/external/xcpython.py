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

    @property
    def url(self):
        return f"https://ftp.osuosl.org/pub/blfs/conglomeration/db/db-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("6.2.32")

    # noinspection PyPep8Naming
    # noinspection PyMethodMayBeStatic
    def xenv_CFLAGS(self):
        yield "-fPIC"

    def _do_linux_compile(self):
        self.run_configure("../dist/configure", "--enable-shared=no", "--enable-static=yes", "--enable-dbm", "--with-pic=yes")
        self.run_make()
        self.run_make("install")


class Bzip2(ModuleBuilder):
    """
    See https://docs.python.org/3/library/bz2.html
    """

    m_telltale = "{include}/bzlib.h"

    @property
    def url(self):
        return f"https://sourceware.org/pub/bzip2/bzip2-{self.version}.tar.gz"

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
    m_telltale = ["{include}/gdbm.h"]

    @property
    def url(self):
        return f"https://ftp.gnu.org/gnu/gdbm/gdbm-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("1.18.1")

    def _do_linux_compile(self):
        self.run_configure(
            "./configure",
            "--enable-shared=no",
            "--enable-static=yes",
            "--with-pic=yes",
            "--enable-libgdbm-compat",
            "--disable-dependency-tracking",
            "--disable-nls",
            "--disable-rpath",
            "--disable-silent-rules",
            "--without-libiconv-prefix",
            "--without-libintl-prefix",
            "--without-readline",
        )
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
    m_telltale = ["{include}/ffi.h", "{include}/ffi/ffi.h"]

    @property
    def url(self):
        return f"https://github.com/libffi/libffi/releases/download/v{self.version}/libffi-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("3.4.2")

    # noinspection PyPep8Naming
    # noinspection PyMethodMayBeStatic
    def xenv_CFLAGS(self):
        yield "-fPIC"

    def _do_linux_compile(self):
        self.run_configure(
            "./configure",
            "--enable-shared=no",
            "--enable-static=yes",
            "--with-pic=yes",
            PPG.target.is_macos and "--disable-multi-os-directory",
            "--disable-docs",
        )
        self.run_make()
        self.run_make("install")


class Openssl(ModuleBuilder):
    """
    See https://wiki.openssl.org/index.php/Compilation_and_Installation
    """

    m_include = "openssl"
    m_telltale = "{include}/openssl/ssl.h"

    @property
    def url(self):
        return f"https://www.openssl.org/source/openssl-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("1.1.1k")

    def c_configure_args(self):
        yield f"--openssldir={self.deps}"
        yield "-DPEDANTIC"
        yield "no-shared", "no-idea", "no-tests"
        if PPG.target.is_macos:
            yield "darwin64-%s-cc" % PPG.target.arch

        else:
            yield "%s-%s" % (PPG.target.platform, PPG.target.arch)

    def _do_linux_compile(self):
        self.run_configure("./Configure", self.c_configure_args())
        self.run_make("depend")
        self.run_make("all")
        self.run_make("install_sw")  # See https://github.com/openssl/openssl/issues/8170


class Ncurses(ModuleBuilder):

    m_include = "ncursesw"

    @property
    def url(self):
        return f"https://ftp.gnu.org/pub/gnu/ncurses/ncurses-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("6.2")

    def c_configure_args(self):
        yield "--enable-shared=no"
        yield "--enable-static=yes"
        yield "--enable-widec"
        yield "--enable-pc-files"
        yield f"--with-pkg-config-libdir={self.deps_lib}/pkgconfig"
        if PPG.target.is_linux:
            yield "--with-terminfo-dirs=/etc/terminfo:/lib/terminfo:/usr/share/terminfo"

        yield "--enable-sigwinch"
        yield "--enable-symlinks"
        yield "--with-gpm=no",
        yield "--without-ada"
        yield "--without-cxx"
        yield "--without-tests"
        yield "--without-manpages"
        # yield "--without-progs"
        if PPG.target.is_macos:
            yield "--disable-db-install"
            yield "--datadir=/usr/share"
            yield "--sysconfdir=/etc"
            yield "--sharedstatedir=/usr/com"
            yield "--with-terminfo-dirs=/usr/share/terminfo"
            yield "--with-default-terminfo-dir=/usr/share/terminfo"

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

    @classmethod
    def candidate_modules(cls):
        return [Ncurses]

    @property
    def url(self):
        return f"https://ftp.gnu.org/gnu/readline/readline-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("8.1")

    def _do_linux_compile(self):
        self.run_configure("./configure", "--enable-shared=no", "--enable-static=yes", "--disable-install-examples", "--with-curses")
        self.run_make()
        self.run_make("install")


class Sqlite(ModuleBuilder):
    """
    Known issues:
    - linux: libsqlite3-dev must be installed in order for static build to succeed
    """

    m_debian = "+libsqlite3-dev"
    m_telltale = ["{include}/sqlite3.h"]

    def linker_outcome(self, is_selected):
        if is_selected and not runez.which("tclsh"):
            return LinkerOutcome.failed, "%s (apt install tcl)" % runez.red("needs tclsh")

        return super().linker_outcome(is_selected)

    @property
    def url(self):
        return f"https://github.com/sqlite/sqlite/archive/refs/tags/version-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("3.36.0")

    # noinspection PyPep8Naming
    # noinspection PyMethodMayBeStatic
    def xenv_CFLAGS(self):
        yield "-fPIC"

    def _do_linux_compile(self):
        self.run_configure(
            "./configure", "--enable-shared=no", "--enable-static=yes", "--disable-tcl", "--disable-readline", "--with-pic=yes"
        )
        self.run_make()
        self.run_make("install")


class Uuid(ModuleBuilder):
    """
    Known issues:
    - linux: uuid-dev must be installed in order for static build to succeed
    """

    m_debian = "+uuid-dev"
    m_include = "uuid"
    m_telltale = ["{include}/uuid/uuid.h"]

    @property
    def url(self):
        return f"https://sourceforge.net/projects/libuuid/files/libuuid-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("1.0.3")

    # noinspection PyPep8Naming
    # noinspection PyMethodMayBeStatic
    def xenv_CFLAGS(self):
        yield "-fPIC"

    def _do_linux_compile(self):
        self.run_configure("./configure", "--enable-shared=no", "--enable-static=yes", "--with-pic=yes")
        self.run_make()
        self.run_make("install")


class Xz(ModuleBuilder):

    m_telltale = "{include}/lzma.h"

    @property
    def url(self):
        return f"https://tukaani.org/xz/xz-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("5.2.5")

    def _do_linux_compile(self):
        self.run_configure(
            "./configure",
            "--enable-shared=no", "--enable-static=yes", "--with-pic=yes", "--disable-rpath",
            "--disable-dependency-tracking", "--disable-doc", "--disable-nls", "--without-libintl-prefix",
        )
        self.run_make()
        self.run_make("install")


class Zlib(ModuleBuilder):
    """
    Known issues:
    - linux: needs zlib1g-dev installed (even for a static build)
    """

    m_debian = "!zlib1g-dev"
    m_telltale = "{include}/zlib.h"

    @property
    def url(self):
        return f"https://zlib.net/zlib-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("1.2.11")

    # noinspection PyPep8Naming
    # noinspection PyMethodMayBeStatic
    def xenv_CFLAGS(self):
        yield "-fPIC"

    def _do_linux_compile(self):
        self.run_configure("./configure", "--64", "--static")
        self.run_make()
        self.run_make("install")

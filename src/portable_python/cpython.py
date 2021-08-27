import os

import runez

from portable_python import LOG, ModuleBuilder, PythonBuilder


class Cpython(PythonBuilder):
    """Build CPython binaries"""

    m_name = "cpython"

    base_url = "https://www.python.org/ftp/python"
    _main_python = None

    @classmethod
    def available_modules(cls):
        return [Zlib, Bzip2, LibFFI, Openssl, Readline, Xz, Sqlite, Bdb, Gdbm, Tcl, Tk, Tix, Uuid]

    @property
    def url(self):
        """Url of source tarball"""
        return f"{self.base_url}/{self.version}/Python-{self.version}.tar.xz"

    def xenv_cflags(self):
        yield "-Wno-unused-command-line-argument"
        yield self.checked_deps_folder("include", prefix="-I")
        yield self.checked_deps_folder("include/readline", prefix="-I")
        yield self.checked_deps_folder("include/openssl", prefix="-I")
        yield self.checked_deps_folder("include/uuid", prefix="-I")

    def xenv_ldflags(self):
        yield self.checked_deps_folder("lib", prefix="-L")

    def c_configure_args(self):
        yield from super().c_configure_args()
        openssl = self.setup.get_module("openssl")
        yield "--with-ensurepip=%s" % ("upgrade" if openssl else "install")
        yield "--enable-optimizations"
        yield "--with-lto"
        if openssl:
            yield f"--with-openssl={self.deps}"

        tcl = self.setup.get_module("tcl")
        if tcl:
            yield f"--with-tcltk-includes=-I{self.deps}/include"
            yield f"--with-tcltk-libs=-L{self.deps}/lib"

    @property
    def main_python(self):
        if self._main_python is None:
            main_python_candidates = ("python", "python%s" % self.version.major, "python%s.%s" % (self.version.major, self.version.minor))
            for f in runez.ls_dir(self.bin_folder):
                if f.name in main_python_candidates:
                    self._main_python = runez.basename(f, extension_marker=None, follow=True)
                    break

        return self._main_python or "python"

    def _prepare(self):
        self.setup.fix_lib_permissions()

    def _finalize(self):
        if self.setup.get_module("openssl"):
            self.run(self.bin_folder / self.main_python, "-mpip", "install", "-U", "pip", "setuptools", "wheel")

        if self.setup.static:
            self._symlink_static_libs()

        self.correct_symlinks()
        self.cleanup_distribution()
        self.run(self.bin_folder / self.main_python, "-mcompileall")
        runez.compress(self.install_folder, self.tarball_path)

    def _symlink_static_libs(self):
        """Symlink libpython*.a to save space"""
        libs = []
        for dirpath, dirnames, filenames in os.walk(self.install_folder / "lib"):
            for name in filenames:
                if name.startswith("libpython"):
                    libs.append(os.path.join(dirpath, name))

        if len(libs) == 2:
            shorter, longer = sorted(libs, key=lambda x: len(x))
            shorter_size = runez.to_path(shorter).stat().st_size
            longer_size = runez.to_path(longer).stat().st_size
            if shorter_size == longer_size:  # Double-check that they are the same size (they should be identical)
                runez.symlink(longer, shorter)

    @runez.cached_property
    def cleanable_basenames(self):
        """Folders that are not useful in deliverable (test suites etc)"""
        r = {
            "__phello__.foo.py",
            "__pycache__",  # Clear it because lots of unneeded stuff is in there initially, -mcompileall regenerates it
            "_bundled",
            "idle_test",
            "test",
            "tests",
        }
        if not self.setup.static:
            # Don't keep static compilation file unless --static
            r.add(f"libpython{self.version.major}.{self.version.minor}.a")

        return r

    @runez.cached_property
    def cleanable_prefixes(self):
        """Files/folders that are not useful in deliverable, but name varies, can be identified by their prefix"""
        r = set()
        if not self.setup.static:
            r.add("config-%s.%s-" % (self.version.major, self.version.minor))

        return r

    @runez.cached_property
    def cleanable_suffixes(self):
        """Files/folders that are not useful in deliverable, but name varies, can be identified by their suffix"""
        return {"_failed.so"}

    def should_clean(self, basename):
        if basename in self.cleanable_basenames:
            return True

        if any(basename.startswith(x) for x in self.cleanable_prefixes):
            return True

        return any(basename.endswith(x) for x in self.cleanable_suffixes)

    def cleanup_distribution(self):
        cleaned = []
        for dirpath, dirnames, filenames in os.walk(self.install_folder):
            removed = []
            for name in dirnames:
                if self.should_clean(name):
                    # Remove unnecessary file, to save on space
                    full_path = os.path.join(dirpath, name)
                    removed.append(name)
                    cleaned.append(name)
                    runez.delete(full_path, logger=None)

            for name in removed:
                dirnames.remove(name)

            for name in filenames:
                if self.should_clean(name):
                    full_path = os.path.join(dirpath, name)
                    cleaned.append(name)
                    runez.delete(full_path, logger=None)

        if cleaned:
            names = runez.joined(sorted(set(cleaned)))
            LOG.info("Cleaned %s: %s" % (runez.plural(cleaned, "build artifact"), runez.short(names)))

    def correct_symlinks(self):
        with runez.CurrentFolder(self.bin_folder):
            all_files = {}
            files = {}
            symlinks = {}
            cleanable = ("2to3", "easy_install", "idle3", "pip", "pydoc", "wheel")
            for f in runez.ls_dir(self.bin_folder):
                if f.name.startswith(cleanable):
                    runez.delete(f)  # Get rid of old junk, can be pip installed if needed
                    continue

                all_files[f.name] = f
                if f.is_symlink():
                    symlinks[f.name] = f

                else:
                    files[f.name] = f

            if "python" not in all_files:
                runez.symlink(self.main_python, "python")

            for f in files.values():
                if f.name != self.main_python:
                    self._auto_correct_shebang(f)

    def _auto_correct_shebang(self, path):
        lines = []
        with open(path) as fh:
            for line in fh:
                if lines:
                    lines.append(line)

                elif not line.startswith("#!") or "bin/python" not in line:
                    return

                else:
                    lines.append("#!/bin/sh\n")
                    lines.append('"exec" "$(dirname $0)/%s" "$0" "$@"\n' % self.main_python)

        LOG.info("Auto-corrected shebang for %s" % runez.short(path))
        with open(path, "wt") as fh:
            for line in lines:
                fh.write(line)


class Bdb(ModuleBuilder):
    """See https://docs.python.org/3/library/dbm.html"""

    m_name = "bdb"
    c_configure_cwd = "build_unix"
    c_configure_program = "../dist/configure"

    @property
    def url(self):
        return f"https://ftp.osuosl.org/pub/blfs/conglomeration/db/db-{self.version}.tar.gz"

    @property
    def version(self):
        return "6.2.32"

    def xenv_cflags(self):
        yield "-fPIC"

    def c_configure_args(self):
        yield from super().c_configure_args()
        yield "--enable-shared=no"
        yield "--enable-static=yes"
        yield "--enable-dbm"
        yield "--with-pic=yes"


class Bzip2(ModuleBuilder):
    """
    See https://docs.python.org/3/library/bz2.html
    """

    m_name = "bzip2"
    m_telltale = "{include}/bzlib.h"
    c_configure_program = None
    make_args = None

    @property
    def url(self):
        return f"https://sourceware.org/pub/bzip2/bzip2-{self.version}.tar.gz"

    @property
    def version(self):
        return "1.0.8"

    def run_make_install(self):
        self.run("make", "install", f"PREFIX={self.deps}", "CFLAGS=-fPIC -O2 -g -D_FILE_OFFSET_BITS=64")


class Gdbm(ModuleBuilder):
    """See https://docs.python.org/2.7/library/gdbm.html"""

    m_name = "gdbm"
    m_telltale = "{include}/gdbm.h"

    @classmethod
    def auto_use_with_reason(cls, target):
        if target.is_macos:
            return False, runez.brown("only on demand on macos")  # Can build, but waste of time

        return super().auto_use_with_reason(target)

    @property
    def url(self):
        return f"https://ftp.gnu.org/gnu/gdbm/gdbm-{self.version}.tar.gz"

    @property
    def version(self):
        return "1.18.1"

    def xenv_cflags(self):
        yield "-fPIC"

    def c_configure_args(self):
        # CPython setup.py looks for libgdbm_compat and gdbm-ndbm.h, which require --enable-libgdbm-compat
        yield from super().c_configure_args()
        yield "--enable-shared=no"
        yield "--enable-static=yes"
        yield "--with-pic=yes"
        yield "--disable-rpath"
        yield "--without-libiconv-prefix"
        yield "--without-libintl-prefix"
        yield "--without-readline"


class LibFFI(ModuleBuilder):

    m_name = "libffi"
    m_telltale = ["/usr/share/doc/libffi-dev", "{include}/ffi/ffi.h"]

    @property
    def url(self):
        return f"https://github.com/libffi/libffi/releases/download/v{self.version}/libffi-{self.version}.tar.gz"

    @property
    def version(self):
        return "3.3"

    def xenv_cflags(self):
        yield "-fPIC"

    def c_configure_args(self):
        yield from super().c_configure_args()
        yield "--enable-shared=no"
        yield "--enable-static=yes"
        yield "--with-pic=yes"
        yield "--disable-multi-os-directory"
        yield "--disable-docs"


class Openssl(ModuleBuilder):

    m_name = "openssl"
    m_telltale = "{include}/openssl/ssl.h"
    c_configure_program = "./Configure"

    @property
    def url(self):
        return f"https://www.openssl.org/source/openssl-{self.version}.tar.gz"

    @property
    def version(self):
        return "1.1.1k"

    def c_configure_args(self):
        yield from super().c_configure_args()
        yield f"--openssldir={self.deps}"
        yield "-DPEDANTIC"
        yield "no-shared"
        if self.target.is_macos:
            yield "darwin64-%s-cc" % self.target.architecture

        else:
            yield "%s-%s" % (self.target.platform, self.target.architecture)


class Readline(ModuleBuilder):

    m_name = "readline"
    m_telltale = "{include}/readline/readline.h"

    @property
    def url(self):
        return f"https://ftp.gnu.org/gnu/readline/readline-{self.version}.tar.gz"

    @property
    def version(self):
        return "8.1"

    def c_configure_args(self):
        yield from super().c_configure_args()
        yield "--enable-shared=no"
        yield "--enable-static=yes"
        yield "--disable-install-examples"
        yield "--with-curses"

    # TODO: check linux again
    # def make_args(self):
    #     if self.target.is_linux:
    #         # See https://github.com/Homebrew/homebrew-core/blob/HEAD/Formula/readline.rb
    #         yield "SHLIB_LIBS=-lcurses"


class Sqlite(ModuleBuilder):

    m_name = "sqlite"
    m_telltale = "{include}/sqlite3.h"

    @classmethod
    def auto_use_with_reason(cls, target):
        if not runez.which("tclsh"):
            return None, runez.brown("requires tclsh")

        return super().auto_use_with_reason(target)

    @property
    def url(self):
        return f"https://github.com/sqlite/sqlite/archive/refs/tags/version-{self.version}.tar.gz"

    @property
    def version(self):
        return "3.36.0"

    def xenv_cflags(self):
        yield "-fPIC"

    def c_configure_args(self):
        yield from super().c_configure_args()
        yield "--enable-shared=no"
        yield "--enable-static=yes"
        yield "--disable-tcl"
        yield "--disable-readline"
        yield "--with-pic=yes"


class TclTkModule(ModuleBuilder):
    """
    Common Tcl/Tk stuff
    TODO: macos build fails with Symbol not found: _TclBN_mp_clear
    """

    m_telltale = ["{include}/tk", "{include}/tk.h"]

    @classmethod
    def auto_use_with_reason(cls, target):
        if not target.is_macos and not os.path.isdir("/usr/include/X11"):
            return False, runez.brown("requires libx11-dev")

        return super().auto_use_with_reason(target)

    @property
    def version(self):
        return "8.6.10"

    def c_configure_args(self):
        yield from super().c_configure_args()
        yield "--enable-shared=no"
        yield "--enable-threads"

    def run_make_install(self):
        self.run("make")
        if self.__class__ is Tk:
            runez.touch("wish")

        self.run("make", "install")
        if self.__class__ is not Tix:
            self.run("make", "install-private-headers")


class Tcl(TclTkModule):

    m_name = "tcl"
    c_configure_cwd = "unix"

    @property
    def url(self):
        return f"https://prdownloads.sourceforge.net/tcl/tcl{self.version}-src.tar.gz"

    def _prepare(self):
        for path in runez.ls_dir(self.m_src_build / "pkgs"):
            if path.name.startswith(("sqlite", "tdbc")):
                # Remove packages we don't care about and can pull in unwanted symbols
                runez.delete(path)


class Tk(TclTkModule):

    m_name = "tk"
    c_configure_cwd = "unix"

    @property
    def url(self):
        return f"https://prdownloads.sourceforge.net/tcl/tk{self.version}-src.tar.gz"

    def xenv_cflags(self):
        yield self.checked_deps_folder("include", prefix="-I")

    def xenv_ldflags(self):
        yield self.checked_deps_folder("lib", prefix="-L")

    def c_configure_args(self):
        yield from super().c_configure_args()
        yield f"--with-tcl={self.deps}/lib"
        yield "--without-x"
        if self.target.is_macos:
            yield "--enable-aqua=yes"


class Tix(TclTkModule):

    m_name = "tix"
    c_configure_program = "/bin/sh configure"

    @property
    def url(self):
        return f"https://github.com/python/cpython-source-deps/archive/tix-{self.version}.tar.gz"

    @property
    def version(self):
        return "8.4.3.6"

    def xenv_cflags(self):
        # Needed to avoid error: Getting no member named 'result' in 'struct Tcl_Interp'
        yield "-DUSE_INTERP_RESULT"
        yield "-Wno-implicit-function-declaration"  # Allows to not fail compilation due to missing 'panic' symbol
        yield self.checked_deps_folder("include", prefix="-I")

    def xenv_ldflags(self):
        yield self.checked_deps_folder("lib", prefix="-L")

    def c_configure_args(self):
        yield from super().c_configure_args()
        yield f"--with-tcl={self.deps}/lib"
        yield f"--with-tk={self.deps}/lib"
        yield "--without-x"


class Uuid(ModuleBuilder):

    m_name = "uuid"
    m_telltale = "{include}/uuid/uuid.h"

    @property
    def url(self):
        return f"https://sourceforge.net/projects/libuuid/files/libuuid-{self.version}.tar.gz"

    @property
    def version(self):
        return "1.0.3"

    def c_configure_args(self):
        yield from super().c_configure_args()
        yield "--enable-shared=no"
        yield "--enable-static=yes"


class Xz(ModuleBuilder):

    m_name = "xz"
    m_telltale = "{include}/lzma.h"

    @property
    def url(self):
        return f"https://tukaani.org/xz/xz-{self.version}.tar.gz"

    @property
    def version(self):
        return "5.2.5"

    def c_configure_args(self):
        yield from super().c_configure_args()
        yield "--with-pic=yes"
        yield "--enable-shared=no"
        yield "--enable-static=yes"
        yield "--disable-doc"
        yield "--disable-xz"
        yield "--disable-xzdec"
        yield "--disable-lzmadec"
        yield "--disable-lzmainfo"
        yield "--disable-lzma-links"
        yield "--disable-scripts"
        yield "--disable-rpath"


class Zlib(ModuleBuilder):

    m_name = "zlib"
    m_telltale = "{include}/zlib.h"

    @property
    def url(self):
        return f"https://zlib.net/zlib-{self.version}.tar.gz"

    @property
    def version(self):
        return "1.2.11"

    def c_configure_args(self):
        yield f"--prefix={self.c_configure_prefix}"
        yield "--64"
        yield "--static"

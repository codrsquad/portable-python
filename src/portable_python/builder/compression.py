from portable_python.builder import ModuleBuilder


class Bzip2(ModuleBuilder):
    """
    See https://docs.python.org/3/library/bz2.html
    """

    c_configure_program = None
    make_args = None
    telltale = "{include}/bzlib.h"

    @property
    def url(self):
        return f"https://sourceware.org/pub/bzip2/bzip2-{self.version}.tar.gz"

    @property
    def version(self):
        return "1.0.8"

    def run_make_install(self):
        self.run("make", "install", f"PREFIX={self.deps}", "CFLAGS=-fPIC -O2 -g -D_FILE_OFFSET_BITS=64")


class Xz(ModuleBuilder):

    telltale = "{include}/lzma.h"

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

    telltale = "{include}/zlib.h"

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

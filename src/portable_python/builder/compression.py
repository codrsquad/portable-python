from portable_python.builder import BuildSetup, ModuleBuilder


@BuildSetup.module_builders.declare
class Bzip2(ModuleBuilder):
    """See https://docs.python.org/3/library/bz2.html"""

    @property
    def url(self):
        return f"https://sourceware.org/pub/bzip2/bzip2-{self.version}.tar.gz"

    @property
    def version(self):
        return "1.0.8"

    def _do_linux_compile(self):
        self.run("make", "install", "PREFIX=%s" % self.deps)


@BuildSetup.module_builders.declare
class Xz(ModuleBuilder):

    @property
    def url(self):
        return f"https://tukaani.org/xz/xz-{self.version}.tar.gz"

    @property
    def version(self):
        return "5.2.5"

    def c_configure_args(self):
        yield from super().c_configure_args()
        yield "--disable-xz"
        yield "--disable-xzdec"
        yield "--disable-lzmadec"
        yield "--disable-lzmainfo"
        yield "--disable-lzma-links"
        yield "--disable-scripts"

    def _do_linux_compile(self):
        self.run_configure()
        self.run("make")
        self.run("make", "install", "DESTDIR=%s" % self.deps.parent)


@BuildSetup.module_builders.declare
class Zlib(ModuleBuilder):

    @property
    def url(self):
        return f"https://zlib.net/zlib-{self.version}.tar.gz"

    @property
    def version(self):
        return "1.2.11"

    def _do_linux_compile(self):
        self.run_configure()
        self.run("make")
        self.run("make", "install", "DESTDIR=%s" % self.deps.parent)

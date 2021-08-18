from portable_python.builder import BuildSetup, ModuleBuilder


@BuildSetup.module_builders.declare
class Xorgproto(ModuleBuilder):

    needs_platforms = ["linux"]

    @property
    def url(self):
        return f"ftp://mirror.csclub.uwaterloo.ca/x.org/pub/current/src/proto/xorgproto-{self.version}.tar.gz"

    @property
    def version(self):
        return "2019.1"

    def _do_linux_compile(self):
        self.run_configure()
        self.run("make")
        self.run("make", "install", "DESTDIR=%s" % self.deps.parent)


@BuildSetup.module_builders.declare
class Xproto(ModuleBuilder):

    needs_platforms = ["linux"]

    @property
    def url(self):
        return f"ftp://mirror.csclub.uwaterloo.ca/x.org/pub/current/src/proto/xproto-{self.version}.tar.gz"

    @property
    def version(self):
        return "7.0.31"

    def _do_linux_compile(self):
        self.run_configure()
        self.run("make")
        self.run("make", "install", "DESTDIR=%s" % self.deps.parent)

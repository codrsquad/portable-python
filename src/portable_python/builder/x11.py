from portable_python.builder import BuildSetup, ModuleBuilder


@BuildSetup.module_builders.declare
class Xorgproto(ModuleBuilder):

    base_url = "https://gitlab.freedesktop.org/xorg/proto/xorgproto/-/archive/xorgproto-{version}/xorgproto-xorgproto-{version}.tar.gz"
    needs_platforms = ["linux"]

    @property
    def url(self):
        return self.base_url.format(version=self.version)

    @property
    def version(self):
        return "2019.1"

    def _do_linux_compile(self):
        self.run("make")
        self.run("make", "install", "DESTDIR=%s" % self.deps.parent)


@BuildSetup.module_builders.declare
class Xproto(ModuleBuilder):

    base_url = "https://gitlab.freedesktop.org/xorg/proto/xproto/-/archive/xproto-{version}/xproto-xproto-{version}.tar.gz"
    needs_platforms = ["linux"]

    @property
    def url(self):
        return self.base_url.format(version=self.version)

    @property
    def version(self):
        return "7.0.31"

    def _do_linux_compile(self):
        self.run_configure()
        self.run("make")
        self.run("make", "install", "DESTDIR=%s" % self.deps.parent)

from portable_python import ModuleBuilder


class Autoconf(ModuleBuilder):
    """Needed so we don't accidentally use any /usr/local autoconf"""

    @property
    def url(self):
        return f"https://ftp.gnu.org/gnu/autoconf/autoconf-{self.version}.tar.xz"

    @property
    def version(self):
        return self.cfg_version("2.71")

    def _do_linux_compile(self):
        self.run_configure("./configure")
        self.run_make()
        self.run_make("install")


class Automake(ModuleBuilder):
    """Needed so we don't accidentally use any /usr/local automake"""

    @property
    def url(self):
        return f"https://ftp.gnu.org/gnu/automake/automake-{self.version}.tar.xz"

    @property
    def version(self):
        return self.cfg_version("1.16.4")

    def _do_linux_compile(self):
        self.run_configure("./configure")
        self.run_make()
        self.run_make("install")


class PkgConfig(ModuleBuilder):
    """Ensure pkg-config is present"""

    @property
    def url(self):
        # return f"https://github.com/freedesktop/pkg-config/archive/refs/tags/pkg-config-{self.version}.tar.gz"
        return f"https://pkg-config.freedesktop.org/releases/pkg-config-{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("0.29.1")

    def _do_linux_compile(self):
        self.run_configure("./configure", f"--prefix={self.deps}", "--disable-shared", "--enable-static", "--with-internal-glib")
        self.run_make()
        self.run_make("install")
